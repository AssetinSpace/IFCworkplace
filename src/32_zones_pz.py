"""Fáza 13 — #Q2: zóny `PZ01`–`PZ10` naviazané na priestory.

Register: #Q2. Rozhodnutie Samuela z 10. 8.: odvodiť **geometricky
aj logicky**.

    python src/32_zones_pz.py            # dry-run
    python src/32_zones_pz.py --apply    # zapíše out/ASR_v20.ifc

Čo robí
-------
Desať `IfcSpatialZone` má vlastné teleso a `PredefinedType = OCCUPANCY`,
ale `IfcRelReferencedInSpatialStructure` majú 0×. Prenajímateľnosť tak
dnes nesie iba objem, nie väzba na miestnosti. Skript väzbu doplní.

Opora v schéme
--------------
`IfcRelReferencedInSpatialStructure` má pravidlo `AllowedRelatedElements`,
ktoré vkladanie priestorových prvkov do priestorových prvkov zakazuje —
**s výslovnou výnimkou**: *„an IfcSpace can be referenced by another
spatial structure element, in particular by an IfcSpatialZone. IFC4-CHANGE
The relaxation to allow IfcSpace has been included."* Presne tento prípad.

Ako sa priraďuje
----------------
Nie bboxom. Pôdorys zóny aj priestoru sa zostaví ako **únia trojuholníkov
telesa premietnutých do XY** (shapely), a priestor patrí do zóny, ak

1. sa ich zvislé rozsahy prekrývajú aspoň o 1 mm, a
2. podiel plochy priestoru vnútri zóny je aspoň ``--prah`` (default 0.5).

Prečo nie bbox: `PZ01` má bbox celého pôdorysu budovy, ale skutočná plocha
je 611.54 m² — bboxom by pohltila aj `PZ03`, `PZ07`, `PZ08` a `PZ09`.

Prah je necitlivý: 0.3, 0.5 aj 0.7 dávajú **rovnakých 42 väzieb**, lebo
namerané podiely sú 0.84 až 1.00. Skript citlivosť vypíše, nech je to
vidieť, a **zastane**, ak ktorákoľvek zóna vyjde prázdna alebo ak by
priestor spadol do dvoch zón naraz.

Čo zostane nepriradené a prečo
------------------------------
Z 75 priestorov dostane zónu 42. Zvyšných 33 nie je chyba:

* **celé 3NP (22)** — `PZ01`–`PZ10` na kóte 3NP teleso nemajú vôbec.
  Prenajímateľné priestory 3NP nesie `IfcZone` „Nájomné priestory 3NP",
  ktorú založila fáza 5c (#Q). Tam je zdrojom legenda, nie geometria;
  §15;
* **služobné priestory 2NP (9)** — elektrorozvodňa, výťahová lobby,
  technická miestnosť, šachty a schodisko. `PZ10` sa volá „Nájomný
  priestor" a tie do nej nepatria;
* **šachty `1.25` a `4.05` (2)** — ležia mimo telies zón; obe už členmi
  šachtových `IfcZone` z fázy 5c.

Jedna nesúmernosť, ktorú treba vidieť
-------------------------------------
`2.19` je inštalačná šachta 0.75 m², ktorá **geometricky leží vnútri**
`PZ10` „Nájomný priestor" (podiel 1.00), takže ju skript priradí. Jej
náprotivok na 3NP (`3.18`) v zóne 3NP nie je, lebo tá vznikla z legendy,
kde šachty nie sú. Vzťah je „referenced in", nie „je prenajímateľná",
takže priradenie je vecne v poriadku — ale rozdiel oproti 3NP je
vedomý, nie prehliadnutý.

Pasce
-----
* shape z ``create_shape`` sa **drží v premennej** — inak numpy číta
  uvoľnenú pamäť (§31).
* zvislé steny dajú v priemete nulovú plochu; trojuholníky pod 1 mm²
  sa zahadzujú, inak `unary_union` spadne na degenerovaných polygónoch.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v19.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v20.ifc")

DRY_RUN = True
PRAH = 0.5
MIN_PREKRYV_Z = 1.0     # mm
MIN_TROJUHOLNIK = 1.0   # mm²


def footprint(settings, element):
    """Priemet telesa do XY ako shapely plocha + zvislý rozsah v mm."""
    shape = ifcopenshell.geom.create_shape(settings, element)
    v = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3) * 1000.0
    f = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
    del shape
    tris = []
    for a, b, c in f:
        p = Polygon([v[a][:2], v[b][:2], v[c][:2]])
        if p.is_valid and p.area > MIN_TROJUHOLNIK:
            tris.append(p)
    if not tris:
        return None, None
    return unary_union(tris), (float(v[:, 2].min()), float(v[:, 2].max()))


def storey_of(space):
    return space.Decomposes[0].RelatingObject.Name if space.Decomposes else "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--prah", type=float, default=PRAH)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY")
    print("prah  :", args.prah, "\n")

    zones = []
    for z in sorted(model.by_type("IfcSpatialZone"), key=lambda x: x.Name or ""):
        if not z.Representation:
            continue
        poly, zr = footprint(settings, z)
        if poly is None:
            raise SystemExit("STOP: zóna %r nemá použiteľný pôdorys" % z.Name)
        zones.append((z, poly, zr))
    if not zones:
        raise SystemExit("STOP: v modeli nie je ani jedna IfcSpatialZone s telesom")

    spaces = []
    for s in model.by_type("IfcSpace"):
        if not s.Representation:
            continue
        poly, sr = footprint(settings, s)
        if poly is None or poly.area < MIN_TROJUHOLNIK:
            continue
        spaces.append((s, poly, sr))

    # --- priradenie --------------------------------------------------------
    podiely: dict[str, list] = collections.defaultdict(list)
    for s, sp, sr in spaces:
        for z, zp, zr in zones:
            if min(sr[1], zr[1]) - max(sr[0], zr[0]) <= MIN_PREKRYV_Z:
                continue
            r = sp.intersection(zp).area / sp.area if sp.area else 0.0
            if r > 0.0:
                podiely[z.Name].append((s, r))

    prir: dict[str, list] = {}
    kde: dict[str, list] = collections.defaultdict(list)
    for zn, lst in podiely.items():
        vybrane = [(s, r) for s, r in lst if r >= args.prah]
        prir[zn] = vybrane
        for s, r in vybrane:
            kde[s.Name].append(zn)

    dvoj = {k: v for k, v in kde.items() if len(v) > 1}
    if dvoj:
        raise SystemExit("STOP: priestor v dvoch zónach naraz: %s" % dvoj)

    prazdne = [z.Name for z, _, _ in zones if not prir.get(z.Name)]
    if prazdne:
        raise SystemExit("STOP: zóny bez jediného priestoru: %s — "
                         "geometrický test zlyhal" % prazdne)

    # --- citlivosť prahu ---------------------------------------------------
    print("citlivosť prahu:")
    for p in (0.3, 0.5, 0.7, 0.9):
        n = sum(1 for lst in podiely.values() for _, r in lst if r >= p)
        print("    %.1f → %d väzieb" % (p, n))
    print()

    for z, _, _ in zones:
        lst = sorted(prir[z.Name], key=lambda x: x[0].Name or "")
        rmin = min(r for _, r in lst)
        print("  %-6s %-30s %2d priestorov, najmenší podiel %.2f"
              % (z.Name, z.LongName or "", len(lst), rmin))
        print("         " + ", ".join(s.Name for s, _ in lst))

    nepriradene = [s for s, _, _ in spaces if s.Name not in kde]
    po_podl = collections.Counter(storey_of(s) for s in nepriradene)
    print("\npriradených %d z %d priestorov; bez zóny %d %s"
          % (len(kde), len(spaces), len(nepriradene), dict(po_podl)))

    novych = sum(1 for z, _, _ in zones
                 if not (getattr(z, "ReferencesElements", None) or []))
    if novych == 0:
        print("\nIdempotencia: všetkých %d zón väzbu už má, niet čo robiť."
              % len(zones))
        return 0
    if novych != len(zones):
        raise SystemExit("STOP: %d z %d zón väzbu už má — model je "
                         "v polovičnom stave" % (len(zones) - novych, len(zones)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    # --- zápis -------------------------------------------------------------
    owner = model.by_type("IfcOwnerHistory")[0] if model.by_type("IfcOwnerHistory") else None
    nove_guid = []
    for z, _, _ in zones:
        rel = model.create_entity(
            "IfcRelReferencedInSpatialStructure",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=owner,
            Name="Priestory zóny %s" % z.Name,
            Description="Odvodené z geometrie, podiel plochy ≥ %.2f" % args.prah,
            RelatedElements=[s for s, _ in prir[z.Name]],
            RelatingStructure=z,
        )
        nove_guid.append(rel.GlobalId)

    model.write(args.dst)
    print("\nzapísané:", args.dst)

    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(nove_guid)}, fh, indent=2)
        fh.write("\n")
    print("allowlist : %d nových IfcRelReferencedInSpatialStructure" % len(nove_guid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
