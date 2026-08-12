"""Akceptačné meranie modelu.

    python src/report_final.py                    # out/ASR_v16.ifc
    python src/report_final.py --in out/ASR_v9.ifc

Prejde tvrdenia, ktoré o modeli robí `AUDIT.md`, a odmeria ich naraz.
Nič nemení. Určené na to, aby sa dalo kedykoľvek povedať, v akom stave
model je, bez čítania celého registra.

Invarianty tu **nie sú** — tie robí `src/gate.py`. Toto je vecný obsah:
názvoslovie, typy, priestory, vzťahy, materiály.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

import ifcopenshell

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_invariants import (  # noqa: E402
    SKLADBA_PARENT,
    parse_snim,
    snim_occurrences,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v16.ifc")


def riadok(nazov, hodnota, poznamka=""):
    print("  %-42s %12s  %s" % (nazov, hodnota, poznamka))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    args = ap.parse_args()
    m = ifcopenshell.open(args.src)
    print("model:", args.src, "\n")

    # ---- názvoslovie ----------------------------------------------------
    print("NÁZVOSLOVIE")
    occ = snim_occurrences(m)
    plne = [e for e in occ if parse_snim(e.Name)[1] is not None]
    bez = [e for e in occ if parse_snim(e.Name)[0] is None]
    mena = collections.Counter(e.Name for e in plne)
    dupl = [k for k, v in mena.items() if v > 1]
    riadok("occurrences spolu", len(occ))
    riadok("z toho s plným SNIM kódom", len(plne))
    riadok("bez rozpoznaného kódu", len(bez),
           sorted({e.is_a() for e in bez}) if bez else "")
    riadok("duplicitných plných kódov", len(dupl), dupl[:5] if dupl else "žiadne")

    # ---- typy -----------------------------------------------------------
    print("\nTYPY")
    typy = m.by_type("IfcTypeObject")
    viac = [t for t in typy if len(t.Types) > 1]
    # porty sa netypujú a agregujúce IfcRoof z fázy 1 typ nemajú zámerne
    netypovane = [e for e in occ if not getattr(e, "IsTypedBy", None)
                  and not e.is_a("IfcSpace") and not e.is_a("IfcCurtainWall")
                  and not e.is_a("IfcSpatialElement")
                  and not e.is_a("IfcDistributionPort") and not e.is_a("IfcRoof")]
    riadok("IfcTypeObject", len(typy))
    riadok("typov s viac než jedným IfcRelDefinesByType", len(viac))
    riadok("netypovaných prvkov", len(netypovane),
           "porty a strešné obaly sa nerátajú")
    rovnomenne = [k for k, v in collections.Counter(t.Name for t in typy).items() if v > 1]
    riadok("rovnomenných typov", len(rovnomenne), rovnomenne[:6] if rovnomenne else "žiadne")

    # ---- priestory ------------------------------------------------------
    print("\nPRIESTORY")

    def podlazie(s):
        for r in (s.Decomposes or ()):
            return r.RelatingObject.Name

    def plocha(s):
        for r in (s.IsDefinedBy or ()):
            if r.is_a("IfcRelDefinesByProperties"):
                d = r.RelatingPropertyDefinition
                if d.is_a("IfcElementQuantity"):
                    for q in d.Quantities:
                        if q.Name == "NetFloorArea":
                            return q.AreaValue
        return 0.0

    per = collections.Counter()
    ks = collections.Counter()
    for s in m.by_type("IfcSpace"):
        per[podlazie(s)] += plocha(s)
        ks[podlazie(s)] += 1
    for k in sorted(per, key=str):
        riadok("  %s" % k, "%.2f m²" % per[k], "%d priestorov" % ks[k])
    riadok("spolu", "%.2f m²" % sum(per.values()), "%d priestorov" % sum(ks.values()))
    riadok("bez Qto_BodyGeometryValidation",
           sum(1 for s in m.by_type("IfcSpace")
               if not any(r.is_a("IfcRelDefinesByProperties")
                          and r.RelatingPropertyDefinition.is_a("IfcElementQuantity")
                          and r.RelatingPropertyDefinition.Name == "Qto_BodyGeometryValidation"
                          for r in (s.IsDefinedBy or ()))))

    # ---- vzťahy ---------------------------------------------------------
    print("\nVZŤAHY")
    vspace = sum(len(r.RelatedElements) for r in m.by_type("IfcRelContainedInSpatialStructure")
                 if r.RelatingStructure.is_a("IfcSpace"))
    vstorey = sum(len(r.RelatedElements) for r in m.by_type("IfcRelContainedInSpatialStructure")
                  if r.RelatingStructure.is_a("IfcBuildingStorey"))
    riadok("prvkov kontajnovaných v miestnostiach", vspace)
    riadok("prvkov kontajnovaných v podlažiach", vstorey)
    hr = m.by_type("IfcRelSpaceBoundary")
    riadok("IfcRelSpaceBoundary", len(hr),
           "%d s ParentBoundary" % sum(1 for x in hr if getattr(x, "ParentBoundary", None)))
    riadok("IfcRelAggregates", len(m.by_type("IfcRelAggregates")))
    riadok("IfcZone / IfcSystem / IfcGroup",
           "%d / %d / %d" % (len(m.by_type("IfcZone")), len(m.by_type("IfcSystem")),
                             len(m.by_type("IfcGroup"))))

    # ---- skladby ---------------------------------------------------------
    # Po fáze 21 sú skupiny dvojúrovňové. Bez rozlíšenia by počet skupín
    # vyskočil z 8 na 23 a vyzeralo by to ako strata prehľadu.
    print("\nSKLADBY")
    predpisy = [g for g in m.by_type("IfcGroup")
                if g.is_a() == "IfcGroup" and SKLADBA_PARENT.match(g.Name or "")]
    vyskyty, clenstiev, rozlozene = [], 0, 0
    for g in sorted(predpisy, key=lambda x: int(x.Name[1:])):
        deti = [x for rel in (g.IsDecomposedBy or ())
                for x in rel.RelatedObjects if x.is_a("IfcGroup")]
        vyskyty.extend(deti)
        rozlozene += 1 if deti else 0
        clenstiev += sum(len(rel.RelatedObjects)
                         for d in deti for rel in (d.IsGroupedBy or ()))
    riadok("predpisov skladieb (S1–S9)", len(predpisy))
    riadok("z toho rozložených na výskyty", "%d / %d" % (rozlozene, len(predpisy)))
    riadok("výskytov skladieb (S<n>.<NN>)", len(vyskyty))
    riadok("členstiev vo výskytoch", clenstiev,
           "prvok smie byť vo viacerých skladbách naraz")

    # ---- psety a materiály ----------------------------------------------
    print("\nPSETY A MATERIÁLY")
    prazdne = [p for p in m.by_type("IfcPropertySet") if not p.HasProperties]
    riadok("prázdnych IfcPropertySet", len(prazdne))
    # Status je IfcPropertyEnumeratedValue, nie SingleValue — merať cez
    # IfcProperty, inak vyjde nula a vyzerá to ako strata dát
    status = sum(1 for p in m.by_type("IfcProperty") if p.Name == "Status")
    riadok("vlastností Status", status)
    kon = m.by_type("IfcMaterialConstituent")
    riadok("IfcMaterialConstituent", len(kon))
    vzduch = [l for l in m.by_type("IfcMaterialLayer")
              if l.IsVentilated is not None and l.Material is None]
    riadok("vzduchových vrstiev (void, IsVentilated)", len(vzduch))

    # ---- PredefinedType --------------------------------------------------
    print("\nPREDEFINEDTYPE")
    bezpt = collections.Counter()
    for e in occ:
        if not hasattr(e, "PredefinedType"):
            continue
        if getattr(e, "PredefinedType", None) in (None, "NOTDEFINED"):
            bezpt[e.is_a()] += 1
    riadok("occurrences bez PredefinedType", sum(bezpt.values()),
           "z toho %d IfcCurtainWall (enum nemá čo ponúknuť)"
           % bezpt.get("IfcCurtainWall", 0))
    for k, v in bezpt.most_common():
        if k != "IfcCurtainWall":
            riadok("  %s" % k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
