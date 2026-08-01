# _Instructions — pravidlá pre claude.ai projekt (IFC štúdium)

> Metasúbor pre Project Knowledge claude.ai projektu. Poznámky sa od 1. 8. 2026 pushujú do vaultu **AssetinSpace/ObsidianPKM**, nie sem — v tomto repe sa udržiava už len `Glossary.md`. Po každej zmene tohto súboru treba jeho obsah ručne skopírovať do Project Knowledge v claude.ai (projekt to samo nespraví).

---

## Push workflow

1. Fine-grained GitHub token je uložený v Project Knowledge. **Scope tokenu musí zahŕňať `AssetinSpace/ObsidianPKM`** (Contents: Read and write) — pôvodný token obmedzený len na IFCstudy treba rozšíriť/nahradiť; na úpravy `Glossary.md` je ďalej potrebný aj scope na IFCstudy.
2. Pokyn typu *„pushni X do vaultu"*: naklonovať `AssetinSpace/ObsidianPKM` do sandboxu, vytvoriť/upraviť MD podľa pravidiel nižšie, commit + push cez HTTPS s tokenom (SSH port 22 je blokovaný), token po pushi odstrániť z remote URL.
3. Pred pushom si prečítať `CLAUDE.md` v koreni vaultu — je to záväzná schéma; pri konflikte s týmto súborom platí `CLAUDE.md`.
4. Úpravy slovníka (`Glossary.md`) sa pushujú naďalej do **IFCstudy**.

## Kam a ako zapisovať poznámky

Nové poznámky idú do `10_Notes/` s týmto frontmatterom (presne toto poradie polí):

```yaml
---
aliases:
kind: pojem        # entita IfcXxx → pojem; prierezová téma/rozhodnutie → synteza
status: draft      # vždy draft — na done prepína len človek
topics:
  - "[[IFC]]"      # vždy; ďalšie podľa obsahu ([[BIM]], [[buildingSMART]]…)
resource:
  - "[[buildingSMART IFC 4.3 dokumentácia]]"
locator: "8.3.3.2" # kapitola z ifc43-docs; len pri pojme, ak je známa
origin: ai
verified:
---
```

- **Entita** (`IfcSpace.md` — názov = presný PascalCase názov entity): telo `## Schema fakty` (prvý bod „Zdroj pravdy:" s linkom na lexical stránku), voliteľne `## Praktický zápis (ifcopenshell.api…)`, `## Otvorené otázky / poznámky`, `## Súvisiace`.
- **Téma** (`kind: synteza`, názov **bez** prefixu „Téma - "): `## Problém` → analýza s normatívnym zdôvodnením → **`## Ako sme na to prišli`** (povinné: 2–5 viet, zlomové body úvahy vrátane omylov) → `## Otvorené / na overenie` → `## Zdroje` (Primárne/Sekundárne) → `## Súvisiace`.
- Wikilinky medzi poznámkami ako doteraz; na slovník **markdown linkom** `[Glossary](https://github.com/AssetinSpace/IFCstudy/blob/main/Glossary.md)`, nie wikilinkom.
- Existujúcu poznámku pri návrate k téme dopĺňať, nie zakladať duplikát. Prázdny súbor je vo vaulte zakázaný stav — na neexistujúci cieľ stačí wikilink.

### Názvy súborov (vault sa synchronizuje Windows + iPhone)

Max ~150 znakov / 200 bajtov UTF-8; zakázané `: / \ | # ^ [ ] * ? " < >`; diakritika v NFC; žiadne koncové/dvojité medzery, žiadne emoji.

---

## IFC Reference Authority

Jediný autoritatívny zdroj pre IFC schému: **https://ifc43-docs.standards.buildingsmart.org/**

1. Pred odpoveďou o IFC vždy fetchnúť príslušnú stránku — nespoliehať sa na trénovacie dáta.
2. URL vzory: entita `…/IFC/RELEASE/IFC4x3/HTML/lexical/[EntityName].htm`; kapitoly `…/HTML/chapter-5/`…`chapter-8/`; concepts `…/HTML/concepts/content.html`; Annex A/B/C `…/HTML/annex-a.html` atď.
3. Citovať presne — rozlišovať normatívny text od vlastnej interpretácie.
4. Blogy, fóra a vendor dokumentáciu (Revit, ArchiCAD…) nikdy necitovať ako schema autoritu — len ako označené implementačné príklady (`⚠️ vendor, nie spec`).
5. Ak stránka nejde fetchnúť, uviesť to výslovne a navrhnúť navigačnú cestu.

## Jazykové pravidlá (SK/CZ)

- Primárny zdroj prekladov je `Glossary.md` v tomto repe — používa sa len odsúhlasený preklad; návrh bez odsúhlasenia sa značí `⚠️ NEPOTVRDENÉ`.
- SK termín pri SK kontexte, CZ pri CZ; ak trh nie je jasný: *Sada výmer (SK) / Sada výměr (CZ)*.
- Nový termín: navrhnúť preklad do oboch jazykov a upozorniť — nikdy nevymýšľať potichu.
- Anglický IFC termín vždy v pôvodnom tvare (*Quantity Set*, `IfcWall`); preklad je doplnok.

## Kontext autora

BIM konzultant (Sustainable Building Design; Asset Management, Digital Twins, FM, CDE, CAFM). Poznámky prepájať s týmito doménami; referenčný model `Office_centrum_Brno.ifc`, vlastný nástroj AIMviewer.
