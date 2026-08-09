"""#J — sonda: existuje šachta v modeli už teraz? (**nič nemení**)

    python src/probe_shafts.py                      # out/ASR_v8.ifc
    python src/probe_shafts.py --in out/ASR_v9.ifc

Otázka, na ktorú odpovedá
-------------------------
Samuel: „over, či tie šachty proste nepreliezajú až pod základy alebo úplne
hore nad strechu ako jeden priestor, ktorý oreže všetko — inak by tam diera
nebola, nejako tá šachta už teraz byť musí."

Odpoveď spec na tú intuíciu je, že „jedna šachta cez celý objekt" sa
nemodeluje ako jeden vysoký ``IfcSpace``, ale ako **zóna**, ktorá zoskupí
priestory po podlažiach. ``IfcZone`` (IFC4.3, §5.4.3.82) doslova:

    'ElevatorShaft': a collection of spaces within an elevator, potentially
                     going through many storeys.
    'RisingDuct':    A collection of vertical airspaces.

Sonda preto meria päť vecí:

A  Je v modeli ``IfcZone``/``IfcSpatialZone``, ktorá šachty drží pokope?
B  Je ``IfcSpace``, ktorý presahuje viac podlaží alebo nevisí na žiadnom?
C  Čo reže dieru v doskách — ``IfcFeatureElement`` nad pôdorysom šachty
   a jeho zvislý rozsah.
D  Zvislý stĺpec nad každým pôdorysom šachty: čo na ktorom podlaží je
   a kde je v rade diera.
E  Ako ďaleko siaha teleso existujúcich priestorov (slab-to-slab vs
   podlaha→podhľad). Spec to nemandátuje — je to vec MVD — takže nový
   priestor sa musí modelovať tak ako susedia, nie „podľa knihy".

Konvencie prevzaté z ``tests/test_invariants.py``: ``geom.iterator``
s multiprocessingom (nie opakovaný ``create_shape``), ``use-world-coords``,
a výsledok v **milimetroch** (``create_shape`` vracia metre, súbor je v mm).
"""

from __future__ import annotations

import argparse
import collections
import os
import re

import ifcopenshell
import ifcopenshell.geom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v8.ifc")

THREADS = max(1, (os.cpu_count() or 2) - 1)

#: priestory, ktoré považujeme za šachtu — podľa LongName
SHAFT_RE = re.compile(r"(?i)(šacht|sacht|shaft)")

#: hodnoty ObjectType, ktoré spec odporúča pre zvislé zoskupenia
SHAFT_OBJECTTYPES = ("elevatorshaft", "risingduct", "runningduct", "firecompartment")

#: prekryv pôdorysov, od ktorého ich považujeme za ten istý zvislý stĺpec
OVERLAP = 0.5

#: pôdorys pod touto plochou je prestup potrubia, nie šachta (mm²)
MIN_AREA = 100_000.0


# --------------------------------------------------------------------------
# pomôcky
# --------------------------------------------------------------------------


def storey_of(e):
    """Podlažie prvku — cez Decomposes (priestory) aj cez kontajnment."""
    for r in (getattr(e, "Decomposes", None) or ()):
        return r.RelatingObject
    for r in (getattr(e, "ContainedInStructure", None) or ()):
        return r.RelatingStructure
    return None


def host_of(feature):
    """Prvok, do ktorého je otvor vyrezaný."""
    for r in (getattr(feature, "VoidsElements", None) or ()):
        return r.RelatingBuildingElement
    return None


def bboxes(model, products):
    """``{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)}`` v milimetroch."""
    out = {}
    products = [p for p in products if p.Representation is not None]
    if not products:
        return out
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(st, model, THREADS, include=products)
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


def _inter(a, b):
    ix = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    iy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ix * iy


def _area(a):
    return (a[3] - a[0]) * (a[4] - a[1])


def xy_inside(a, b):
    """Prekryv voči **menšiemu** — „prechádza jeden druhým".

    Malá šachta vnorená do veľkého otvoru dá 1.0, preto sa týmto testom
    nesmú zlučovať stĺpce, len sa ním hľadá, čo daný pôdorys prerazí.
    """
    m = min(_area(a), _area(b))
    return (_inter(a, b) / m) if m > 0 else 0.0


