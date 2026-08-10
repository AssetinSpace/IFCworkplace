"""Fáza 16 — `OV02` prístrešky vstupov na `IfcShadingDevice / AWNING`.

Rozhodnutie Samuela z 10. 8.: *„builtelement podľa mňa takto schéma
nepovoľuje, daj radšej shading protective system alebo čo alebo niečo iné
na markízu."*

    python src/35_ov02_shading.py            # dry-run
    python src/35_ov02_shading.py --apply    # zapíše out/ASR_v23.ifc

Čo robí
-------
Sedem `OV02` (6× `OV02.01` 3470×1500, 1× `OV02.02` 5970×1500) a ich dva
typy prechádza z `IfcBuiltElement` na `IfcShadingDevice / AWNING`.

Prečo sa mení to, čo fáza 11 zapísala
-------------------------------------
Fáza 11 zvolila `IfcBuiltElement` s odôvodnením, že entita
`IfcShadingDevice` je definovaná ako ochrana *„from the sunlight, from
natural light, or screening them from view"* a jej NOTE posiela prvky
s iným primárnym účelom inam — sklenený prístrešok netieni, chráni pred
zrážkami.

**Schéma `IfcBuiltElement` nezakazuje** — overené priamo proti
`IFC4X3_ADD2`, `is_abstract()` je `False` pre `IfcBuiltElement` aj
`IfcBuiltElementType`. Rozhodnutie Samuela je teda voľbou konkrétnejšej
entity pred všeobecnou, nie opravou nelegálneho zápisu, a §8 dáva
autoritu jemu.

Vecná opora pre `AWNING` je pritom silná — enum hovorí doslova:
*„A rooflike shelter of canvas or other material extending over a doorway,
from the top of a window, over a deck, or similar, in order to provide
protection, as from the sun."* Formulácia „extending over a doorway"
sedí na prístrešok vstupu presne; napätie je len medzi ňou a definíciou
nadradenej entity.

`ObjectType` sa **maže**. Nesie význam len vtedy, keď je
`PredefinedType = USERDEFINED`; pri `AWNING` by bol duplicitný.
Meno `OV02.*` a popis rozmeru zostávajú.

Pasce
-----
* `IfcShadingDevice` aj `IfcBuiltElement` sú `IfcBuiltElement`, takže
  množina tvarov, ktorú stráži invariant 1, sa **nemení** — allowlist je
  prázdny. Fáza 11 ho mať musela, lebo vtedy prvky do tej množiny
  vstupovali z `IfcFurniture`.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell
import ifcopenshell.util.schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v22.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v23.ifc")

DRY_RUN = True

TYPY = {"OV02.01": 6, "OV02.02": 1}
NOVA_TRIEDA = "IfcShadingDevice"
NOVY_TYP = "IfcShadingDeviceType"
PDT = "AWNING"


def type_by_name(model, name):
    hits = [t for t in model.by_type("IfcTypeObject") if t.Name == name]
    if len(hits) != 1:
        raise SystemExit("STOP: typ %r nájdený %d× (čakal som 1)" % (name, len(hits)))
    return hits[0]


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

    hotove = sum(1 for n in TYPY if type_by_name(model, n).is_a() == NOVY_TYP)
    if hotove == len(TYPY):
        print("Idempotencia: oba typy už sú %s, niet čo meniť." % NOVY_TYP)
        return 0
    if hotove:
        raise SystemExit("STOP: %d z %d typov je už prekvalifikovaných"
                         % (hotove, len(TYPY)))

    rows = []
    for name, ocak in TYPY.items():
        typ = type_by_name(model, name)
        occ = list(typ.Types[0].RelatedObjects) if typ.Types else []
        if len(occ) != ocak:
            raise SystemExit("STOP: %s má %d occurrences, čakal som %d"
                             % (name, len(occ), ocak))
        pred = occ[0].is_a()
        occ_ids = [o.id() for o in occ]
        tid = typ.id()

        rel = typ.Types[0]
        saved = [o.id() for o in rel.RelatedObjects]
        rel.RelatedObjects = ()
        for oid in occ_ids:
            ifcopenshell.util.schema.reassign_class(
                model, model.by_id(oid), NOVA_TRIEDA)
        ifcopenshell.util.schema.reassign_class(model, model.by_id(tid), NOVY_TYP)
        rel = model.by_id(rel.id())
        rel.RelatedObjects = tuple(model.by_id(i) for i in saved)

        typ = model.by_id(tid)
        typ.PredefinedType = PDT
        for oid in occ_ids:
            o = model.by_id(oid)
            o.PredefinedType = PDT
            o.ObjectType = None          # význam nesie enum, nie ObjectType
        rows.append((name, pred, NOVA_TRIEDA, PDT, len(occ)))

    w = "  %-9s %-18s → %-18s %-9s %4s"
    print(w % ("typ", "pred", "po", "PDT", "occ"))
    print("  " + "-" * 66)
    for r in rows:
        print(w % r)
    print("\nprekvalifikovaných %d occurrences a %d typov"
          % (sum(r[4] for r in rows), len(rows)))

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
