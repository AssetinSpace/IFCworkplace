"""Fáza 9a — číselný šum (#AJ).

    python src/26_fix_numeric.py           # dry-run
    python src/26_fix_numeric.py --apply   # zapíše out/ASR_v14.ifc

Čo robí
-------
Zaokrúhli hodnoty, ktoré nesú šum plávajúcej čiarky z exportu: `5000`
zapísané ako `4999.999999999999`, `161.2625` ako `161.2624999999994`.
Register uvádza 2653 takých hodnôt — 2502 v `Qto`, 145 v `Overall*`
a 18 v property.

Prečo 6 desatinných miest
-------------------------
Súbor má dĺžky v **milimetroch**, takže 6 desatinných miest je nanometer —
rádovo pod akoukoľvek stavebnou toleranciou aj pod presnosťou, s akou
model vznikol. Šum je pritom na úrovni `1e-12` relatívne, takže sa
zaokrúhlením odstráni celý a **žiadna skutočná hodnota sa nezmení**.
Skript navyše zastane, ak by niektorá zmena presiahla `TOL`.

Geometria sa nedotýka — `Qto`, `Overall*` ani property nie sú tvar, takže
invariant 1 nemá čo hlásiť.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v13.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v14.ifc")

DRY_RUN = True

NDIG = 6

#: väčšia zmena než toto by už nebola šum, ale prepisovanie dát
TOL = 1e-4

#: atribúty s hodnotou na množstvách
QTY_ATTRS = ("LengthValue", "AreaValue", "VolumeValue", "CountValue",
             "WeightValue", "TimeValue", "PerimeterValue")

#: atribúty prvkov, ktoré nesú rozmer mimo geometrie
OVERALL = {"IfcDoor": ("OverallHeight", "OverallWidth"),
           "IfcWindow": ("OverallHeight", "OverallWidth")}


def clean(v):
    """Vráti zaokrúhlenú hodnotu alebo ``None``, ak sa nič nemení."""
    if not isinstance(v, float):
        return None
    r = round(v, NDIG)
    if r == v:
        return None
    if abs(r - v) > TOL:
        raise SystemExit("STOP: %r → %r je zmena %.3g, to už nie je šum"
                         % (v, r, abs(r - v)))
    return r


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
    zmeny = collections.Counter()
    najvacsia = 0.0

    # ---- množstvá --------------------------------------------------------
    for q in m.by_type("IfcPhysicalSimpleQuantity"):
        for a in QTY_ATTRS:
            if not hasattr(q, a):
                continue
            v = getattr(q, a)
            r = clean(v)
            if r is not None:
                najvacsia = max(najvacsia, abs(r - v))
                setattr(q, a, r)
                zmeny["Qto"] += 1

    # ---- Overall* na výplniach -------------------------------------------
    for cls, attrs in OVERALL.items():
        for e in m.by_type(cls):
            for a in attrs:
                v = getattr(e, a, None)
                r = clean(v)
                if r is not None:
                    najvacsia = max(najvacsia, abs(r - v))
                    setattr(e, a, r)
                    zmeny["Overall*"] += 1

    # ---- property --------------------------------------------------------
    for p in m.by_type("IfcPropertySingleValue"):
        v = p.NominalValue
        if v is None:
            continue
        w = v.wrappedValue
        r = clean(w)
        if r is not None:
            najvacsia = max(najvacsia, abs(r - w))
            p.NominalValue = m.create_entity(v.is_a(), r)
            zmeny["property"] += 1

    print("ZMENY")
    if zmeny:
        for k in ("Qto", "Overall*", "property"):
            print("  #AJ  %-10s %5d hodnôt" % (k, zmeny[k]))
        print("  #AJ  spolu %d; najväčšia oprava %.3g" % (sum(zmeny.values()), najvacsia))
    else:
        print("  #AJ  žiadny šum — preskočené (idempotentné)")

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