def xy_similar(a, b):
    """Prekryv voči **väčšiemu** — „je to ten istý pôdorys".

    Vnorenie tu dá malé číslo, takže schodiskový otvor nepohltí šachtu,
    ktorá v ňom leží.
    """
    m = max(_area(a), _area(b))
    return (_inter(a, b) / m) if m > 0 else 0.0


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args()

    print("vstup :", args.src, "(sonda, nič sa nemení)\n")
    m = ifcopenshell.open(args.src)

    storeys = sorted(m.by_type("IfcBuildingStorey"),
                     key=lambda s: (s.Elevation if s.Elevation is not None else 0.0))
    print("PODLAŽIA")
    for s in storeys:
        print("   %-8s Elevation = %s" % (s.Name, s.Elevation))

    spaces = list(m.by_type("IfcSpace"))
    shafts = [s for s in spaces if SHAFT_RE.search(s.LongName or "")]
    print("\n   priestorov spolu %d, z toho podľa LongName šachiet %d"
          % (len(spaces), len(shafts)))

    # ---- A · drží šachty nejaká zóna? -----------------------------------
    print("\nA · ZÓNY")
    zones = list(m.by_type("IfcZone")) + list(m.by_type("IfcSpatialZone"))
    if not zones:
        print("   žiadna IfcZone ani IfcSpatialZone v modeli nie je")
    shaft_ids = {s.id() for s in shafts}
    for z in zones:
        members = []
        for r in (getattr(z, "IsGroupedBy", None) or ()):
            members.extend(r.RelatedObjects)
        hit = sum(1 for o in members if o.id() in shaft_ids)
        ot = (z.ObjectType or "")
        flag = "  ← ODPORÚČANÝ TYP" if ot.lower().replace(" ", "") in SHAFT_OBJECTTYPES else ""
        print("   %-16s Name=%-22r ObjectType=%-16r členov=%-4d z toho šachiet=%d%s"
              % (z.is_a(), z.Name, ot or None, len(members), hit, flag))

    # ---- B · viacpodlažné / bezdomové priestory --------------------------
    print("\nB · PRIESTORY MIMO JEDNÉHO PODLAŽIA")
    space_bb = bboxes(m, spaces)
    elevations = [s.Elevation for s in storeys if s.Elevation is not None]
    orphans = [s for s in spaces if storey_of(s) is None]
    multi = []
    for s in spaces:
        bb = space_bb.get(s.GlobalId)
        if not bb:
            continue
        crossed = [e for e in elevations if bb[2] + 1.0 < e < bb[5] - 1.0]
        if crossed:
            multi.append((s, bb, crossed))
    if orphans:
        print("   BEZ PODLAŽIA: %d" % len(orphans))
        for s in orphans[: args.show]:
            print("      %-10s %s" % (s.Name, s.LongName))
    if multi:
        print("   PRETÍNAJÚ ÚROVEŇ INÉHO PODLAŽIA: %d" % len(multi))
        for s, bb, cr in multi[: args.show]:
            print("      %-10s %-24s z %.0f…%.0f mm, pretína %s"
                  % (s.Name, s.LongName, bb[2], bb[5], cr))
    if not orphans and not multi:
        print("   žiadne — každý priestor sedí v jednom podlaží")

    # ---- C+D · zvislé stĺpce nad pôdorysmi šácht -------------------------
    print("\nC+D · ZVISLÉ STĹPCE NAD PÔDORYSMI ŠÁCHT")
    features = list(m.by_type("IfcFeatureElement"))
    feat_bb = bboxes(m, features)
    by_gid = {e.GlobalId: e for e in spaces + features}

    # Stĺpce sa nesmú hľadať len podľa priestorov — šachta, ktorá priestor
    # nemá na žiadnom podlaží, by tak zostala neviditeľná. Semienkom je preto
    # aj **zvislý otvor**: prerazí viac než jedno podlažie a jeho pôdorys je
    # presne pôdorysom šachty (overené, viď §14).
    span = (max(s.Elevation for s in storeys if s.Elevation is not None)
            - min(s.Elevation for s in storeys if s.Elevation is not None))
    seeds = [(s, space_bb[s.GlobalId]) for s in shafts if s.GlobalId in space_bb]
    drobne = 0
    for gid, fbb in feat_bb.items():
        if fbb[5] - fbb[2] <= span:         # neprerazí viac podlaží
            continue
        if _area(fbb) < MIN_AREA:           # prestupy potrubí, nie šachty
            drobne += 1
            continue
        seeds.append((by_gid[gid], fbb))
    if drobne:
        print("   (vynechaných %d zvislých prestupov pod %.2f m²)"
              % (drobne, MIN_AREA / 1e6))

    columns: list[list] = []
    for e, bb in sorted(seeds, key=lambda x: -_area(x[1])):
        for col in columns:
            if xy_similar(col[0][1], bb) >= OVERLAP:
                col.append((e, bb))
                break
        else:
            columns.append([(e, bb)])

    for n, col in enumerate(columns, 1):
        ref = col[0][1]
        w, d = ref[3] - ref[0], ref[4] - ref[1]
        print("\n   stĺpec %d — pôdorys %.0f × %.0f mm, %.2f m²"
              % (n, w, d, w * d / 1e6))
        cols_spaces = [(e, bb) for e, bb in col if e.is_a("IfcSpace")]
        cols_feats = [(e, bb) for e, bb in col if not e.is_a("IfcSpace")]

        have = set()
        for s, bb in sorted(cols_spaces, key=lambda x: x[1][2]):
            st = storey_of(s)
            have.add(st.Name if st else None)
            print("      priestor %-8s %-10s %-22s z %8.0f … %8.0f"
                  % (st.Name if st else "?", s.Name, s.LongName, bb[2], bb[5]))
        if not cols_spaces:
            print("      priestor NEEXISTUJE na žiadnom podlaží")
        chybajuce = [s.Name for s in storeys if s.Name not in have]
        if chybajuce and cols_spaces:
            print("      CHÝBA priestor na: %s" % ", ".join(chybajuce))

        # otvory, ktoré tento pôdorys prerážajú — kde a v čom
        hosts = collections.Counter()
        zr = set()
        for f, fbb in cols_feats:
            h = host_of(f)
            hs = storey_of(h) if h is not None else None
            hosts["%s %s (%s)" % (h.is_a().replace("Ifc", "") if h is not None else "?",
                                  h.Name if h is not None else None,
                                  hs.Name if hs is not None else "?")] += 1
            zr.add((fbb[2], fbb[5]))
        if cols_feats:
            print("      otvory: %d, zvislý rozsah %s"
                  % (len(cols_feats),
                     ", ".join("%.0f…%.0f" % z for z in sorted(zr))))
            for h, c in hosts.most_common(args.show):
                print("         %d× v %s" % (c, h))
        else:
            print("      otvory: žiadne — šachta neprerazí dosku")

    # ---- E · ako ďaleko siaha teleso priestoru ---------------------------
    print("\nE · ZVISLÝ ROZSAH TELIES PRIESTOROV")
    elev = {s.Name: s.Elevation for s in storeys}
    per = collections.defaultdict(list)
    for s in spaces:
        bb = space_bb.get(s.GlobalId)
        st = storey_of(s)
        if bb and st is not None and st.Elevation is not None:
            per[st.Name].append((bb[2] - st.Elevation, bb[5] - bb[2]))
    for name in sorted(per, key=lambda k: elev.get(k) or 0.0):
        vals = per[name]
        base = sorted(v[0] for v in vals)
        hgt = sorted(v[1] for v in vals)
        mid = len(vals) // 2
        print("   %-8s n=%-4d spodok nad úrovňou podlažia medián %6.0f mm,"
              " výška telesa medián %6.0f mm" % (name, len(vals), base[mid], hgt[mid]))

    print("\nHOTOVO — sonda nič nezapísala.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
