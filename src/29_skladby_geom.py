"""Fáza 8b — skladby so zdieľanými kódmi (S1, S2, S6).

    python src/29_skladby_geom.py           # dry-run
    python src/29_skladby_geom.py --apply   # zapíše out/ASR_v17.ifc

Prečo samostatný krok
---------------------
Fáza 8 založila päť skupín, ktorých členstvo je jednoznačné. `S1`, `S2`
a `S6` zdieľajú kódy `ST01.10` (25 ks), `SD02` (9) a `PH01` (24)
s ostatnými skladbami, takže priradenie „všetky prvky kódu" by dalo tú
istú dosku do štyroch skupín naraz.

Pravidlo od Samuela
-------------------
*„Kačírek je pri atikách a stenách asi 600 mm od kraja."* Model to už
nesie: `ST01.21` má menší rozmer pôdorysu **360–1000 mm, medián 520** —
úzke pásy po obvode, kým `ST01.20` má 4195–9750 mm, teda plochy. Ktorá
plocha je ktorá sa teda nemusí odvodzovať, stačí ju prečítať z modelu.

Sufix `a`/`b` v tom nepomáha: majú ho len typy `ST01.10a` a `ST01.10b`
a rozlišuje klinovú izoláciu od rovných dosiek, nie kačírek od vegetácie.

Ako sa priraďujú zdieľané kódy
------------------------------
Prvok patrí do skladby, ak **leží v jej súvrství**: pôdorysne prekrýva
značkovú vrstvu a jeho zvislý rozsah zasahuje do pásma od spodku značky
nadol o `HLBKA`.

Skupiny sa **nevylučujú** a nemajú. Kačírkový pás je 600 mm okraj tej
istej strešnej plochy, pod ktorou je vegetácia, takže jedna izolačná
doska patrí do `S1` aj `S2` — a tak to aj v skutočnosti je.

Prvý pokus o toto priradenie zlyhal na podmienke „vrch prvku pod spodkom
značky". Klinová izolácia sa s krytinou **prerastá** — medzera vychádza
medián −144 mm — takže tá podmienka vylúčila skoro všetko. Pásmo tento
problém nemá.

Stabilita
---------
Hĺbka pásma je zvolená z citlivostnej skúšky. `S1` a `S2` sa nemenia
medzi 600 a 3000 mm — `ST01.10` 23 resp. 24 kusov, `SD02` po 2 —
takže nestoja na šťastnej tolerancii. `S6` áno: zo 17 prvkov pri 2000 mm
skočí na 30 pri 3000, lebo značkou je celá podlahová doska a pásmo
prepadne do podlažia pod ňou. Preto 2000 mm.

Skúšku vie zopakovať ktokoľvek cez `--hlbka`.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v16.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v17.ifc")

DRY_RUN = True

#: Hĺbka pásma pod značkovou vrstvou (mm) — izolácia + doska + plénum.
#: Zvolená z citlivostnej skúšky, nie od oka: S1 a S2 sú stabilné od 1200
#: do 3000 (ST01.10 23 a 24 kusov, SD02 po 2), ale S6 skočí zo 17 na 30
#: prvkov medzi 2000 a 3000 — tam už pásmo siaha do cudzieho podlažia.
#: 2000 je vnútri stabilného pásma pre všetky tri.
HLBKA = 2000.0

#: skupina → (názov, značkový kód, zdieľané kódy v pásme)
SKLADBY = {
    "S1": ("Skladba jednoplášťovej plochej strechy - vegetácia",
           "ST01.20", ("ST01.10", "SD02", "PH01")),
    "S2": ("Skladba jednoplášťovej plochej strechy - kačírek",
           "ST01.21", ("ST01.10", "SD02", "PH01")),
    "S6": ("Skladba podlahy a stropu v kanceláriách",
           "PD03.30", ("SD02", "PH01")),
}

DESC = ("Skladba podľa D.1.1.09. Zdieľané kódy priradené z geometrie: prvok "
        "pôdorysne prekrýva značkovú vrstvu a leží v jej súvrství. Skupiny sa "
        "nevylučujú — kačírkový pás je okraj tej istej plochy ako vegetácia.")


def bboxes(model, products):
    out = {}
    products = [p for p in products if p.Representation is not None]
    if not products:
        return out
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        s, model, max(1, (os.cpu_count() or 2) - 1), include=products)
    if not it.initialize():
        return out
    while True:
        sh = it.get()
        v = sh.geometry.verts
        if v:
            xs, ys, zs = v[0::3], v[1::3], v[2::3]
            out[sh.guid] = (min(xs) * 1000, min(ys) * 1000, min(zs) * 1000,
                            max(xs) * 1000, max(ys) * 1000, max(zs) * 1000)
        if not it.next():
            break
    return out


def prekryv(a, b):
    ix = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    iy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ix * iy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--hlbka", type=float, default=HLBKA)
    args = ap.parse_args()
    dry = DRY_RUN and not args.apply

    print("vstup :", args.src)
    print("výstup:", args.dst, "(DRY-RUN)" if dry else "")
    print("hĺbka pásma:", args.hlbka, "mm\n")

    m = ifcopenshell.open(args.src)
    added: list[str] = []

    existujuce = {g.Name for g in m.by_type("IfcGroup")}
    chybaju = [k for k in SKLADBY if k not in existujuce]
    if not chybaju:
        print("S1, S2 aj S6 už existujú — skript je idempotentný, končí")
        return 0

    occ = [e for e in m.by_type("IfcProduct")
           if not e.is_a("IfcFeatureElement") and not e.is_a("IfcTypeObject")]
    zaujem = set()
    for _, znacka, kody in SKLADBY.values():
        zaujem.add(znacka)
        zaujem.update(kody)
    kandidati = [e for e in occ if (e.Name or "").startswith(tuple(zaujem))]
    box = bboxes(m, kandidati)
    owner = occ[0].OwnerHistory

    for kod in sorted(chybaju):
        nazov, znacka, kody = SKLADBY[kod]
        znacky = [(e, box[e.GlobalId]) for e in kandidati
                  if (e.Name or "").startswith(znacka) and e.GlobalId in box]
        if not znacky:
            raise SystemExit("STOP: %s — značka %s nemá ani jeden prvok"
                             % (kod, znacka))

        cleny = {e.id(): e for e, _ in znacky}
        najdene = collections.Counter()
        for e in kandidati:
            n = e.Name or ""
            if not n.startswith(tuple(kody)) or e.GlobalId not in box:
                continue
            eb = box[e.GlobalId]
            for _, zb in znacky:
                if prekryv(eb, zb) <= 0:
                    continue
                lo, hi = zb[2] - args.hlbka, zb[5]
                if eb[5] >= lo and eb[2] <= hi:      # zvislé rozsahy sa stretnú
                    cleny[e.id()] = e
                    najdene[n[:7]] += 1
                    break

        g = m.create_entity("IfcGroup", GlobalId=ifcopenshell.guid.new(),
                            OwnerHistory=owner, Name=kod,
                            Description="%s — %s" % (nazov, DESC))
        rel = m.create_entity("IfcRelAssignsToGroup",
                              GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                              RelatedObjects=tuple(cleny.values()), RelatingGroup=g)
        added.extend([g.GlobalId, rel.GlobalId])
        print("  %-3s %-46s %3d prvkov" % (kod, nazov[:46], len(cleny)))
        print("       značka %s %d ks; v pásme %s"
              % (znacka, len(znacky), dict(najdene)))

    siroty = [e for e in m if not m.get_total_inverses(e)
              and not any(e.is_a(w) for w in
                          ("IfcShapeAspect", "IfcMaterialDefinitionRepresentation",
                           "IfcPresentationLayerAssignment", "IfcMapConversion",
                           "IfcRelationship", "IfcRepresentationContext"))]
    if siroty:
        raise SystemExit("STOP: krok vyrobil %d osirelých entít" % len(siroty))
    print("\n  kontrola inv 4: 0 osirelých")
    print("  GlobalId nových: %d" % len(added))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(added)}, fh,
                  ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
