"""Fáza 18 — #AY: zmazanie nepoužitého subkontextu „Box".

Rozhodnutie Samuela z 10. 8.: *„tak ho zmaž, keď to nič nepokazí."*

    python src/37_sweep_box_context.py            # dry-run
    python src/37_sweep_box_context.py --apply    # zapíše out/ASR_v25.ifc

Čo robí
-------
Zmaže `IfcGeometricRepresentationSubContext` s `ContextIdentifier = 'Box'`.
Je to zvyšok po Revite — subkontext pre reprezentácie typu obalové teleso,
ktorý v modeli **nepoužíva ani jedna reprezentácia**.

Prečo to bola vôbec otázka
--------------------------
Objavil sa tak, že ho invariant 4 hlásil ako osirelú entitu, a to hlásenie
bolo **falošné**: subkontext drží väzbu na rodiča dopredným atribútom
`ParentContext`, takže inverzov má vždy nula, aj keď je riadnou súčasťou
stromu projektu. Preto je `IfcRepresentationContext` v `ORPHAN_WHITELIST`.
Otázka teda neznela „je to chyba", ale „načo to tam je".

Namerané na `ASR_v24.ifc`:

| kontext | reprezentácií | detí | inverzov |
|---|--:|--:|--:|
| `#13` Model | 47 | 4 | 53 |
| `#14` Axis | 617 | 0 | 617 |
| `#15` Body | 3282 | 0 | 3282 |
| **`#16` Box** | **0** | **0** | **0** |
| `#17` FootPrint | 185 | 0 | 185 |

Skript to overí znova a **zastaví sa**, ak by naň čokoľvek odkazovalo.

Čo NEROBÍ
---------
`IfcRepresentationContext` sa z `ORPHAN_WHITELIST` **nevyhadzuje**.
Po zmazaní „Boxu" by tam už nebol potrebný — ostatné tri subkontexty
inverzy majú — ale pravidlo platí ďalej: keby ktorýkoľvek subkontext
prestal byť použitý, test by ho opäť hlásil falošne.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v24.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v25.ifc")

DRY_RUN = True
IDENTIFIER = "Box"


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

    ciele = [c for c in model.by_type("IfcGeometricRepresentationSubContext")
             if c.ContextIdentifier == IDENTIFIER]
    if not ciele:
        print("Idempotencia: subkontext %r v modeli nie je." % IDENTIFIER)
        return 0
    if len(ciele) != 1:
        raise SystemExit("STOP: subkontextov %r je %d, čakal som 1"
                         % (IDENTIFIER, len(ciele)))
    ctx = ciele[0]

    # dôkaz, že mazanie nič nepokazí — tri nezávislé kontroly
    repr_na_nom = [r for r in model.by_type("IfcRepresentation")
                   if r.ContextOfItems and r.ContextOfItems.id() == ctx.id()]
    deti = [c for c in model.by_type("IfcGeometricRepresentationSubContext")
            if c.ParentContext and c.ParentContext.id() == ctx.id()]
    inverzy = list(model.get_inverse(ctx))

    print("  #%d  %s" % (ctx.id(), ctx.is_a()))
    print("     reprezentácií na ňom : %d" % len(repr_na_nom))
    print("     detských subkontextov: %d" % len(deti))
    print("     inverzných odkazov   : %d" % len(inverzy))
    print("     rodič                : #%d" % ctx.ParentContext.id())

    if repr_na_nom or deti or inverzy:
        raise SystemExit("STOP: na subkontext sa odkazuje — mazanie by "
                         "model pokazilo")

    zostanu = [c.ContextIdentifier for c in
               model.by_type("IfcGeometricRepresentationSubContext")
               if c.id() != ctx.id()]
    print("\n  zostanú subkontexty: %s" % ", ".join(sorted(map(str, zostanu))))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    model.remove(ctx)
    model.write(args.dst)
    print("\nzmazaný 1 subkontext, zapísané:", args.dst)

    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
