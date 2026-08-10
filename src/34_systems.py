"""Fáza 15 — `IfcDistributionSystem` namiesto `IfcSystem`.

Rozhodnutie Samuela z 10. 8.: *„takýto systém určite nie, skôr asi
distribution system a pridaj tam všetky."*

    python src/34_systems.py            # dry-run
    python src/34_systems.py --apply    # zapíše out/ASR_v22.ifc

Čo robí
-------
Tri `IfcSystem` prekvalifikuje na `IfcDistributionSystem` s `PredefinedType`
a doplní do strešného odvodnenia dva poistné prepady `OV04.03`, ktoré
fáza 10 minula a fáza 11 nechala mimo.

| systém | členov | `PredefinedType` |
|---|--:|---|
| Zdravotechnika | 46 | `SEWAGE` |
| Odvodnenie strechy | 18 + **2** | `RAINWATER` |
| Podlahové vpuste | 5 | `DRAINAGE` |

Opora pre hodnoty
-----------------
`SEWAGE` — *„Sewage collection system."* Model to hovorí sám: všetkých
**51 `IfcDistributionPort` nesie `SystemType = SEWAGE`**.

`RAINWATER` — *„Rainwater resulting from precipitation which directly
falls on a parcel."* Zvolené proti `STORMWATER`, ktoré je *„runs off or
travels over the ground surface"* — strešná vpusť zachytáva zrážky priamo,
nie povrchový odtok.

`DRAINAGE` — *„Drainage collection system."* Podlahové vpuste `OV01.01`
ležia **vnútri budovy** (1NP, `1.07`, `3.14`, `4.01`), nie na streche,
takže `RAINWATER` by na ne nesedelo.

Pozor — toto prebíja skoršie rozhodnutie
----------------------------------------
Fáza 10 zvolila `IfcSystem` **zámerne** a `BEP_ANNEX.md` §2.5 to zdôvodňuje
tým, že model má 51 portov a **0 `IfcFlowSegment`**, takže sieť neexistuje
a entita, ktorá ju sľubuje, by klamala. Rozhodnutie Samuela to prebíja.

Vecne to schéma nezakazuje: `IfcDistributionSystem` je podtyp `IfcSystem`,
teda zoskupenie, a **žiadne pravidlo nevyžaduje, aby systém obsahoval
segmenty**. Zostáva pravdivé, že sieť v modeli nie je — to sa presúva
z odôvodnenia triedy do poznámky o rozsahu. §2.5 sa prepisuje.

Mená sa menia tiež: „Zoskupenie zariadení — …" bolo zvolené práve preto,
aby netvrdilo, že ide o systém. Po prekvalifikovaní by si meno a trieda
protirečili.

Pasce
-----
* ``ifcopenshell.util.schema.reassign_class`` — zachová ``id()`` aj
  ``GlobalId``, takže `IfcRelServicesBuildings` aj `IfcRelAssignsToGroup`
  držia a invariant 3 nehlási nič.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell
import ifcopenshell.util.schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v21.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v22.ifc")

DRY_RUN = True

#: staré meno → (nové meno, PredefinedType, počet členov, kód na doplnenie)
PLAN = {
    "Zoskupenie zariadení — zdravotechnika":
        ("Zdravotechnika", "SEWAGE", 46, None),
    "Zoskupenie zariadení — strešné vpuste":
        ("Odvodnenie strechy", "RAINWATER", 18, "OV04.03"),
    "Zoskupenie zariadení — podlahové vpuste":
        ("Podlahové vpuste", "DRAINAGE", 5, None),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY", "\n")

    systemy = [s for s in model.by_type("IfcSystem") if s.is_a() == "IfcSystem"]
    hotove = model.by_type("IfcDistributionSystem")
    if not systemy and len(hotove) == len(PLAN):
        print("Idempotencia: všetky %d systémy už sú IfcDistributionSystem."
              % len(hotove))
        return 0
    if len(systemy) != len(PLAN):
        raise SystemExit("STOP: nájdených %d IfcSystem, čakal som %d"
                         % (len(systemy), len(PLAN)))

    rows = []
    for s in sorted(systemy, key=lambda x: x.Name or ""):
        if s.Name not in PLAN:
            raise SystemExit("STOP: neznámy systém %r" % s.Name)
        nove_meno, pdt, ocak, doplnit = PLAN[s.Name]

        rel = s.IsGroupedBy[0] if s.IsGroupedBy else None
        clenov = len(rel.RelatedObjects) if rel else 0
        if clenov != ocak:
            raise SystemExit("STOP: %r má %d členov, čakal som %d"
                             % (s.Name, clenov, ocak))

        pridane = []
        if doplnit:
            pridane = [e for e in model.by_type("IfcWasteTerminal")
                       if (e.Name or "").startswith(doplnit)]
            if not pridane:
                raise SystemExit("STOP: %s v modeli nie je" % doplnit)
            uz = {o.id() for o in rel.RelatedObjects}
            pridane = [e for e in pridane if e.id() not in uz]

        sid = s.id()
        stare_meno = s.Name
        ifcopenshell.util.schema.reassign_class(
            model, model.by_id(sid), "IfcDistributionSystem")
        s = model.by_id(sid)
        s.Name = nove_meno
        s.PredefinedType = pdt

        if pridane:
            rel = model.by_id(rel.id())
            rel.RelatedObjects = tuple(rel.RelatedObjects) + tuple(pridane)

        rows.append((stare_meno, nove_meno, pdt, clenov, len(pridane)))

    w = "  %-40s → %-20s %-11s %4s %6s"
    print(w % ("pôvodné meno", "nové meno", "PDT", "člen", "prid."))
    print("  " + "-" * 88)
    for r in rows:
        print(w % r)
    print("\nprekvalifikovaných systémov: %d, doplnených členov: %d"
          % (len(rows), sum(r[4] for r in rows)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    model.write(args.dst)
    print("\nzapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
