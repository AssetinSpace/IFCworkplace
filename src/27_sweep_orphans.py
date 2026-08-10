"""Fáza 9b — zametanie osirelých entít (#F).

    python src/27_sweep_orphans.py           # dry-run
    python src/27_sweep_orphans.py --apply   # zapíše out/ASR_v15.ifc

Čo robí
-------
Zmaže entity, na ktoré v súbore nič neodkazuje. Register #F ich eviduje
48: 31 `IfcLocalPlacement`, 11 `IfcRectangleProfileDef`,
5 `IfcArbitraryClosedProfileDef`, 1 `IfcSurfaceStyle`. Sú vo vstupe od
začiatku a všetky fázy 1–10 ich nechali tak.

Kaskáda
-------
Osirelý `IfcLocalPlacement` drží `IfcAxis2Placement3D`, ten body a smery.
Po zmazaní placementu osirejú aj tie, takže sa zametá **v kolách**, kým
sa niečo maže. Zdieľané entity prežijú samy — po každom kole sa počet
inverzov ráta nanovo, takže bod používaný iným placementom sa nezmaže.
Preto je zmazaných viac než 48; 48 je počet **koreňov**.

Whitelist
---------
Rovnaký ako v invariante 4. `IfcRepresentationContext` je v ňom zámerne
(#AY): subkontext visí na rodičovi **dopredným** `ParentContext`, takže
inverzov má vždy 0, aj keď je riadnou súčasťou stromu projektu.
Nepoužitý Revit subkontext „Box" tým v modeli zostáva.

Pasce
-----
Atribúty sa čítajú **pred** `model.remove()` a nikdy sa nesiaha na
handle po zmazaní — čítanie zo zmazanej entity proces zhodí, nevyhodí
výnimku (viď `ifcutil`).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_invariants import ORPHAN_WHITELIST  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v14.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v15.ifc")
BASELINE = os.path.join(ROOT, "tests", "known_baseline.json")

DRY_RUN = True


def orphans(model):
    """``[id]`` entít bez inverzov, mimo whitelistu."""
    out = []
    for e in model:
        if model.get_total_inverses(e):
            continue
        if any(e.is_a(w) for w in ORPHAN_WHITELIST):
            continue
        out.append(e.id())
    return out


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

    korene = orphans(m)
    rozpad = collections.Counter(m.by_id(i).is_a() for i in korene)
    print("KORENE")
    if not korene:
        print("  #F   žiadne osirelé entity — preskočené (idempotentné)")
        if dry:
            print("\nDRY-RUN — nič sa nezapísalo.")
            return 0
        m.write(args.dst)
        with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
            json.dump({"removed": [], "added": []}, fh, ensure_ascii=False, indent=2)
        print("\nzapísané:", args.dst)
        return 0

    for k, v in sorted(rozpad.items()):
        print("  %5d  %s" % (v, k))

    # porovnanie s registrom — nesmie sa nič neočakávane pridať
    with open(BASELINE, encoding="utf-8") as fh:
        ocakavane = json.load(fh)["F"]
    if dict(rozpad) != ocakavane["rozpad"]:
        raise SystemExit("STOP: rozpad %s nesedí s registrom #F %s"
                         % (dict(rozpad), ocakavane["rozpad"]))
    print("  rozpad sedí s registrom #F (%d koreňov)" % ocakavane["pocet"])

    # ---- zametanie v kolách ---------------------------------------------
    zmazane = collections.Counter()
    removed_guids: list[str] = []
    kolo = 0
    while True:
        ids = orphans(m)
        if not ids:
            break
        kolo += 1
        for i in ids:
            e = m.by_id(i)
            gid = getattr(e, "GlobalId", None)     # čítať PRED remove
            trieda = e.is_a()
            if isinstance(gid, str):
                removed_guids.append(gid)
            zmazane[trieda] += 1
            m.remove(e)
        if kolo > 50:
            raise SystemExit("STOP: zametanie sa nezastavilo po 50 kolách")

    print("\nZMENY")
    print("  #F   zametené v %d kolách, spolu %d entít" % (kolo, sum(zmazane.values())))
    for k, v in sorted(zmazane.items(), key=lambda x: -x[1]):
        print("        %5d  %s" % (v, k))

    zvysok = orphans(m)
    if zvysok:
        raise SystemExit("STOP: po zametaní zostalo %d osirelých" % len(zvysok))
    print("  #F   po zametaní: 0 osirelých entít")
    print("  GlobalId zrušených: %d" % len(removed_guids))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed_guids)), "added": []},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
