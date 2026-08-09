"""Fáza 5a — identita typov (#AF).

    python src/19_fix_type_names.py           # dry-run
    python src/19_fix_type_names.py --apply   # zapíše out/ASR_v7.ifc

Čo robí
-------
A  zlúči rovnomenné typy, ktoré sú **naozaj ten istý výrobok**
B  premenuje typ tak, aby sa volal podľa SNIM kódu svojich occurrences

Čo NEROBÍ a prečo
-----------------
Rovnomenný typ **nie je** sám o sebe vada. Podľa rozhodnutia Samuela
(fáza 4) SNIM kód nesie **užitie**, nie výrobok — takže dva rôzne výrobky
pod jedným kódom sú legitímne a zlúčiť sa nesmú:

===========  =========================================  ==========
kód          dôvod, prečo sú to rôzne výrobky           typov
===========  =========================================  ==========
``DD01.02``  dvojkrídlové vs jednokrídlové              2
``DD02.03``  dvojkrídlové vs jednokrídlové              2
``DD03.03``  dvojkrídlové vs jednokrídlové              2
``DD04.03``  dvojkrídlové vs jednokrídlové              2
``DD01.06``  dva ``Exteriér_Retail`` s inou geometriou
             (4 vs 1 ``RepresentationMap``) + ``Chodba``  3
===========  =========================================  ==========

Zlučujú sa len 4 dvojice ``IfcCoveringType`` — ``ST01.10a``, ``ST01.20``,
``ST01.21``, ``ST01.31``. Tie vznikli **vo fáze 1**: ten istý výrobok bol
v modeli raz ako ``IfcRoof`` a raz ako ``IfcSlab``, a prekvalifikovanie
z nich spravilo dva rovnaké ``IfcCoveringType``. Zhodujú sa v triede,
popise, ``PredefinedType`` aj materiáli a žiadny nemá ``RepresentationMap``.

``DD01.05`` → ``DD01.04`` je nedotiahnutý koniec #AP: fáza 4 premenovala
occurrences sklenených dvojkrídlových dverí na ``DD01.04.01/.02``, ale ich
typ ostal ``DD01.05``. Typ sa má volať podľa kódu svojich occurrences.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ifcutil import merge_types, sweep_orphans  # noqa: E402
from tests.test_invariants import parse_snim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v6.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v7.ifc")

DRY_RUN = True


def material_fingerprint(t):
    """Porovnateľný odtlačok materiálu typu."""
    for r in (t.HasAssociations or ()):
        if not r.is_a("IfcRelAssociatesMaterial"):
            continue
        mm = r.RelatingMaterial
        if mm.is_a("IfcMaterialLayerSet"):
            return ("LayerSet", tuple((l.Material.Name, l.LayerThickness)
                                      for l in mm.MaterialLayers))
        if mm.is_a("IfcMaterialConstituentSet"):
            return ("ConstituentSet",
                    tuple(sorted((c.Name, c.Material.Name)
                                 for c in mm.MaterialConstituents)))
        return (mm.is_a(), getattr(mm, "Name", None))
    return None


def is_same_product(types) -> bool:
    """Sú to naozaj rovnaké výrobky, alebo len rovnaké mená?"""
    keys = {(t.is_a(), t.Description, t.PredefinedType,
             len(t.RepresentationMaps or ()), material_fingerprint(t))
            for t in types}
    return len(keys) == 1


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
    n_before = len(m.by_type("IfcTypeObject"))
    removed: list[str] = []
    added: list[str] = []
    cand: list = []
    dead: set = set()
    log: list[str] = []

    # ---- A · zlúčiť len skutočné duplikáty ------------------------------
    groups = collections.defaultdict(list)
    for t in m.by_type("IfcTypeObject"):
        groups[t.Name].append(t)

    kept = []
    for name in sorted(groups):
        ts = groups[name]
        if len(ts) < 2:
            continue
        if is_same_product(ts):
            merge_types(m, ts, name, removed, cand, dead, log, "#AF")
        else:
            kept.append((name, len(ts)))

    # ---- B · #AP nedotiahnutý koniec fázy 4 ------------------------------
    # Len tento jeden prípad: fáza 4 premenovala occurrences, typ ostal.
    # Všeobecné pravidlo „typ sa volá podľa kódu occurrences" sa NEROBÍ —
    # samo by vyrobilo nové duplicity: ST01.10a aj ST01.10b majú occurrences
    # ST01.10, a ZD02.03 má occurrences ZD02.02, kde už typ ZD02.02 existuje.
    renamed = []
    for t in list(m.by_type("IfcDoorType")):
        if t.Name != "DD01.05":
            continue
        occ = [o for r in t.Types for o in r.RelatedObjects]
        codes = {parse_snim(o.Name)[0] for o in occ}
        if codes == {"DD01.04"}:
            t.Name = "DD01.04"
            renamed.append(("DD01.05", "DD01.04", len(occ)))
    for old, new, n in renamed:
        log.append("#AP  typ %s → %s (%d occurrences)" % (old, new, n))

    # ---- ohlásiť ostatné nesúlady mena typu a kódu occurrences ----------
    mismatch = []
    for t in m.by_type("IfcTypeProduct"):
        occ = [o for r in t.Types for o in r.RelatedObjects]
        if not occ or not t.Name:
            continue
        codes = {parse_snim(o.Name)[0] for o in occ}
        if len(codes) == 1:
            code = codes.pop()
            if code and code != t.Name:
                mismatch.append((t.Name, code, len(occ)))

    swept = sweep_orphans(m, cand, removed, dead)
    if swept:
        log.append("     zametené osirelé entity: %s" % dict(swept))

    # ---- kontrola --------------------------------------------------------
    groups = collections.defaultdict(list)
    for t in m.by_type("IfcTypeObject"):
        groups[t.Name].append(t)
    still = {k: len(v) for k, v in groups.items() if len(v) > 1}

    print("ZMENY")
    for line in log:
        print("  " + line)
    if not log:
        print("  (žiadna zmena — model je už v cieľovom stave)")
    print("\nKONTROLA")
    print("  IfcTypeObject : %d → %d" % (n_before, len(m.by_type("IfcTypeObject"))))
    print("  rovnomenné skupiny, ktoré ostávajú zámerne: %d %s"
          % (len(still), still))
    print("  (rôzne výrobky pod jedným kódom — kód nesie užitie, nie výrobok)")
    if mismatch:
        print("\n  NEOPRAVENÉ — meno typu sa nezhoduje s kódom occurrences (%d):"
              % len(mismatch))
        for old, new, n in sorted(mismatch):
            print("     typ %-10s occurrences %-10s ×%d" % (old, new, n))
        print("     Zmena by vyrobila nové duplicity, treba rozhodnutie.")
    print("  GlobalId zrušených: %d, nových: %d" % (len(removed), len(added)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(removed), "added": sorted(added)},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
