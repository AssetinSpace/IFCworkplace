# OCB — štart v Claude Code

## Východiskový súbor

**Pokračuj z `ASR_final_v2.ifc`.**

| súbor | rola |
|---|---|
| `data/ASR.ifc` | **nemenný zdroj.** Nikdy sa neprepisuje. Referencia pre kontrolu geometrie |
| `out/ASR_final.ifc` | výstup pôvodnej pipeline (kroky 1–12) |
| `out/ASR_final_v2.ifc` | + oprava #C. **Vstup fázy 1** |

Revit nie je dostupný, takže model sa už nebude re-exportovať. Tým padá pôvodná
obava, že sa fixy stratia pri ďalšom exporte — ale **poradové číslovanie krokov
zostáva**, lebo pipeline musí byť reprodukovateľná od `ASR.ifc`.

```
ASR.ifc
 1–12  pôvodná pipeline            → ASR_final.ifc
 13    fix_spacetypes.py     #C    → ASR_final_v2.ifc   ✅ hotové
 14–37 fázy 1–18                   → ASR_v3.ifc … ASR_v25.ifc
 38    fáza 19  #BC                → ASR_v26.ifc
 39    fáza 20  #BD                → ASR_v27.ifc
```

Aktuálny výstup je **`out/ASR_v27.ifc`**.

## Štruktúra repozitára

```
/
├─ AUDIT.md                  ← register, rozhodnutia, plán
├─ BEP_ANNEX.md              ← SNIM rozšírenia + odchýlky od IFC vzoru
├─ decisions/                ← ADR na položku
├─ src/                      ← kroky pipeline, číslované
├─ tests/
│  ├─ test_geometry.py
│  ├─ test_schema.py
│  └─ test_invariants.py
├─ data/                     ← ASR.ifc, snim_mapovanie.csv, výkresy PDF
└─ out/                      ← medzivýstupy, v .gitignore
```

## Invarianty po každom kroku

Toto je jadro. Pôvodný handover tvrdil 0 osirelých entít a konvertovaný
`Status` — obe nepravdivé, lebo kontrola merala zámer.

1. **Geometria** — bboxy všetkých `IfcBuiltElement` a `IfcSpace` sa zhodujú
   s `ASR.ifc` na 6 desatinných miest, okrem GUID v allowliste kroku.
2. **EXPRESS** — `validate(express_rules=True)` = 0 hlásení.
3. **GUID účtovníctvo** — každý stratený a nový GUID vysvetlený
   v očakávaniach kroku. Žiadne duplicity.
4. **Osirelé entity** — 0, s whitelistom `IfcShapeAspect`,
   `IfcMaterialDefinitionRepresentation`, `IfcPresentationLayerAssignment`,
   `IfcMapConversion`, `IfcRelationship`.
5. **Prázdne povinné agregácie** — 0.
6. **Jednoznačnosť** — plný SNIM kód occurrence je unikátny;
   `Types : SET [0:1]` na každý typ.
7. **Kontajnment vs agregácia** — žiadny prvok nie je súčasne `Decomposes`
   aj `ContainedInStructure`.
8. **Priestorové zaradenie sedí s geometriou** — prvok leží v pásme
   podlažia, v ktorom je zaradený (aspoň polovicou výšky), a geometricky
   zhodné prvky sú v jednom podlaží. Pásmo podlažia sa počíta z **vrchu
   nosnej dosky**, nie z `Elevation` — `Elevation` je čistá podlaha, prvky
   podlažia začínajú 150 mm pod ňou. Pribudol po fáze 19; AUDIT.md §41.

Invariant 6 dnes **zámerne zlyháva** na `DD01.05.01` a `.02`. Nechaj ho zlyhať;
opraví sa vo fáze 4. Invariant 7 bude najviac namáhaný po fázach 1, 6 a 7.

Testy 1, 2, 4, 5 a 8 v CI. Test 1 na 2564 tvarov trvá jednotky minút,
test 8 počíta obálky všetkých kontajnovaných prvkov — obidva nech bežia
na merge, nie na každý commit.

## Pravidlá pre skripty

- `DRY_RUN = True` default
- vstup sa neprepisuje, výstup je nový súbor
- idempotentné: druhý beh nič nezmení a ohlási to
- atribúty entity čítaj **pred** `model.remove()`
- `for x in list(model.by_type(...))` — nemutuj kolekciu počas iterácie
- entity porovnávaj cez `.id()`, nie `is`
- `reassign_class` na occurrence kaskádovo prepíše zdieľaný typ — pred zmenou
  triedy prvok od typu odpoj
- `geom.iterator`, nie opakované `geom.create_shape`
- shape z `create_shape` **drž v premennej**. `np.array(create_shape(...).geometry.verts)`
  v jednom výraze číta pamäť dočasného objektu, ktorý medzitým zanikne —
  výsledkom sú nuly a hodnoty rádu `1e260`, nie výnimka
- `MERGE_IDENTICAL_MAPS` zostáva natrvalo `False`
- `geom.create_shape` vracia metre, súbor je v milimetroch
- **bbox nie je teleso.** Bbox kuchynky prekrýva bbox openspace, bbox
  openspace obsahuje pôdorys každého WC. Otázka „je bod v miestnosti" sa
  odpovedá lúčom cez trojuholníky obalu — `spatial.point_in_mesh`, nie
  pôdorysným prekryvom
- **tolerancia nesmie byť väčšia než to, čo má oddeľovať.** 300 mm
  tolerancia priľahlosti preskočila 250 mm nosnú dosku a dala skladbu
  podlahy 3NP miestnosti na 2NP (AUDIT.md §40)

## Prvý prompt

> Prečítaj `AUDIT.md`. Pracujeme na fáze 1 — triedny model.
>
> Vstup `out/ASR_final_v2.ifc`, výstup `out/ASR_v3.ifc`. `data/ASR.ifc` sa
> nikdy neprepisuje.
>
> Najprv napíš `tests/test_invariants.py` podľa §„Invarianty" v tomto súbore
> a over ho proti `ASR_final_v2.ifc`. Musí prejsť všetko okrem invariantu 6,
> ktorý zlyhá na `DD01.05.01` a `.02` — to je očakávané.
>
> Potom `src/14_fix_classes.py` podľa rozhodnutí 8, 10, 12, 13, 14, 15
> z `AUDIT.md` §2. `DRY_RUN` default. Nekomituj, kým nemám výstup dry-runu.

## Poradie a čo nerobiť naraz

Fázy 1–3 menia triedy, typy a mená. Nepúšťaj ich spolu — keď sa niečo pokazí,
nebudeš vedieť čo. Fáza za fázou, commit za commitom, po každom testy.

Fázy 6 a 7 sú najrizikovejšie: prepájajú agregácie a menia kontajnment.
Tam pusť invariant 7 na každý commit, nie až na merge.

## Rozdelenie nástrojov

| kde | čo |
|---|---|
| **Claude Code** | všetky fázy pipeline, testy, CI, git |
| **Cowork** | metodická časť diplomovky, `BEP_ANNEX.md`, ADR záznamy |
| **chat** | rozsudzovanie proti ifc43-docs pri otázke „je toto podľa schémy správne" |
