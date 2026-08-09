"""Tabuľka „pred → po" pre každý dotknutý SNIM kód.

    python src/report_diff.py out/ASR_final_v2.ifc out/ASR_v3.ifc
"""

from __future__ import annotations

import argparse
import collections

import ifcopenshell


def snapshot(path):
    """``{(kód, 'occ'|'typ'): Counter((trieda, PredefinedType))}``"""
    m = ifcopenshell.open(path)
    out = collections.defaultdict(collections.Counter)
    for e in m.by_type("IfcObjectDefinition"):
        if e.is_a("IfcFeatureElement") or not getattr(e, "Name", None):
            continue
        if e.is_a("IfcSpatialElement") or e.is_a("IfcProject"):
            continue
        kind = "typ" if e.is_a("IfcTypeObject") else "occ"
        out[(e.Name, kind)][(e.is_a(), getattr(e, "PredefinedType", None))] += 1
    return out


def fmt(counter):
    return ", ".join("%s/%s×%d" % (k[0].replace("Ifc", ""), k[1], v)
                     for k, v in sorted(counter.items()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    args = ap.parse_args()

    a, b = snapshot(args.before), snapshot(args.after)
    keys = sorted(set(a) | set(b))

    rows = []
    for k in keys:
        if a.get(k) != b.get(k):
            rows.append((k[0], k[1],
                         fmt(a[k]) if k in a else "—",
                         fmt(b[k]) if k in b else "—"))
    if not rows:
        print("žiadny kód sa nezmenil")
        return 0

    w0 = max(len(r[0]) for r in rows)
    w2 = max(len(r[2]) for r in rows)
    print("%-*s  %-3s  %-*s  →  %s" % (w0, "kód", "čo", w2, "pred", "po"))
    print("-" * (w0 + w2 + 40))
    for r in rows:
        print("%-*s  %-3s  %-*s  →  %s" % (w0, r[0], r[1], w2, r[2], r[3]))
    print("\ndotknutých kódov: %d" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
