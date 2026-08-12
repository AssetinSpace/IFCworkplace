"""Fáza 22 — `S3` sa zužuje na základovú dosku (#BE).

    python src/41_s3_rozsah.py           # dry-run
    python src/41_s3_rozsah.py --apply   # zapíše out/ASR_v29.ifc

Čo bolo zle
-----------
`S3` sa volá „Skladba základovej dosky a podlahy v 1NP", ale mala 54
prvkov, z toho 22 podláh na 2NP–4NP. Členstvo prišlo z fázy 8 pravidlom
„všetky prvky kódu" — `PD02` vtedy nikto iný nezdieľal, čo je ale iná
otázka než „patrí do tejto skladby". Fáza 21 to zviditeľnila rozkladom
na štyri výskyty; tento krok to rieši.

Doklady z podkladu
------------------
Tri nezávislé, všetky hovoria to isté:

1. **`PD02` je vo výpise `D.1.1.09` presne raz** — v S3. Ani S6 (tá má
   `PD03.30` dutinovú podlahu), ani žiadna iná skladba ho neuvádza.
   Podlaha na stropnej doske vo výpise **nie je vôbec**.

2. **S3 stojí na základovej doske.** Vrstva 7 výpisu je `ZD02.01`,
   „Železobetónová základová doska", 500 mm; pod ňou `IH01`
   hydroizolácia a `DZ01` podkladný betón. V modeli je `ZD02.01` jedna
   jediná doska. Podlahy vyšších podlaží ležia na stropných doskách
   `SD02`, čo je iný substrát.

3. **Sedí to na hrúbke izolácie.** Výpis predpisuje EPS 150 hrúbky
   **200 mm**. Každý `PD02` na 1NP má 200 mm (výnimky `PD02.11` XPS 150
   a `PD02.54` EPS 100), kým **všetkých 22 na 2NP–4NP má EPS 50 mm**.

Rozhodnutie Samuela (12. 8.) po kontrole podkladov: prvky zo skupiny
vypadnú a **novú skupinu nedostanú**. Výpis pre ne skladbu nemá, takže
akákoľvek skupina by tvrdila viac, než podklad hovorí. Zostáva to ako
chýbajúci podklad v registri, nie ako vada modelu.

Poznámka pre toho, kto to bude riešiť ďalej: výpis preskakuje práve jedno
číslo — za `S6` ide rovno `S8`. Že chýbajúca `S7` je práve táto podlaha
na stropnej doske, je pravdepodobné, ale je to domnienka. Potvrdiť ju vie
len projektant.

Ako sa vyberá, čo zostane
-------------------------
Nie podľa mena podlažia, ale podľa toho, čo skladbu definuje: **zostáva
ten výskyt, ktorý obsahuje základovú dosku.** Kritérium je prevzaté
priamo z výpisu, takže sa nedá rozísť s ním preklepom v názve podlažia.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from tests.test_invariants import ORPHAN_WHITELIST  # noqa: E402

IN = os.path.join(ROOT, "out", "ASR_v28.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v29.ifc")

DRY_RUN = True

#: skladba, ktorá sa zužuje
KOD = "S3"

#: vrstva 7 výpisu — nosný prvok, ktorý skladbu definuje. Výskyt, ktorý
#: ju obsahuje, je ten pravý; ostatné ležia na stropných doskách.
NOSNA_VRSTVA = "ZD02.01"


def cleny(g):
    return [e for rel in (g.IsGroupedBy or ()) for e in rel.RelatedObjects]


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
    removed: list[str] = []

    rodic = [g for g in m.by_type("IfcGroup")
             if g.is_a() == "IfcGroup" and g.Name == KOD]
    if len(rodic) != 1:
        raise SystemExit("STOP: %s je v modeli %dx, očakáva sa raz"
                         % (KOD, len(rodic)))
    rodic = rodic[0]

    aggs = list(rodic.IsDecomposedBy or ())
    if len(aggs) != 1:
        raise SystemExit("STOP: %s nie je rozložená — najprv fáza 21" % KOD)
    deti = [x for x in aggs[0].RelatedObjects if x.is_a("IfcGroup")]

    drzi = [d for d in deti
            if any((e.Name or "").startswith(NOSNA_VRSTVA) for e in cleny(d))]
    if len(drzi) != 1:
        raise SystemExit(
            "STOP: %s obsahuje %d výskytov so základovou doskou %s, očakáva sa "
            "práve jeden — kritérium neplatí a krok by hádal"
            % (KOD, len(drzi), NOSNA_VRSTVA))
    drzi = drzi[0]
    zrusit = [d for d in deti if d.id() != drzi.id()]

    if not zrusit:
        print("%s má už len výskyt so základovou doskou (%s) — skript je "
              "idempotentný, končí" % (KOD, drzi.Name))
        return 0

    print("ZMENY")
    print("  %-6s ZOSTÁVA  %3d prvkov  %s"
          % (drzi.Name, len(cleny(drzi)),
             dict(collections.Counter((e.Name or "")[:7] for e in cleny(drzi)))))
    spolu = 0
    for d in zrusit:
        c = cleny(d)
        spolu += len(c)
        print("  %-6s RUŠÍ SA %3d prvkov  %s"
              % (d.Name, len(c),
                 dict(collections.Counter((e.Name or "")[:7] for e in c))))
    print("\n  zo skupiny %s vypadne %d prvkov; skupinu nedostanú, výpis "
          "D.1.1.09 pre ne skladbu nemá" % (KOD, spolu))

    # agregácia sa previaže skôr, než deti zmiznú — inak by na ne
    # `RelatedObjects` ukazoval do prázdna
    aggs[0].RelatedObjects = (drzi,)
    for d in zrusit:
        for rel in list(d.IsGroupedBy or ()):
            removed.append(rel.GlobalId)
            m.remove(rel)
        removed.append(d.GlobalId)
        m.remove(d)

    zostalo = cleny(drzi)
    print("\n  %s po zmene: 1 výskyt, %d prvkov" % (KOD, len(zostalo)))

    siroty = [e for e in m if not m.get_total_inverses(e)
              and not any(e.is_a(w) for w in ORPHAN_WHITELIST)]
    if siroty:
        raise SystemExit("STOP: krok vyrobil %d osirelých entít: %s"
                         % (len(siroty), collections.Counter(e.is_a() for e in siroty)))
    print("  kontrola inv 4: 0 osirelých")
    print("  GlobalId zmazaných: %d" % len(removed))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed)), "added": []},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
