"""Spustí invarianty proti súboru a vypíše brány.

    python src/gate.py out/ASR_final_v2.ifc [--skip 1,2] [--allow GID,GID]
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_invariants import (  # noqa: E402
    REFERENCE,
    known_baseline,
    inv1_geometry,
    inv2_express,
    inv3_guid_accounting,
    inv4_orphans,
    inv5_empty_sets,
    inv6_uniqueness,
    inv7_containment_vs_aggregation,
    inv8_spatial_fit,
)
import ifcopenshell  # noqa: E402

NAMES = {
    1: "geometria",
    2: "EXPRESS",
    3: "GUID účtovníctvo",
    4: "osirelé entity",
    5: "prázdne povinné SET",
    6: "jednoznačnosť",
    7: "kontajnment vs agregácia",
    8: "priestorové zaradenie",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("subject")
    ap.add_argument("--reference", default=REFERENCE)
    ap.add_argument("--skip", default="")
    ap.add_argument("--allow", default="")
    ap.add_argument("--known", default="",
                    help="položky registra zo známych vád základne, napr. AW")
    ap.add_argument("--allow-file", action="append", default=[],
                    help="JSON s {'removed': [...], 'added': [...]} od skriptu kroku. "
                         "Dá sa uviesť viackrát — allowlisty sa zlúčia. Reťazová "
                         "kontrola proti data/ASR.ifc potrebuje základňu "
                         "tests/allowlist_prepipeline.json aj out/ASR_v*.allowlist.json")
    ap.add_argument("--show", type=int, default=8)
    args = ap.parse_args()

    skip = {int(x) for x in args.skip.split(",") if x.strip()}
    allow = {x for x in args.allow.split(",") if x.strip()}
    known = [k.strip() for k in args.known.split(",") if k.strip()]
    if known:
        allow |= known_baseline(*known)
    if args.allow_file:
        import json
        for path in args.allow_file:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            allow |= set(d.get("removed", [])) | set(d.get("added", []))

    print("subject   :", args.subject)
    print("reference :", args.reference,
          "" if os.path.exists(args.reference) else "  ← CHÝBA")
    print("allowlist :", len(allow), "GlobalId",
          ("(známe vady: %s)" % ", ".join(known)) if known else "")
    print()

    results: dict[int, list] = {}

    if 1 in skip:
        pass
    elif not os.path.exists(args.reference):
        results[1] = None  # nedá sa spustiť
    else:
        results[1] = inv1_geometry(args.subject, args.reference, allow)

    if 2 not in skip:
        results[2] = inv2_express(args.subject, allow)

    model = ifcopenshell.open(args.subject)
    ref = args.reference if os.path.exists(args.reference) else None
    if 3 not in skip:
        results[3] = inv3_guid_accounting(model, ref, allowlist=allow)
    if 4 not in skip:
        results[4] = inv4_orphans(model, allow)
    if 5 not in skip:
        results[5] = inv5_empty_sets(model, allow)
    if 6 not in skip:
        results[6] = inv6_uniqueness(model, allow)
    if 7 not in skip:
        results[7] = inv7_containment_vs_aggregation(model, allow)
    if 8 not in skip:
        results[8] = inv8_spatial_fit(args.subject, allow)

    failed = 0
    for n in sorted(results):
        v = results[n]
        if v is None:
            print("inv%d  %-26s NEDÁ SA SPUSTIŤ (chýba referencia)" % (n, NAMES[n]))
            failed += 1
            continue
        status = "OK" if not v else "ZLYHAL — %d porušení" % len(v)
        print("inv%d  %-26s %s" % (n, NAMES[n], status))
        if v:
            failed += 1
            by_type = collections.Counter(x.entity for x in v)
            for k, c in by_type.most_common():
                print("        %5d  %s" % (c, k))
            for x in v[: args.show]:
                print("        ", x)
            if len(v) > args.show:
                print("         … a ďalších %d" % (len(v) - args.show))
    print()
    print("zlyhalo %d z %d" % (failed, len(results)))
    # Návratový kód musí zlyhanie ohlásiť, inak brána v CI nič nezastaví.
    # Známe vady sa nepúšťajú cez výnimku v kóde, ale cez `--known`
    # a `--allow-file` — teda menovite a viditeľne.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
