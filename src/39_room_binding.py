"""Fáza 20 — #BD: dvere, stĺpy a podlahové vpuste do miestností.

    python src/39_room_binding.py           # dry-run
    python src/39_room_binding.py --apply   # zapíše out/ASR_v27.ifc

Čo hovorí schéma
----------------
Samuel sa pýtal, kam to podľa IFC patrí. Schéma na to má **tri rôzne
vzťahy** a odpoveď nie je „jeden z nich", ale „každý na svoju otázku":

``IfcRelContainedInSpatialStructure``
    „V čom prvok primárne je." *„The containment relationship … has to be
    a hierarchical relationship; an element can only be contained within a
    single spatial structure element."* Platným kontajnerom je ktorýkoľvek
    `IfcSpatialElement`, teda aj `IfcSpace`; `IfcBuildingStorey` je podľa
    §4.1.5.13 len **predvolený**, nie predpísaný. Exkluzivita znamená, že
    dvere medzi chodbou a kanceláriou sa musia prikloniť k jednej z nich.

``IfcRelReferencedInSpatialStructure``
    „Kam prvok patrí okrem toho." *„Any element can be referenced to zero,
    one or several levels of the spatial structure … not restricted to be
    hierarchical."* Toto je schémou určená odpoveď na druhú miestnosť za
    dverami a na stĺp, ktorý stojí v priečke medzi dvomi miestnosťami.

``IfcRelSpaceBoundary``
    „Čo miestnosť uzatvára", pohľadom z miestnosti. Založené vo fáze 6b.

Rozhodnutie 24 z ``AUDIT.md`` znelo „dvere a steny do miestností nie, lebo
kontajnment je exkluzívny". Exkluzivita platí, ale záver z nej nevyplýva:
schéma sa pýta na primárnu miestnosť, nie na žiadnu. Rozhodnutie sa preto
mení — viď ``AUDIT.md`` §40 a ``BEP_ANNEX.md`` §2.7.

Ako sa určí miestnosť
---------------------
**Dvere.** Krídlo nie je vnútri žiadneho priestoru, sedí v otvore steny.
Sonda preto strieľa body po **normále dverí** — podľa spec je to +Y ich
`ObjectPlacement` (*„the door opening direction (by the positive y-axis of
the ObjectPlacement)"*) — na obe strany, 0.3/0.6/0.9 m, vo výške 1 m nad
prahom. Primárna je **obsluhovaná** miestnosť: z nájdených sa vyhodia
komunikačné priestory (chodba, schodisko, CHÚC, lobby, openspace) a zvyšok
sa uprednostní. Zvyšné miestnosti dostanú referenciu.

To je presne Samuelovo zadanie: *„nemusia byť priradené ku chodbe, ale do
tej priamej miestnosti áno."*

**Stĺpy.** Obal `IfcSpace` je okolo stĺpa **vykrojený**, takže stred stĺpa
nie je v žiadnom priestore a test bodom vnútri nefunguje. Sonda preto
obchádza stĺp po obvode. Stĺp obklopený **jedinou** miestnosťou v nej
stojí a je do nej kontajnovaný; stĺp na rozhraní ostáva v podlaží — ktorá
z dvoch miestností by to mala byť, sa nedá povedať — a dostane referenciu
na obe. Sedemnásť z 52 stĺpov je na rozhraní; keby sa kontajnment vynútil,
tá tretina by bola vymyslená.

**Podlahové vpuste.** Fáza 6a ich hľadala testom „ťažisko v obale
priestoru", lenže vpusť sedí v skladbe podlahy, teda **pod** obalom, a tak
jej test nikdy nevyjde. Tie, ktoré preto zostali na podlaží, sa dohľadajú
sondou **nahor**: vpusť patrí miestnosti, ktorej podlahu odvodňuje. Obe,
ktoré sa takto našli, sú technické miestnosti — presne kde podlahová vpusť
býva.

Pasce
-----
* agregované dvere (v LOP) sa **ne**kontajnujú — do štruktúry ich viaže
  celok (invariant 7). Referenciu dostať smú, tá hierarchická nie je;
* ``IfcRelContainedInSpatialStructure`` je pre prvok jediný — presun je
  odobratie zo starého a pridanie do nového;
* referencia na priestor, v ktorom je prvok kontajnovaný, je nadbytočná
  rovnako ako pri podlaží (fáza 19, oddiel C);
* `IfcSpace` nie je `IfcBuildingStorey` — po presune do priestoru sa prvok
  v strome objaví o úroveň nižšie, nie na inom podlaží. Kontroluje sa to.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

import numpy as np
import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.placement

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import detach_from_containment  # noqa: E402
import spatial  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v26.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v27.ifc")

DRY_RUN = True

#: komunikačné priestory — nie sú cieľom cesty, len ňou vedú. Zoznam je
#: z `LongName`, teda z názvoslovia projektanta, nie z odhadu.
CIRCULATION = re.compile(
    r"chodba|schodisk|ch[úu]c|lobby|openspace|predsie|z[áa]dver",
    re.IGNORECASE)

#: ako ďaleko od dverí sa hľadá miestnosť (mm)
DOOR_PROBE = (300.0, 600.0, 900.0)

#: v akej výške nad spodkom dverí sa sonduje (mm)
DOOR_HEIGHT = 1000.0

#: odstup sondy od plášťa stĺpa (mm)
COLUMN_PROBE = 150.0

#: v akých podieloch výšky stĺpa sa sonduje
COLUMN_LEVELS = (0.25, 0.5, 0.75)

#: koľko bodov na jednu stranu stĺpa
COLUMN_PER_SIDE = 3

#: ako vysoko nad vpusťou sa hľadá miestnosť, ktorej podlahu odvodňuje (mm)
DRAIN_PROBE = (300.0, 700.0, 1200.0)

#: ako ďaleko od skladby sa hľadá miestnosť, ktorej podlahu či podhľad
#: tvorí. Prvý krok je väčší než hrúbka nosnej dosky (250 mm) by dovolila
#: preskočiť — sonda ide **do** miestnosti, nie cez ňu.
COVERING_PROBE = (300.0, 700.0, 1200.0)


# --------------------------------------------------------------------------
# sondy
# --------------------------------------------------------------------------


def door_normal(door, b):
    """Jednotkový vodorovný smer naprieč dverami."""
    mat = ifcopenshell.util.placement.get_local_placement(door.ObjectPlacement)
    n = np.array(mat[:3, 1], dtype=float)
    n[2] = 0.0
    if np.linalg.norm(n) > 1e-6:
        return n / np.linalg.norm(n)
    # bez použiteľného umiestnenia rozhodne tenší pôdorysný rozmer
    return (np.array([1.0, 0.0, 0.0]) if (b[3] - b[0]) < (b[4] - b[1])
            else np.array([0.0, 1.0, 0.0]))


def spaces_at(pt, spaces, shp, sbox):
    return [s for s in spaces
            if s.GlobalId in shp
            and spatial.in_box(pt, sbox[s.GlobalId])
            and spatial.point_in_mesh(pt, shp[s.GlobalId])]


def door_sides(door, b, spaces, shp, sbox):
    """``{+1: [priestory], -1: [priestory]}`` po oboch stranách dverí."""
    n = door_normal(door, b)
    ctr = np.array([(b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0, b[2] + DOOR_HEIGHT])
    out = {}
    for sgn in (+1, -1):
        found = []
        for off in DOOR_PROBE:
            for s in spaces_at(ctr + sgn * off * n, spaces, shp, sbox):
                if s not in found:
                    found.append(s)
        out[sgn] = found
    return out


def around_column(col, b, spaces, shp, sbox):
    """Priestory obklopujúce stĺp. Obal priestoru je okolo stĺpa vykrojený."""
    found = []
    for lvl in COLUMN_LEVELS:
        z = b[2] + (b[5] - b[2]) * lvl
        for axis in (0, 1):
            lo, hi = (b[axis], b[axis + 3])
            for sgn in (+1, -1):
                edge = (hi + COLUMN_PROBE) if sgn > 0 else (lo - COLUMN_PROBE)
                other = 1 - axis
                a0, a1 = b[other], b[other + 3]
                for k in range(COLUMN_PER_SIDE):
                    t = (k + 0.5) / COLUMN_PER_SIDE
                    pos = a0 + (a1 - a0) * t
                    pt = ([edge, pos, z] if axis == 0 else [pos, edge, z])
                    for s in spaces_at(pt, spaces, shp, sbox):
                        if s not in found:
                            found.append(s)
    return found


def floor_area(space, sbox):
    """Plocha z ``Qto_SpaceBaseQuantities``, inak z pôdorysu obalu."""
    for r in (getattr(space, "IsDefinedBy", None) or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcElementQuantity"):
                for q in (d.Quantities or ()):
                    if q.is_a("IfcQuantityArea") and q.Name in ("NetFloorArea",
                                                                "GrossFloorArea"):
                        return float(q.AreaValue)
    b = sbox.get(space.GlobalId)
    return spatial.xy_area(b) / 1e6 if b else float("inf")


def served(spaces, sbox):
    """Obsluhovaná miestnosť: komunikačné ustúpia, potom rozhodne plocha."""
    if not spaces:
        return None
    rooms = [s for s in spaces if not CIRCULATION.search(s.LongName or s.Name or "")]
    pool = rooms or spaces
    return min(pool, key=lambda s: (floor_area(s, sbox), s.Name or ""))


def is_external(e):
    """`IsExternal` z occurrence, inak z typu, inak ``None``."""
    for r in (getattr(e, "IsDefinedBy", None) or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcPropertySet"):
                for p in (d.HasProperties or ()):
                    if p.Name == "IsExternal" and p.is_a("IfcPropertySingleValue"):
                        return bool(p.NominalValue.wrappedValue)
    t = getattr(e, "IsTypedBy", None)
    if t:
        for p in (t[0].RelatingType.HasPropertySets or ()):
            if p.is_a("IfcPropertySet"):
                for q in (p.HasProperties or ()):
                    if q.Name == "IsExternal" and q.is_a("IfcPropertySingleValue"):
                        return bool(q.NominalValue.wrappedValue)
    return None


# --------------------------------------------------------------------------
# väzby
# --------------------------------------------------------------------------


def bind(m, element, primary, extra, added, removed, log_moves):
    """Kontajnment na ``primary`` (ak smie), referencie na ``extra``."""
    cur = spatial.container_of(element)
    if primary is not None and not getattr(element, "Decomposes", None):
        if cur is None or cur.id() != primary.id():
            detach_from_containment(m, element, removed)
            spatial.contain_in(m, primary, element, added)
            log_moves[(cur.is_a().replace("Ifc", "") if cur else "?",
                       primary.is_a().replace("Ifc", ""))] += 1
    have = {x.id() for x in spatial.references_of(element)}
    keep = {s.id() for s in extra}
    for s in extra:
        if s.id() not in have:
            spatial.reference_in(m, s, element, added)
    # referencia na vlastný kontajner alebo na priestor, ktorý sa už netýka
    cur = spatial.container_of(element)
    for s in spatial.references_of(element):
        if not s.is_a("IfcSpace"):
            continue
        if s.id() not in keep or (cur is not None and cur.id() == s.id()):
            spatial.drop_reference(m, s, element, removed)


# ==========================================================================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--show", action="store_true", help="vypíše rozpis po prvkoch")
    args = ap.parse_args()
    dry = DRY_RUN and not args.apply

    print("vstup :", args.src)
    print("výstup:", args.dst, "(DRY-RUN)" if dry else "")
    print()

    m = ifcopenshell.open(args.src)
    added: list[str] = []
    removed: list[str] = []
    owner = (m.by_type("IfcOwnerHistory") or [None])[0]

    spaces = list(m.by_type("IfcSpace"))
    doors = list(m.by_type("IfcDoor"))
    cols = list(m.by_type("IfcColumn"))
    drains = [e for e in m.by_type("IfcFlowTerminal")
              if getattr(e, "PredefinedType", None) == "GULLYTRAP"]
    shp = spatial.shapes(m, spaces + doors + cols + drains)
    box = {g: spatial.bbox_of(v) for g, v in shp.items()}
    moves: collections.Counter = collections.Counter()

    # ---- A · dvere -------------------------------------------------------
    print("A · DVERE — miestnosť, do ktorej sa vstupuje")
    stat: collections.Counter = collections.Counter()
    rows = []
    for d in doors:
        b = box.get(d.GlobalId)
        if b is None:
            stat["bez tvaru"] += 1
            continue
        sides = door_sides(d, b, spaces, shp, box)
        cand = list(dict.fromkeys(sides[+1] + sides[-1]))
        primary = served(cand, box)
        extra = [s for s in cand if primary is None or s.id() != primary.id()]
        agg = bool(getattr(d, "Decomposes", None))
        if primary is None:
            stat["bez priestoru — ostáva na podlaží"] += 1
        elif agg:
            stat["agregované v LOP — len referencia"] += 1
        else:
            stat["kontajnment do miestnosti"] += 1
        refs = ([primary] + extra if agg and primary is not None else
                extra if not agg else extra)
        bind(m, d, None if agg else primary, refs, added, removed, moves)
        rows.append((d.Name, agg, primary, extra))
    for k, n in sorted(stat.items(), key=lambda kv: -kv[1]):
        print("    %-40s %3d" % (k, n))
    if args.show:
        for name, agg, primary, extra in sorted(rows):
            print("      %-16s %-6s → %-6s  aj %s"
                  % (name, "LOP" if agg else "",
                     primary.Name if primary else "—",
                     ",".join(s.Name for s in extra) or "—"))

    # ---- B · stĺpy -------------------------------------------------------
    print()
    print("B · STĹPY — stojí v jednej miestnosti, alebo na rozhraní")
    cstat: collections.Counter = collections.Counter()
    crows = []
    for c in cols:
        b = box.get(c.GlobalId)
        if b is None:
            cstat["bez tvaru"] += 1
            continue
        near = around_column(c, b, spaces, shp, box)
        one = near[0] if len(near) == 1 else None
        cstat["v jednej miestnosti → kontajnment" if one is not None
              else ("na rozhraní %d miestností → referencie" % len(near)) if near
              else "mimo miestností — ostáva na podlaží"] += 1
        bind(m, c, one, near if one is None else [], added, removed, moves)
        crows.append((c.Name, one, near))
    for k, n in sorted(cstat.items(), key=lambda kv: -kv[1]):
        print("    %-40s %3d" % (k, n))
    if args.show:
        for name, one, near in sorted(crows):
            print("      %-16s → %-6s  okolo %s"
                  % (name, one.Name if one else "podlažie",
                     ",".join(s.Name for s in near) or "—"))

    # ---- C · podlahové vpuste v skladbe podlahy --------------------------
    print()
    print("C · PODLAHOVÉ VPUSTE, ktoré fáza 6a nenašla")
    strays = [d for d in drains
              if spatial.container_of(d) is not None
              and spatial.container_of(d).is_a("IfcBuildingStorey")]
    for d in strays:
        b = box.get(d.GlobalId)
        if b is None:
            continue
        # vpusť odvodňuje podlahu miestnosti nad sebou; jej vlastné telo je
        # v skladbe, teda pod obalom priestoru, preto sonda ide nahor
        ctr = spatial.centre(b)
        target = None
        for off in DRAIN_PROBE:
            hits = spaces_at((ctr[0], ctr[1], b[5] + off), spaces, shp, box)
            if hits:
                target = hits[0]
                break
        if target is not None:
            print("    %-16s odvodňuje podlahu → %s (%s)"
                  % (d.Name, target.Name, target.LongName or ""))
            bind(m, d, target, [], added, removed, moves)
        else:
            print("    %-16s nad sebou nemá miestnosť — ostáva na podlaží" % d.Name)
    if not strays:
        print("    žiadna — všetky sú v miestnostiach")

    # ---- D · podlahy a podhľady k správnej miestnosti --------------------
    # Fáza 6a hľadala priľahlú miestnosť s toleranciou 300 mm na obe strany,
    # lenže nosná doska má 250 mm — tolerancia ju **preskočila** a skladba
    # podlahy 3NP sa dala miestnosti pod ňou ako podhľad. Smer určuje
    # `PredefinedType`, teda schéma, nie odhad: `FLOORING` patrí miestnosti
    # nad sebou, `CEILING` miestnosti pod sebou.
    print()
    print("D · PODLAHY A PODHĽADY — smer podľa PredefinedType")
    layers = [e for e in m.by_type("IfcCovering")
              if getattr(e, "PredefinedType", None) in ("FLOORING", "CEILING")
              and not getattr(e, "Decomposes", None)]
    lshp = spatial.shapes(m, layers)
    lbox = {g: spatial.bbox_of(v) for g, v in lshp.items()}
    lstat: collections.Counter = collections.Counter()
    for e in layers:
        b = lbox.get(e.GlobalId)
        if b is None:
            lstat["bez tvaru"] += 1
            continue
        up = e.PredefinedType == "FLOORING"
        target = None
        for off in COVERING_PROBE:
            z = (b[5] + off) if up else (b[2] - off)
            hits = spaces_at((*spatial.centre(b)[:2], z), spaces, shp, box)
            if hits:
                target = hits[0]
                break
        cur = spatial.container_of(e)
        if target is None:
            print("    %-16s %-8s %-8s → miestnosť sa nenašla, ostáva"
                  % (e.Name, e.PredefinedType,
                     cur.Name if cur is not None else "—"))
            lstat["%s · miestnosť sa nenašla" % e.PredefinedType] += 1
            continue
        if cur is not None and cur.id() == target.id():
            lstat["%s · sedí" % e.PredefinedType] += 1
            continue
        print("    %-16s %-8s %-8s → %s (%s)"
              % (e.Name, e.PredefinedType,
                 cur.Name if cur is not None else "—", target.Name,
                 target.LongName or ""))
        bind(m, e, target, [], added, removed, moves)
        lstat["%s · presunuté" % e.PredefinedType] += 1
    for k, n in sorted(lstat.items()):
        print("    %-40s %3d" % (k, n))

    # ---- E · chýbajúce hranice priestorov pre dvere ----------------------
    print()
    print("E · HRANICE PRIESTOROV pre dvere, ktoré lúč fázy 6b minul")
    have = {(r.RelatingSpace.id(), r.RelatedBuildingElement.id())
            for r in m.by_type("IfcRelSpaceBoundary")
            if r.RelatedBuildingElement is not None}
    novych = 0
    made = collections.Counter()
    for name, agg, primary, extra in rows:
        d = next(x for x in doors if x.Name == name)
        for s in ([primary] if primary is not None else []) + list(extra):
            if (s.id(), d.id()) in have:
                continue
            ext = is_external(d)
            rel = m.create_entity(
                "IfcRelSpaceBoundary1stLevel",
                GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                Name="%s / %s" % (s.Name, d.Name),
                RelatingSpace=s, RelatedBuildingElement=d,
                ConnectionGeometry=None,
                PhysicalOrVirtualBoundary="PHYSICAL",
                InternalOrExternalBoundary=("EXTERNAL" if ext else
                                            "INTERNAL" if ext is False else "NOTDEFINED"))
            added.append(rel.GlobalId)
            have.add((s.id(), d.id()))
            made[rel.InternalOrExternalBoundary] += 1
            novych += 1
    print("    nových IfcRelSpaceBoundary1stLevel: %d %s"
          % (novych, dict(made) if made else ""))
    bez = [d.Name for d in doors
           if not (getattr(d, "BoundedBy", None) or ())
           and not any(r.RelatedBuildingElement is not None
                       and r.RelatedBuildingElement.id() == d.id()
                       for r in m.by_type("IfcRelSpaceBoundary"))]
    print("    dverí bez jedinej hranice: %d %s" % (len(bez), bez[:8] if bez else ""))

    # ---- kontroly --------------------------------------------------------
    print()
    print("KONTROLY")
    if moves:
        print("  presuny kontajnmentu: %s" % {"%s → %s" % k: v for k, v in moves.items()})

    bad = [e for e in m.by_type("IfcObjectDefinition")
           if getattr(e, "Decomposes", None) and getattr(e, "ContainedInStructure", None)]
    if bad:
        raise SystemExit("STOP: invariant 7 porušený na %d prvkoch — %s"
                         % (len(bad), [e.Name for e in bad][:6]))
    print("  inv 7 · dvojitá väzba: 0")

    # presun do priestoru nesmie prvok preniesť na iné podlažie
    zones = spatial.storey_zones(m)
    slipped = []
    for e in doors + cols + drains:
        cur = spatial.container_of(e)
        b = box.get(e.GlobalId)
        if cur is None or b is None:
            continue
        st = spatial.storey_of(cur)
        if st is None or spatial.zone_share(b, zones[st]) < 0.5:
            slipped.append((e.Name, cur.Name, st.Name if st else "-"))
    if slipped:
        for n, c, s in slipped[:10]:
            print("     %-16s v %-6s → podlažie %s" % (n, c, s))
        raise SystemExit("STOP: %d prvkov skončilo mimo pásma svojho podlažia"
                         % len(slipped))
    print("  prvky ostali vo svojom podlaží: %d" % len(doors + cols + drains))

    dup = [(e.Name, s.Name) for e in doors + cols + drains
           for s in spatial.references_of(e)
           if spatial.container_of(e) is not None
           and spatial.container_of(e).id() == s.id()]
    if dup:
        raise SystemExit("STOP: %d referencií na vlastný kontajner — %s"
                         % (len(dup), dup[:5]))
    print("  referencií na vlastný kontajner: 0")

    per = collections.Counter()
    for e in doors + cols:
        cur = spatial.container_of(e)
        per[e.is_a().replace("Ifc", ""),
            "priestor" if cur is not None and cur.is_a("IfcSpace")
            else "podlažie" if cur is not None else "žiadny"] += 1
    print("  kontajner po behu: %s" % {"%s/%s" % k: v for k, v in sorted(per.items())})

    print("\n  GlobalId nových: %d, zrušených: %d" % (len(added), len(removed)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed)), "added": sorted(set(added))},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
