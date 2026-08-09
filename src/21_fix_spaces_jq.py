"""Pred fázou 6 — #J a #Q.

    python src/21_fix_spaces_jq.py           # dry-run
    python src/21_fix_spaces_jq.py --apply   # zapíše out/ASR_v9.ifc

Čo robí
-------
A  #J  `LongName` štyroch priestorov, ktoré §6 pomenovala „Inštalačná
       šachta", hoci výkres ich značí `VT01 01`/`VT01 02` → „Výťahová
       šachta". Nemení sa `Name` ani geometria. Priestory sa nehľadajú
       podľa mena, ale podľa **pôdorysu** — meno je práve to, čo je zle.
B  #J  chýbajúce šachtové priestory. Pravidlo: šachta je na podlaží,
       ktorého **strop prerazí jej void**. Void je existujúci
       `IfcOpeningElement` s pôdorysom presne šachty, takže sa nič
       nefabrikuje — preberá sa tvar, ktorý v modeli je, a oreže sa na
       pásmo podlažia. Výťahové šachty sa nekreslia (rozhodnutie Samuela).
C  #Q  vnorená `IfcZone` s nájomnými priestormi 3NP, vložená do
       existujúcej `IfcZone` „Pronajmutelné".
D  #J  `IfcZone` na každý zvislý stĺpec, aby šachta bola **jedna vec**
       naprieč podlažiami. `ObjectType` podľa spec (IFC4.3 §5.4.3.82):
       `'ElevatorShaft'` — *a collection of spaces within an elevator,
       potentially going through many storeys*; `'RisingDuct'` —
       *A collection of vertical airspaces*. Zóna geometriu nemá a mať
       nemôže, takže tu nevzniká ani milimeter tvaru.

Prečo takto a nie inak
----------------------
* Horný koniec šachty sa z otvorov odvodiť **nedá** — Revit prereže
  všetky dosky, ktoré void pretne, u všetkých stĺpcov rovnako. Preto sa
  priestor dopĺňa len tam, kde je dôkaz o prieniku stropom **a** kde ho
  ešte niet.
* Test „sú okolo pôdorysu steny" sa nepoužíva: bboxy stien sú dlhé,
  takže štyri strany nájde prakticky vždy a nič nerozlíši.
* Tvar sa robí vzorom rekonštruovaných priestorov 1NP
  (`IfcArbitraryClosedProfileDef` + extrúzia, placement k podlažiu,
  polyline vo svetových XY), nie vzorom Revitu s otočeným profilom.

Kontrola, ktorú skript robí sám na sebe
---------------------------------------
Po zostavení sa každý nový priestor **odmeria z geometrie** a porovná
s pôdorysom a pásmom, z ktorých vznikol. Nesúhlas zastaví beh.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v8.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v9.ifc")

DRY_RUN = True

#: pásma podlaží: strop = spodok dosky nad, zmerané v ASR_v8
BANDS = {"1NP": (0.0, 4600.0), "2NP": (5000.0, 8800.0),
         "3NP": (9200.0, 13000.0), "4NP": (13400.0, 16550.0)}

#: pôdorys pod touto plochou je prestup potrubia, nie šachta (mm²)
MIN_AREA = 100_000.0

#: tolerancia pri kontrole odmeraného tvaru
TOL = 1.0

LIFT = "Výťahová šachta"
DUCT = "Inštalačná šachta"

#: 3NP — nájomné priestory podľa legendy D.1.1.03, stĺpec „Príslušnosť"
NAJOMNE_3NP = ["3.01", "3.02", "3.03", "3.04", "3.05", "3.06",
               "3.07", "3.08", "3.09", "3.10", "3.11"]
NAJOMNE_3NP_M2 = 584.06


# --------------------------------------------------------------------------
# geometria
# --------------------------------------------------------------------------


def bboxes(model, products):
    """``{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)}`` v mm."""
    out = {}
    products = [p for p in products if p.Representation is not None]
    if not products:
        return out
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        st, model, max(1, (os.cpu_count() or 2) - 1), include=products)
    if not it.initialize():
        return out
    while True:
        sh = it.get()
        v = sh.geometry.verts
        if v:
            xs, ys, zs = v[0::3], v[1::3], v[2::3]
            out[sh.guid] = (min(xs) * 1000.0, min(ys) * 1000.0, min(zs) * 1000.0,
                            max(xs) * 1000.0, max(ys) * 1000.0, max(zs) * 1000.0)
        if not it.next():
            break
    return out


def _area(b):
    return (b[3] - b[0]) * (b[4] - b[1])


def _inter(a, b):
    ix = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    iy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ix * iy


def similar(a, b):
    """Prienik voči väčšiemu — ten istý pôdorys, nie vnorenie."""
    m = max(_area(a), _area(b))
    return (_inter(a, b) / m) if m > 0 else 0.0


def storey_of(e):
    for r in (getattr(e, "Decomposes", None) or ()):
        return r.RelatingObject
    for r in (getattr(e, "ContainedInStructure", None) or ()):
        return r.RelatingStructure
    return None


def host_of(feature):
    for r in (getattr(feature, "VoidsElements", None) or ()):
        return r.RelatingBuildingElement
    return None


# --------------------------------------------------------------------------
# stavba priestoru
# --------------------------------------------------------------------------


def make_space(m, storey, foot, band, name, longname, owner, context):
    """Nový ``IfcSpace`` vzorom rekonštruovaných priestorov 1NP."""
    x0, y0, x1, y1 = foot
    zb, zt = band
    elev = storey.Elevation or 0.0

    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    poly = m.create_entity(
        "IfcPolyline",
        Points=[m.create_entity("IfcCartesianPoint", Coordinates=(float(x), float(y)))
                for x, y in pts])
    profile = m.create_entity("IfcArbitraryClosedProfileDef",
                              ProfileType="AREA", OuterCurve=poly)
    origin = m.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, zb - elev))
    solid = m.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=m.create_entity("IfcAxis2Placement3D", Location=origin),
        ExtrudedDirection=m.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=float(zt - zb))
    shape = m.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context, RepresentationIdentifier="Body",
        RepresentationType="SweptSolid", Items=[solid])

    placement = m.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=storey.ObjectPlacement,
        RelativePlacement=m.create_entity(
            "IfcAxis2Placement3D",
            Location=m.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))))

    space = m.create_entity(
        "IfcSpace",
        GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
        Name=name, LongName=longname,
        ObjectPlacement=placement,
        Representation=m.create_entity("IfcProductDefinitionShape",
                                       Representations=[shape]),
        CompositionType="ELEMENT", PredefinedType="INTERNAL")

    # do priestorovej štruktúry — k existujúcej agregácii podlažia
    for rel in (storey.IsDecomposedBy or ()):
        rel.RelatedObjects = tuple(rel.RelatedObjects) + (space,)
        break
    else:
        m.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                        OwnerHistory=owner, RelatingObject=storey,
                        RelatedObjects=(space,))

    w, d, h = x1 - x0, y1 - y0, zt - zb
    psets = [
        m.create_entity(
            "IfcPropertySet", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            Name="Pset_SpaceCommon",
            HasProperties=[m.create_entity(
                "IfcPropertySingleValue", Name="IsExternal",
                NominalValue=m.create_entity("IfcBoolean", False))]),
        m.create_entity(
            "IfcElementQuantity", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            Name="Qto_SpaceBaseQuantities",
            Quantities=[
                m.create_entity("IfcQuantityArea", Name="NetFloorArea",
                                AreaValue=round(w * d / 1e6, 2)),
                m.create_entity("IfcQuantityArea", Name="GrossFloorArea",
                                AreaValue=round(w * d / 1e6, 2)),
                m.create_entity("IfcQuantityLength", Name="Height", LengthValue=h)]),
        m.create_entity(
            "IfcElementQuantity", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            Name="Qto_BodyGeometryValidation",
            Quantities=[
                m.create_entity("IfcQuantityArea", Name="NetSurfaceArea",
                                AreaValue=(2 * w * d + 2 * (w + d) * h) / 1e6),
                m.create_entity("IfcQuantityVolume", Name="NetVolume",
                                VolumeValue=w * d * h / 1e9)]),
    ]
    rels = [m.create_entity("IfcRelDefinesByProperties",
                            GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                            RelatedObjects=(space,), RelatingPropertyDefinition=p)
            for p in psets]
    return space, [space.GlobalId] + [p.GlobalId for p in psets] + [r.GlobalId for r in rels]


def make_zone(m, owner, name, longname, objecttype, members):
    zone = m.create_entity("IfcZone", GlobalId=ifcopenshell.guid.new(),
                           OwnerHistory=owner, Name=name, LongName=longname,
                           ObjectType=objecttype)
    rel = m.create_entity("IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(),
                          OwnerHistory=owner, RelatedObjects=tuple(members),
                          RelatingGroup=zone)
    return zone, [zone.GlobalId, rel.GlobalId]


# ==========================================================================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = DRY_RUN and not args.apply

    print("vstup :", args.src)
    print("výstup:", args.dst, "(DRY-RUN)" if dry else "")
    print()

    m = ifcopenshell.open(args.src)
    added: list[str] = []
    log: list[str] = []

    storeys = {s.Name: s for s in m.by_type("IfcBuildingStorey")}
    spaces = list(m.by_type("IfcSpace"))
    owner = spaces[0].OwnerHistory
    context = m.by_type("IfcGeometricRepresentationSubContext")[0]
    for c in m.by_type("IfcGeometricRepresentationSubContext"):
        if c.ContextIdentifier == "Body":
            context = c
            break

    space_bb = bboxes(m, spaces)
    feats = list(m.by_type("IfcFeatureElement"))
    feat_bb = bboxes(m, feats)
    by_gid = {e.GlobalId: e for e in spaces + feats}

    # ---- stĺpce: pôdorysy zvislých otvorov + existujúce šachty -----------
    span = max(BANDS[k][1] for k in BANDS) - min(BANDS[k][0] for k in BANDS)
    seeds = []
    for s in spaces:
        if "šacht" in (s.LongName or "").lower() and s.GlobalId in space_bb:
            seeds.append((s, space_bb[s.GlobalId]))
    for gid, bb in feat_bb.items():
        if bb[5] - bb[2] > span and _area(bb) >= MIN_AREA:
            seeds.append((by_gid[gid], bb))

    columns: list[list] = []
    for e, bb in sorted(seeds, key=lambda x: -_area(x[1])):
        for col in columns:
            if similar(col[0][1], bb) >= 0.5:
                col.append((e, bb))
                break
        else:
            columns.append([(e, bb)])

    # stĺpec bez jediného priestoru a bez otvoru nás nezaujíma; schodiskový
    # otvor sa odfiltruje tým, že jeho pôdorys nesie priestor „Schodiskový…"
    shafts = []
    for col in columns:
        sp = [e for e, _ in col if e.is_a("IfcSpace")]
        fe = [(e, b) for e, b in col if not e.is_a("IfcSpace")]
        if not sp and not fe:
            continue
        if any("schodisk" in (s.LongName or "").lower() for s in sp):
            continue
        ref = col[0][1]
        # schodiskový otvor nemá šachtový priestor a je veľký — vynechať
        if not sp and _area(ref) > 10e6:
            continue
        shafts.append({"foot": (ref[0], ref[1], ref[3], ref[4]),
                       "spaces": sp, "feats": fe,
                       "area": _area(ref) / 1e6})

    # Výťah sa nerozoznáva podľa mena — meno je práve to, čo je zle (#J).
    # Rozhoduje **šachtová jama**: otvor v základovej doske `ZD02` alebo
    # v podkladnom betóne `DZ01` pod tým istým pôdorysom. Inštalačná šachta
    # pod základovú škáru nejde, výťahová áno.
    pits = [b for gid, b in feat_bb.items()
            if (by_gid[gid].Name or "").startswith(("ZD02", "DZ01"))]
    for sh in shafts:
        fb = (sh["foot"][0], sh["foot"][1], 0.0, sh["foot"][2], sh["foot"][3], 0.0)
        sh["lift"] = any(similar(fb, p) >= 0.5 for p in pits)

    print("ZVISLÉ STĹPCE")
    for i, sh in enumerate(shafts, 1):
        print("   %d  %6.2f m²  priestory: %-24s %s"
              % (i, sh["area"],
                 ", ".join(s.Name for s in sh["spaces"]) or "žiadne",
                 "VÝŤAH" if sh["lift"] else "inštalačná"))

    # ---- A · #J LongName výťahov ----------------------------------------
    fixed = 0
    for sh in shafts:
        if not sh["lift"]:
            continue
        for s in sh["spaces"]:
            if s.LongName != LIFT:
                s.LongName = LIFT
                fixed += 1
    log.append("#J   LongName → %r na %d priestoroch" % (LIFT, fixed))

    # ---- B · #J chýbajúce priestory -------------------------------------
    # podlažie, ktorého strop void prerazí
    def pierced(sh):
        """Podlažia, ktorých **strop** void prerazí.

        Doska nad 1NP je v modeli kontajnovaná v 1NP (4600–4850), doska nad
        2NP v 2NP (8800–9050) atď., takže podlažie hostiteľa je priamo
        podlažie, ktorého stropom šachta prechádza.
        """
        out = set()
        for f, _ in sh["feats"]:
            h = host_of(f)
            hs = storey_of(h) if h is not None else None
            if hs is not None and hs.Name in BANDS:
                out.add(hs.Name)
        return out

    plan = []
    for sh in shafts:
        if sh["lift"]:
            continue
        have = {storey_of(s).Name for s in sh["spaces"] if storey_of(s)}
        want = pierced(sh)
        if not want:
            continue
        for name in sorted(want, key=lambda n: BANDS[n][0]):
            if name in have or name not in BANDS:
                continue
            plan.append((name, sh))

    # čísla nadviažu na rad podlažia, poradie podľa §6: podlažie → Y → X
    plan.sort(key=lambda p: (BANDS[p[0]][0], p[1]["foot"][1], p[1]["foot"][0]))
    nextnum: dict[str, int] = {}
    for name in BANDS:
        used = [int((s.Name or "0.0").split(".")[1])
                for s in spaces if storey_of(s) is not None
                and storey_of(s).Name == name and (s.Name or "").count(".") == 1
                and s.Name.split(".")[1].isdigit()]
        nextnum[name] = (max(used) + 1) if used else 1

    created = []
    for name, sh in plan:
        num = "%s.%02d" % (name[0], nextnum[name])
        nextnum[name] += 1
        sp, gids = make_space(m, storeys[name], sh["foot"], BANDS[name],
                              num, DUCT, owner, context)
        added.extend(gids)
        created.append((sp, sh["foot"], BANDS[name]))
        sh["spaces"].append(sp)
        log.append("#J   nový priestor %-6s %-20s %5.2f m² na %s"
                   % (num, DUCT, sh["area"], name))
    if not created:
        log.append("#J   všetky šachtové priestory už existujú — preskočené")

    # ---- kontrola: odmerať, čo sa vyrobilo ------------------------------
    if created:
        got = bboxes(m, [s for s, _, _ in created])
        for sp, foot, band in created:
            b = got.get(sp.GlobalId)
            if b is None:
                raise SystemExit("STOP: %s nemá geometriu" % sp.Name)
            want = (foot[0], foot[1], band[0], foot[2], foot[3], band[1])
            if any(abs(a - w) > TOL for a, w in zip(b, want)):
                raise SystemExit(
                    "STOP: %s odmerané %s, čakané %s" % (sp.Name, b, want))
        log.append("#J   kontrola tvaru: %d z %d sedí na %.1f mm"
                   % (len(created), len(created), TOL))

    # ---- C · #Q vnorená zóna pre 3NP ------------------------------------
    pron = next((z for z in m.by_type("IfcZone") if z.Name == "Pronajmutelné"), None)
    if pron is None:
        raise SystemExit("STOP: IfcZone 'Pronajmutelné' v modeli nie je")
    by_name = {s.Name: s for s in m.by_type("IfcSpace")}
    najomne = [by_name[n] for n in NAJOMNE_3NP if n in by_name]
    if len(najomne) != len(NAJOMNE_3NP):
        raise SystemExit("STOP: na 3NP chýbajú priestory %s"
                         % sorted(set(NAJOMNE_3NP) - set(by_name)))

    def qto_area(s):
        for r in (s.IsDefinedBy or ()):
            if r.is_a("IfcRelDefinesByProperties"):
                d = r.RelatingPropertyDefinition
                if d.is_a("IfcElementQuantity"):
                    for q in d.Quantities:
                        if q.Name == "NetFloorArea":
                            return q.AreaValue
        return 0.0

    suma = sum(qto_area(s) for s in najomne)
    if abs(suma - NAJOMNE_3NP_M2) > 0.05:
        raise SystemExit("STOP: nájomná plocha 3NP je %.2f m², legenda čaká %.2f"
                         % (suma, NAJOMNE_3NP_M2))

    existing = {o.Name for r in (pron.IsGroupedBy or ()) for o in r.RelatedObjects}
    if "Nájomné priestory 3NP" in existing:
        log.append("#Q   zóna 3NP už existuje — preskočené")
    else:
        z, gids = make_zone(m, owner, "Nájomné priestory 3NP",
                            "Prenajímateľná plocha 3NP", None, najomne)
        added.extend(gids)
        pron.IsGroupedBy[0].RelatedObjects = \
            tuple(pron.IsGroupedBy[0].RelatedObjects) + (z,)
        log.append("#Q   IfcZone 'Nájomné priestory 3NP' — %d priestorov, "
                   "%.2f m², vložená do 'Pronajmutelné'" % (len(najomne), suma))

    # ---- D · #J zóny šácht ----------------------------------------------
    have_zone = {z.Name for z in m.by_type("IfcZone")}
    nl = nd = 0
    for sh in shafts:
        if not sh["spaces"]:
            continue
        if sh["lift"]:
            nl += 1
            nm, ot, ln = "Výťahová šachta %d" % nl, "ElevatorShaft", LIFT
        else:
            nd += 1
            nm, ot, ln = "Inštalačná šachta %d" % nd, "RisingDuct", DUCT
        if nm in have_zone:
            continue
        _, gids = make_zone(m, owner, nm, ln, ot, sh["spaces"])
        added.extend(gids)
        log.append("#J   IfcZone %-22r ObjectType=%-14r %d priestorov"
                   % (nm, ot, len(sh["spaces"])))

    print("\nZMENY")
    for line in log:
        print("  " + line)
    print("\n  GlobalId nových: %d" % len(added))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(added)}, fh,
                  ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
