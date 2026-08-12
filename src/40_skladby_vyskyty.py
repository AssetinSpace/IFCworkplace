"""Fáza 21 — výskyty skladieb, `S1` → `S1.01` a `S1.02`.

    python src/40_skladby_vyskyty.py           # dry-run
    python src/40_skladby_vyskyty.py --apply   # zapíše out/ASR_v28.ifc

Čo bolo zle
-----------
Skupina `S1` (vegetačná strecha) obsahovala naraz prvky **veľkej strechy
4NP** aj **malej strechy 5NP**. To isté `S2`. Skupina tak nezodpovedala
žiadnej skutočnej konštrukcii — bolo to zjednotenie dvoch nezávislých
súvrství, ktoré majú zhodou okolností rovnaký predpis. Vo výkaze sa
nedalo povedať „koľko m² S1 je na malej streche".

Príčina je v kľúči fázy 8b (`29_skladby_geom.py:151-171`): značkové
vrstvy sa hľadajú správne, ale **všetky sa zlúčia do jednej skupiny**.
Žiadny člen kľúča nehovorí, na ktorej streche značka leží. Fáza 8
(`28_layer_sets.py:151-164`) má to isté inak — berie všetky prvky kódu
plus ich agregačných rodičov bez ohľadu na to, koľko samostatných
konštrukcií z toho vyjde.

Čo hovorí schéma
----------------
Nie je to type a occurrence. `IfcRelDefinesByType` by formálne prešlo
(`RelatedObjects : SET [1:?] OF IfcObject`, `IfcGroup` **je** `IfcObject`,
`IfcTypeObject` nie je `ABSTRACT`), ale sémantika typu je o zdieľaných
psetoch a tvare medzi **produktmi** a jediné podtypy `IfcTypeObject` sú
`IfcTypeProduct`, `IfcTypeProcess` a `IfcTypeResource` — typ skupiny
v schéme neexistuje.

`IfcMaterialLayerSet` tiež nie: ten je správny type/occurrence pár pre
skladbu **jedného prvku** (*„can be shared among several occurrence
objects"* + `IfcMaterialLayerSetUsage` na výskyte). Tu je skladba
rozprestretá cez viac prvkov, z ktorých každý nesie vlastný layer set.

Vzťah `S1` ↔ `S1.01` je **celok a časť**, a na to má schéma dve cesty:
vnorenú skupinu cez `IfcRelAssignsToGroup` (*„grouping arbitrary objects
within a group, including other groups… in a recursive manner"*) alebo
`IfcRelAggregates` (`IfcBuiltSystem`: *„inherits IsDecomposedBy pointing
to IfcRelAggregates. It provides the hierarchy between the separate
(partial) building systems"*).

Zvolená **agregácia**: `Decomposes : SET [0:1]` schémou vynúti, že
`S1.01` patrí práve jednej skladbe — omyl „to isté dieťa pod S1 aj S2"
sa nedá zapísať. `IfcRelAggregates` má jediné pravidlo `NoSelfReference`
a žiadne informal propositions.

Pravidlo nosiča
---------------
**Výskyt = (skladba, podlažie nosiča).** Nosič kotviaceho prvku je koreň
jeho agregácie, ak je agregovaný, inak prvok sám.

Nosič robí dve veci: dá výskytu podlažie (krytina agregovaná do strechy
dostane podlažie strechy, nie svoje vlastné) a pomenuje ho.

Prečo nie jemnejšie: nosičom `S4` sú štyri steny, ale tvoria dva výlezy
— po stenách by to bolo rozdrobenie. Prečo nie hrubšie: samotné podlažie
prvku by strešné súvrstvie roztrhalo, lebo podhľady `PH01` sú
kontajnované v miestnostiach 3NP, hoci patria k streche nad 4NP.

Rozklad musí byť úplný a disjunktný
-----------------------------------
Zjednotenie detí sa porovnáva s pôvodným členstvom rodiča a deti sa
kontrolujú na prienik. Ak sa čokoľvek nezhoduje, krok **zastane** —
zmena je rafinácia existujúcich skupín, nie ich preskupenie.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

import spatial  # noqa: E402
# Whitelist osirelých sa neopisuje. Staršie kroky ho majú skopírovaný a od
# fázy 17 je zastaraný — `IfcMaterialProperties` v ňom chýba, takže by tu
# ohlásili 15 sirôt z cudzieho kroku. `gate.py` importuje z testov rovnako.
from tests.test_invariants import ORPHAN_WHITELIST, SKLADBA_PARENT  # noqa: E402

IN = os.path.join(ROOT, "out", "ASR_v27.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v28.ifc")

DRY_RUN = True

#: šírka poradového čísla výskytu; `S1.01`, nie `S1.1`
INST_WIDTH = 2

#: Hĺbka pásma pod značkovou vrstvou (mm), prevzatá z fázy 8b, kde bola
#: zvolená z citlivostnej skúšky. Tu ju kontrola úplnosti **pripne**:
#: pri 1200 vypadnú z `S1`, `S2` aj `S6` po dvoch prvkoch a pri 1500 po
#: jednom, takže krok zastane; pri 2000 a 3000 vyjde to isté. Meniť ju
#: teda netreba a ani sa nedá bez toho, aby sa rozklad rozišiel s tým,
#: čo skupina dnes má. Skúšku zopakuje `--hlbka`.
HLBKA = 2000.0

#: skladby, ktorých členstvo priradila geometria (fáza 8b):
#: skupina → (značkový kód, zdieľané kódy v pásme)
GEOM = {
    "S1": ("ST01.20", ("ST01.10", "SD02", "PH01")),
    "S2": ("ST01.21", ("ST01.10", "SD02", "PH01")),
    "S6": ("PD03.30", ("SD02", "PH01")),
}

DESC = ("Výskyt skladby na jednom nosiči. Nosič je koreň agregácie "
        "kotviaceho prvku, inak prvok sám; výskyt je daný jeho podlažím.")


# --------------------------------------------------------------------------
# nosič
# --------------------------------------------------------------------------


def nosic(e):
    """Koreň agregácie prvku; neagregovaný prvok je nosičom sám sebe.

    `28_layer_sets.py:156-158` robí jediný skok nahor, čo pri ETICS stačí.
    Tu treba plný koreň — krytina strechy visí na `IfcRoof`, ktorá sama
    už agregovaná nie je, ale spoliehať sa na hĺbku 1 by bolo krehké.
    """
    seen = {e.id()}
    while getattr(e, "Decomposes", None):
        parent = e.Decomposes[0].RelatingObject
        if parent.id() in seen:                 # cyklus — schéma ho nezakazuje
            break
        seen.add(parent.id())
        e = parent
    return e


def podlazie(e):
    """Podlažie nosiča prvku. `IfcSpace` sa prejde na jeho podlažie."""
    return spatial.storey_of(spatial.container_of(nosic(e)))


# --------------------------------------------------------------------------
# rozklad
# --------------------------------------------------------------------------


def rozklad_geom(cleny, znacka, kody, box, hlbka):
    """Rozklad skladby so značkovou vrstvou — pásmový test **per nosič**.

    Kandidáti sa berú z členov rodiča, nie z celého modelu. Tým je
    výsledok podmnožinou pôvodnej skupiny už z konštrukcie a kontrola
    úplnosti meria len to, či sa niečo nestratilo.
    """
    znacky = [e for e in cleny
              if (e.Name or "").startswith(znacka) and e.GlobalId in box]
    if not znacky:
        raise SystemExit("STOP: značka %s nemá ani jeden prvok s geometriou" % znacka)
    kandidati = [e for e in cleny
                 if (e.Name or "").startswith(tuple(kody)) and e.GlobalId in box]

    po_nosicoch = collections.defaultdict(list)
    for e in znacky:
        po_nosicoch[nosic(e).id()].append(e)

    out = {}
    for zn in po_nosicoch.values():
        st = podlazie(zn[0])
        vysk = out.setdefault(st, {"nosice": {}, "cleny": {}})
        for e in zn:
            vysk["nosice"][nosic(e).id()] = nosic(e)
            vysk["cleny"][e.id()] = e
        boxy = [box[e.GlobalId] for e in zn]
        for e in kandidati:
            eb = box[e.GlobalId]
            for zb in boxy:
                if spatial.xy_inter(eb, zb) <= 0:
                    continue
                if eb[5] >= zb[2] - hlbka and eb[2] <= zb[5]:
                    vysk["cleny"][e.id()] = e
                    break
    return out


def rozklad_kod(cleny):
    """Rozklad skladby s kódovým členstvom — podľa podlažia nosiča.

    Pri ETICS je členom aj krytina, aj jej substrátová stena. Krytina má
    za nosiča tú istú stenu, takže obe padnú do toho istého výskytu.
    """
    out = {}
    for e in cleny:
        vysk = out.setdefault(podlazie(e), {"nosice": {}, "cleny": {}})
        vysk["nosice"][nosic(e).id()] = nosic(e)
        vysk["cleny"][e.id()] = e
    return out


def poradie(model):
    """`{id podlažia: index}` podľa `Elevation` — kľúč číslovania výskytov."""
    storeys = sorted({s.id(): s for s in model.by_type("IfcBuildingStorey")}.values(),
                     key=lambda s: (s.Elevation if s.Elevation is not None else 0.0))
    return {s.id(): i for i, s in enumerate(storeys)}


def popis_nosicov(nosice):
    """Nosiče výskytu do `Description`, najviac tri menovite."""
    mena = sorted("%s %s" % (n.is_a().replace("Ifc", ""), n.Name or "?")
                  for n in nosice)
    if len(mena) <= 3:
        return ", ".join(mena)
    return "%s a ďalších %d" % (", ".join(mena[:3]), len(mena) - 3)


# --------------------------------------------------------------------------


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
    removed: list[str] = []

    rodicia = [g for g in m.by_type("IfcGroup")
               if g.is_a() == "IfcGroup" and SKLADBA_PARENT.match(g.Name or "")]
    if not rodicia:
        raise SystemExit("STOP: v modeli nie je ani jedna skupina skladby S<n>")
    rodicia.sort(key=lambda g: int(g.Name[1:]))

    hotove = [g.Name for g in rodicia if g.IsDecomposedBy]
    if hotove:
        print("už rozložené: %s — skript je idempotentný, končí" % ", ".join(hotove))
        if len(hotove) != len(rodicia):
            raise SystemExit(
                "STOP: rozložených je len %d z %d skladieb (%s). Model je "
                "v polovici kroku, dokončiť sa nedá bezpečne."
                % (len(hotove), len(rodicia),
                   ", ".join(g.Name for g in rodicia if not g.IsDecomposedBy)))
        return 0

    # členstvo rodičov ešte pred akoukoľvek zmenou — je to referencia úplnosti
    povodne = {}
    for g in rodicia:
        cleny = []
        for rel in (g.IsGroupedBy or ()):
            cleny.extend(rel.RelatedObjects)
        if not cleny:
            raise SystemExit("STOP: %s nemá ani jedného člena" % g.Name)
        povodne[g.Name] = {e.id(): e for e in cleny}

    # bboxy len pre skladby, ktoré ich potrebujú
    treba_box = set()
    for kod in GEOM:
        treba_box.update(povodne.get(kod, {}).values())
    box = spatial.boxes(m, [e for e in treba_box if e.Representation is not None])

    order = poradie(m)
    # OwnerHistory je od IFC4 nepovinná; ak ju rodič nemá, prevezme sa
    # z ktoréhokoľvek jeho člena, nie z natvrdo menovanej skladby
    owner = rodicia[0].OwnerHistory or next(
        iter(povodne[rodicia[0].Name].values())).OwnerHistory

    # ---- výpočet rozkladu -----------------------------------------------
    plan = {}
    for g in rodicia:
        cleny = list(povodne[g.Name].values())
        if g.Name in GEOM:
            znacka, kody = GEOM[g.Name]
            vyskyty = rozklad_geom(cleny, znacka, kody, box, args.hlbka)
        else:
            vyskyty = rozklad_kod(cleny)

        for st in vyskyty:
            if st is None:
                raise SystemExit(
                    "STOP: %s — nosič bez podlažia, výskyt sa nedá pomenovať" % g.Name)

        # číslovanie podľa podlažia, kľúčom je Elevation
        usporiadane = sorted(vyskyty.items(),
                             key=lambda kv: (order.get(kv[0].id(), len(order)),
                                             kv[0].Name or ""))
        plan[g.Name] = [(i + 1, st, v) for i, (st, v) in enumerate(usporiadane)]

    # ---- kontrola úplnosti a disjunktnosti -------------------------------
    chyby = []
    for g in rodicia:
        cely = set(povodne[g.Name])
        zjednotenie: set[int] = set()
        for i, st, v in plan[g.Name]:
            spolocne = zjednotenie & set(v["cleny"])
            if spolocne:
                chyby.append("%s: výskyt .%02d zdieľa %d prvkov s predošlým (%s)"
                             % (g.Name, i, len(spolocne),
                                ", ".join(sorted(m.by_id(x).Name or "?"
                                                 for x in list(spolocne)[:5]))))
            zjednotenie |= set(v["cleny"])
        chyba = cely - zjednotenie
        navyse = zjednotenie - cely
        if chyba:
            chyby.append("%s: %d prvkov vypadlo z rozkladu (%s)"
                         % (g.Name, len(chyba),
                            ", ".join(sorted(m.by_id(x).Name or "?"
                                             for x in list(chyba)[:5]))))
        if navyse:
            chyby.append("%s: %d prvkov pribudlo, ktoré v skupine neboli"
                         % (g.Name, len(navyse)))

    # ---- výpis ------------------------------------------------------------
    print("ROZKLAD")
    for g in rodicia:
        cely = len(povodne[g.Name])
        print("  %-3s %-52s %3d prvkov → %d výskytov"
              % (g.Name, (g.Description or "").split(" — ")[0][:52], cely,
                 len(plan[g.Name])))
        for i, st, v in plan[g.Name]:
            rozpad = collections.Counter((e.Name or "")[:7] for e in v["cleny"].values())
            print("        %s.%s  %-6s %3d prvkov  nosič %s"
                  % (g.Name, str(i).zfill(INST_WIDTH), st.Name,
                     len(v["cleny"]), popis_nosicov(v["nosice"].values())))
            print("                %s" % dict(rozpad))

    if chyby:
        print("\nROZKLAD NESEDÍ")
        for c in chyby:
            print("  " + c)
        raise SystemExit("STOP: rozklad nie je úplný a disjunktný, nič sa nemení")
    print("\n  kontrola: rozklad je úplný a disjunktný pri všetkých %d skladbách"
          % len(rodicia))

    # ---- zápis ------------------------------------------------------------
    for g in rodicia:
        nazov = (g.Description or g.Name or "").split(" — ")[0]
        deti = []
        for i, st, v in plan[g.Name]:
            meno = "%s.%s" % (g.Name, str(i).zfill(INST_WIDTH))
            dieta = m.create_entity(
                "IfcGroup", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                Name=meno,
                Description="%s, výskyt na podlaží %s — nosič %s. %s"
                            % (nazov, st.Name, popis_nosicov(v["nosice"].values()), DESC))
            rel = m.create_entity(
                "IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=owner,
                RelatedObjects=tuple(v["cleny"].values()), RelatingGroup=dieta)
            added.extend([dieta.GlobalId, rel.GlobalId])
            deti.append(dieta)

        agg = m.create_entity(
            "IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            RelatingObject=g, RelatedObjects=tuple(deti))
        added.append(agg.GlobalId)

        # rodič stráca priame členstvo — členovia sú odteraz len na deťoch.
        # Prázdny `IfcRelAssignsToGroup` by porušil invariant 5, preto sa
        # maže celý vzťah, nie len jeho obsah.
        for rel in list(g.IsGroupedBy or ()):
            removed.append(rel.GlobalId)
            m.remove(rel)

    siroty = [e for e in m if not m.get_total_inverses(e)
              and not any(e.is_a(w) for w in ORPHAN_WHITELIST)]
    if siroty:
        raise SystemExit("STOP: krok vyrobil %d osirelých entít: %s"
                         % (len(siroty), collections.Counter(e.is_a() for e in siroty)))
    print("  kontrola inv 4: 0 osirelých")
    print("  GlobalId nových: %d, zmazaných: %d" % (len(added), len(removed)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed)), "added": sorted(set(added))},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
