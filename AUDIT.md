# OCB — audit, rozhodnutia a plán opravy

Nahrádza pôvodný handover a všetky predchádzajúce verzie tohto dokumentu.
Vzniklo nezávislým overením každého tvrdenia pôvodného handoveru proti
`ASR.ifc` a `ASR_final.ifc` (`ifcopenshell` 0.8.5) a konfrontáciou modelu
s projektovou dokumentáciou.

## 0. Rámec

**Vstupný súbor:** `ASR_final_v2.ifc`

**K dispozícii máme len IFC súbory, výkresy a Clauda.** Revit nie je dostupný.
SNIM excel `MOC_BEP_05` **neexistuje**. To mení dve veci oproti pôvodnému §7:

1. **Autoritou pre `IFCclass` a `PredefinedType` už nie je excel**, ale
   projektová dokumentácia a rozhodnutia Samuela. Každé rozhodnutie o triede
   ide do BEP s odôvodnením zo špecifikácie alebo z výkresu.
2. **Kategória „patrí do Revitu" zaniká.** Každá vada sa buď opraví v IFC,
   alebo sa zdokumentuje ako známa medzera. Nefabrikujeme geometriu, ktorá
   v modeli nie je.

**Autoritatívne podklady:**

| dokument | čo určuje |
|---|---|
| `D.1.1.09 Výpis skladieb` | zloženie skladieb S1–S9, hrúbky, funkcie vrstiev |
| `D.1.1.08 Členenie LOP` | delenie fasády na polia `[písmeno][číslo]-[orientácia]` |
| `3 – Tepelná technika LOP` | `Ucw`, rozmery a plochy 48 polí, Σ 1603.63 m² |
| `D.1.1.07 Technické pohľady` | kódy prvkov v pohľadoch |
| `D.1.1.01 Pôdorys 1NP` | legenda miestností (autorita pre plochy 1NP) |
| `snim_mapovanie.csv` | ručné priradenie SNIM kódov k 17 Revit typom |

Jediný autoritatívny zdroj pre IFC schému:
<https://ifc43-docs.standards.buildingsmart.org/> — fetchnúť pred odpoveďou,
necitovať z trénovacích dát.

---

## 1. Čo z pôvodného handoveru platí

Overené, nerobiť znova: EXPRESS validácia 0 hlásení; geometria nedotknutá
(2495 `IfcBuiltElement`, 0 zmenených bboxov, 0 stratených tvarov); GlobalId
účtovníctvo sedí do kusa; dedup typov bez chyby (0 typov s >1 rel, 0
`IfcMappedItem` mimo vlastných máp); `Reference` 0×; prázdne psety 0; SNIM na
2645/2645 occurrences; `IfcSpatialZone` správne deklarované a viazané;
1NP 23 miestností, 613.55 m².

---

## 2. Rozhodnutia

### Názvoslovie a SNIM

| # | vec | rozhodnutie | opora |
|---|---|---|---|
| 1 | 17 kódov bez UOT | zostávajú dvojúrovňové, INST hneď za kód | Samuel |
| 2 | výplň INST | pevná šírka 4 (`LP02.0001`) | Samuel |
| 3 | INST na typoch | **nie** | `IfcTypeObject` je „spoločný pre všetky occurrences", `IfcTypeProduct` „bez umiestnenia" |
| 4 | `LOP02` | → **`LP02`**. Rodina: `LP01` krídlo okna, `LP02` príčeľ, `LP03` akustická zástena | Samuel |
| 6 | dvere UOT 04/05 | swap **len na 3NP**; 2NP je správne; 2 sklenené z `DD01.05` → `DD01.04` (rieši aj duplicitu #AP) | dáta |
| 7 | krídlovosť dverí | do `Description` | Samuel |
| — | INST počítadlo | po kóde globálne, poradie z geometrie: podlažie → Y → X → Z, zaokrúhlenie 10 mm | Samuel |
| — | základový blok | **`ZD02.05`**, „Základový blok pod schodiskom". Rad `ZD02` zostáva: `.01`–`.04` dosky, `.05` blok | Samuel |

### Triedny model

| # | vec | rozhodnutie | opora |
|---|---|---|---|
| 8 | `IH01.01` | `IfcCovering / MEMBRANE` | `MEMBRANE` = „nepriepustná vrstva… hydroizolačný materiál" |
| 9 | atika | do `SN02.01` idú **zvislé** vrstvy `ST01.32`, OSB `ST01.31` a oplechovanie `KV01` (18 dielov); **vodorovné** `ST01.30` ide do strechy. `SN02.01` dostane `PARAPET` | `IfcRelCoversBldgElements` DEPRECATED → `IfcRelAggregates` |
| 10 | `ST01.31` OSB | `IfcCovering / TOPPING` | `TOPPING` = „vrstva na vyrovnanie povrchu" |
| 11 | strecha | dve `IfcRoof / FLAT_ROOF` — **4NP 65, 5NP 10** (pôvodne uvedené 73/19 rátalo aj vrstvy atiky, ktoré si nárokuje #9; `Decomposes` je `SET[0:1]`) | geometria |
| 12 | `ZD02.01` | `IfcSlab` je správne pomenovaný → premenovať **typ** `ZD02.04` → `ZD02.01`; `ZD02.03/.04` → `BASESLAB`; blok → `ZD02.05` `IfcFooting / PAD_FOOTING` | „základové dosky sa neinštancujú ako `IfcFooting`, ale ako `IfcSlab / BASESLAB`" |
| 13 | `SN11.01/.02` | zostáva `IfcWall`, doplniť `PARTITIONING` | test „nie je prevažne zvislý → `IfcPlate`" neplatí |
| 14 | `KV01` | `IfcCovering / COPING` | `COPING` = „ochranné zakončenie steny či atiky" |
| 15 | `PredefinedType` 383× | doplniť z popisov podľa tabuľky §5 | dokumentácia + schéma |
| 20 | tretie `SC01` (3NP) | prekódovať na `SD03`/`SD04`, dotypovať. `SH04.03` (nerez + drevo, 4NP→5NP) **nechať** | geometria a materiály |
| AO | fasádne zateplenia | `IfcRelAggregates` do pokrývanej steny, odobrať z kontajnmentu | tá istá deprecation ako #9 |

### Typy a identita

| # | vec | rozhodnutie |
|---|---|---|
| 17 | `OK01` | zlúčiť 25 typov do jedného, prevziať 50 `RepresentationMaps` |
| 18 | fasáda | **kód = výrobok**, rozmer nesie geometria a `Qto` |
| 19 | `LP01` | 125 `IfcPlate` → `OK01.0001`–`.0126`; 26 `IfcWindow` → `LP01.0001`–`.0026`; typy `LP01.44`/`.69` zlúčiť |

### Priestory

| # | vec | rozhodnutie |
|---|---|---|
| 21 | 14 MEP priestorov | **prerobiť na riadne miestnosti**, nemazať. Prečíslovať a pomenovať podľa tabuľky §6 |
| 22 | typová vrstva priestorov | žiadna — po oprave #C sú všetky netypované a je to konzistentné |
| 23 | `IfcRelSpaceBoundary` | **1. úroveň, bez `ConnectionGeometry`** + `ParentBoundary` pre dvere a okná |
| 24 | krok 10 nanovo | do miestností `IfcCovering`, `IfcFlowTerminal`, `IfcSanitaryTerminal`, `IfcFurniture`, `IfcRailing`; **so Z-filtrom**. Dvere a steny nie — kontajnment je exkluzívny |
| — | energetické zónovanie | **mimo rozsah.** Tým padá aj `IfcRelSpaceBoundary` 2. úrovne |
| — | šachty na 1NP | v rozsahu. **Výťahové šachty sa nekreslia**, len inštalačné. Pôdorys sa neodhaduje — orezáva sa z existujúceho otvoru, viď §14 | Samuel |
| — | #Q zóna pre 3NP | **vnorený `IfcZone`** s 11 nájomnými priestormi 3NP, vložený do `IfcZone` `Pronajmutelné`. Žiadna geometria — `IfcZone` ju niesť nemôže | Samuel + spec |

### Materiály a skladby

| # | vec | rozhodnutie | opora |
|---|---|---|---|
| 27 | konštituenty bez väzby | **zmazať 117 occurrence setov** (91 `IfcDoor` + 26 `IfcWindow`), zdediť typové. Overené: všetkých 117 má funkčný typový set. Terminály (41) a zábradlia (4) nechať | occurrence asociácia prebíja typovú |
| — | skladby | `IfcMaterialLayerSet` **na typoch**; `IfcMaterialLayerSetUsage` len tam, kde hrúbka sedí | „Usage je pre prvky s konštantnou hrúbkou"; „`TotalThickness` musí byť rovná hrúbke prvku" |
| — | agregácia vrstiev | **len pri fyzicky zviazaných vrstvách** (viď test §4) | agregácia je vzťah celok–časť |
| — | kódy S1–S9 | **`IfcGroup`** + `IfcRelAssignsToGroup`. Nie `IfcRelAssociatesDocument`, nie `IfcClassification` | Samuel |
| — | vzduchová medzera | nemodeluje sa; `IsVentilated` platí len vnútri jedného prvku. Rozdiel v súčte hrúbok sa dokumentuje | schéma |
| — | fyzika materiálov (λ, ρ, c, μ) | samostatná fáza neskôr | Samuel |

### Fasáda LOP

| vec | rozhodnutie |
|---|---|
| 48 polí | vnorený `IfcCurtainWall` pod existujúcich 12 `PL01`. Legálne, ale nedokumentované → **do BEP ako odchýlka** |
| názvy polí | `E3-V` atď. z výkresu `D.1.1.08` |
| `Ucw` a plochy | `Pset_CurtainWallCommon.ThermalTransmittance` + `Qto_CurtainWallQuantities` |

### Hotové

| # | vec |
|---|---|
| C | dva prázdne `IfcSpaceType` s enum literálmi v `Name` zmazané → `ASR_final_v2.ifc` |

---

## 3. Register vád

**O** otvorené, **H** hotové, **D** zdokumentovať (nedá sa opraviť bez Revitu), **V** AIM Viewer.

### Strata a nekonzistencia dát
| # | | vec |
|---|---|---|
| A | **H** | ~~28 prvkov stratilo `Status`~~ — vrátené do `Pset_CoveringCommon`, `70d17af`. Pôvodne: — presne množina `IfcWall → IfcCovering` (`FS03.01` 9, `ST01.32` 8, `FS01.10` 4, `FS01.11` 4, `FS01.12` 3) |
| B | **H** | ~~17 `IfcSlab` nesie `Pset_WallCommon`~~ → `Pset_SlabCommon`, `70d17af` |
| C | **H** | ~~`IfcSpaceType` = `NOTDEFINED` / `USERDEFINED`~~ |
| E | **H** | ~~`Pset_SpaceCommon` na 10 `IfcSpatialZone`~~ → `Pset_SpatialZoneCommon`, `70d17af` |
| F | **H** | ~~48 osirelých entít~~ — zametené vo fáze 9b, 48 koreňov a 204 entít v kaskáde, 0 zrušených `GlobalId`. Invariant 4 odvtedy prechádza |
| AY | O | `#16` `IfcGeometricRepresentationSubContext` „Box" nepoužitý (0 reprezentácií). Má 0 inverzov, lebo väzbu na rodiča drží **dopredný** `ParentContext`, nie inverzný `HasSubContexts` — do whitelistu invariantu 4 patrí alebo sa má zmazať |
| AJ | **H** | ~~2653 hodnôt s FP šumom~~ — fáza 9a, zaokrúhlené na 6 desatinných miest. Opravených **15135** (širšie kritérium než pôvodný odhad), najväčšia oprava 5e-07 |

### Triedny model
| # | | vec |
|---|---|---|
| T | **H** | ~~`ST01.*` vrstvy skladby vedené ako `IfcRoof`~~ — 92 vrstiev + 10 typov na `IfcCovering`, `50c26c5` |
| V | **H** | ~~36 prázdnych `IfcRoof` obalov 1:1 nad `IfcSlab`~~ — zrušené, `50c26c5` |
| AL | **H** | ~~`IH01.01` ako `IfcWall / STANDARD`~~ → `IfcCovering / MEMBRANE`, 4 occ + typ, `45ea35d` |
| AB | **H** | ~~blok 0.41×1.25×0.30 ako `IfcStair`~~ → `IfcFooting / PAD_FOOTING`, `ZD02.05`, `45ea35d` |
| AC | **H** | ~~`ZD02.03/.04` `FLOOR`; occurrence `ZD02.01` typovaná `ZD02.04`~~ — typ premenovaný, `BASESLAB`, `45ea35d` |
| AM | O | `PredefinedType` — steny hotové (`45ea35d`): 159 occ podľa §5 + všetkých 12 `IfcWallType`. Číslo 383 = **314** `NOTDEFINED` + **69** `IfcFlowTerminal`, ktoré atribút v IFC4X3 nemajú vôbec (fáza 10). Otvorených ostáva **67** occurrences bez pravidla v §5: 8 `IfcSlab DZ02`, 19 `IfcCurtainWall`, 22 `IfcFurniture`, 12 `IfcRailing`, 5 `SC01`. **Odmerané na `ASR_v17.ifc` (§29):** 114 = 67 `IfcCurtainWall` (uzavreté schémou, §25) + 22 `IfcFurniture` + 12 `IfcRailing` + 8 `IfcSlab` + 3 `IfcStair` + 2 `IfcStairFlight`. §25 uvádzalo 21 `IfcFurniture` — chýbal v ňom `ZV04.01`. Rozhodnutia sú v §29. **Fáza 11 (§30) uzavrela 30 z nich** prekvalifikovaním — 114 → 84 bez `PredefinedType`, z toho 67 `IfcCurtainWall` uzavretých schémou. Zostáva **17**: `SC01` 3, `SD04` 2, `ZV01.01` 4, `ZV01.02` 6, `KV02` 2 — fáza 12 |
| AN | **H** | ~~`KV01` `MOLDING`~~ → `COPING`, 2 occ + typ, `45ea35d` |
| AO | **H** | ~~fasádne zateplenia mimo agregácie~~ — atika fáza 1 (`50c26c5`, 8× `IfcRelAggregates`, 18 dielov); zateplenia fáza 6a, 14 dielov `FS01` do 10 stien. **Otvorené zostáva 7 `FS03.01`**, pre ktoré sa nenašla stena — viď §16 |

### Typy a identita
| # | | vec |
|---|---|---|
| AE | **H** | ~~`OK01` — 25 `IfcPlateType`~~ → 1 typ, 50 `RepresentationMaps`, `bddef62` |
| O | **H** | ~~`LP01` — UOT zneužitý ako počítadlo~~ — 125 `IfcPlate` → `OK01`, INST nanovo, `bddef62` + `7ea9241` |
| AK | **H** | ~~`LP01` kryje 125 `IfcPlate` + 26 `IfcWindow`~~ — rozdelené, typy `LP01.44`/`.69` zlúčené, `bddef62` |
| AF | **H** | ~~`IfcRoot.Name` nie je jednoznačný kľúč~~ — `OK01` a `LP01` (`bddef62`), 4 dvojice `IfcCoveringType` z fázy 1 zlúčené a typ `DD01.05` → `DD01.04` (`19_fix_type_names.py`). Zostáva 5 rovnomenných skupín **zámerne**: `DD01.02`, `DD02.03`, `DD03.03`, `DD04.03` (dvojkrídlové vs jednokrídlové) a `DD01.06` — rôzne výrobky pod jedným kódom sú podľa princípu „kód nesie užitie" legitímne |
| AA | **H** | ~~tretie `SC01` (3NP): 8 prvkov netypovaných~~ — prekódované na `SD03`/`SD04`, dotypované, `bddef62` |

### Názvoslovie
| # | | vec |
|---|---|---|
| M | **H** | ~~INST chýba na 2491 z 2645~~ — pridelený 2460 occurrences, šírka 4, `7ea9241` |
| N | **H** | ~~`LOP02`~~ → `LP02` (1292 occ + 1 typ), `7ea9241`. Kódov bez UOT je v modeli 18, nie 17 |
| P | **H** | ~~occurrences s `ObjectPlacement` v (0,0,0)~~ — poradie INST sa počíta z geometrie, `7ea9241`. Nameraných 149, nie 203 |
| S | — | čísla dverí `DD*` sú výkresovo autoritatívne, kotvy v `build_1np_spaces.py` |
| Y | **H** | ~~`Openspace - Zapad`~~ → `Západ`, aj `Vychod` → `Východ`, `7ea9241` |
| AP | **H** | ~~`DD01.05.01` a `.02` dvakrát~~ — sklenené dvojkrídlové na `DD01.04`, `7ea9241` |
| AX | **H** | ~~rovnaká vada aj na `DD01.02.01`, `.02`, `.03`~~ — **nešlo o vadu kódu.** SNIM kód nesie užitie, nie krídlovosť, takže `DD01.02` je pre obe varianty správny; bola to kolízia `INST`, vyriešená štandardným pravidlom poradia, `7ea9241`. Pôvodný nález: — každý 2×, všetky 1NP, vždy dvojica dvojkrídlové + jednokrídlové. Rozhodnutie 6 ich nepokrýva. Duplicita je aj vo výkrese `D.1.1.01` (39 tagov, 33 unikátnych); model je verný podkladu |

### Priestory a vzťahy
| # | | vec |
|---|---|---|
| I | **H** | ~~14 MEP priestorov s `LongName = 'Space'`~~ — prečíslované podľa §6, `20_fix_spaces.py`. Namerané 78.84 m² |
| J | **H** | ~~schodisko a 2 šachty na 2NP–4NP nepomenované, na 1NP chýbajú~~ — fáza 5c, §15. Pôvodné znenie bolo v dvoch bodoch nepresné: schodisko na 1NP **existuje** (`1.23`, legenda `D.1.1.01`, 18.36 m²) a šácht nie je 2, ale 7 zvislých stĺpcov. Nepomenovanosť riešila fáza 5b (#I). Doplnených 6 šachtových priestorov, 4 výťahy premenované, 7 zón šácht |
| H | **H** | ~~1NP: 2 prvky z 247 v miestnostiach~~ — fáza 6a, kontajnment prepočítaný z geometrie. Prvkov v miestnostiach 93 → **136**, presunutých 95 |
| G | **H** | ~~16 z 18 strešných vpustí v `IfcSpace` na 3NP; `ST01.10` v zlom podlaží~~ — fáza 6a: 17 `OV04` von z openspace do podlaží podľa geometrie; `ST01.10.0001` doplnená do agregácie `ST01.0001` (66 dielov) |
| K | **H** | ~~10 dverí bez priestorového kontajnera~~ — namerané **0** už na `ASR_v9`; vyriešili to skoršie fázy, register bol zastaraný |
| L | **H** | ~~`IfcRelSpaceBoundary` 0×~~ — fáza 6b, **649** `IfcRelSpaceBoundary1stLevel` na všetkých 75 priestoroch, bez `ConnectionGeometry`, `ParentBoundary` na 83 výplniach |
| BA | O | **`C1-J` vo výkrese `D.1.1.08` chýba** — južný pohľad má v treťom poli 1NP kód `C1-S`, ktorý zároveň patrí severnému poľu. Vada podkladu rovnakej povahy ako #AV. Model používa `C1-J` (rozhodnutie Samuela), odchýlka do BEP |
| AZ | O | **80 z 97 `IfcDoor` nemá `FillsVoids`** — dvere nie sú zviazané s otvorom, takže hostiteľskú stenu nemožno prečítať zo vzťahu. Fáza 6b ju pri 52 dverách odvodila z polohy a overila proti hraniciam tej istej miestnosti; 20 dverí zostáva bez `ParentBoundary`. Oprava väzby je samostatná vec. **Overené proti originálu (§29):** `data/ASR.ifc` má tých istých 80 z 97, rovnako 26 z 26 `IfcWindow` a 61 `IfcOpeningElement` — číslo do jedného sedí s `ASR_v17.ifc`. Vada prišla z Revit exportu, pipeline ju nespôsobila ani nezmenila |
| Z | **H** | ~~22 rekonštruovaných priestorov bez `Qto_BodyGeometryValidation`~~ — dopočítané z geometrie, `20_fix_spaces.py` |
| Q | **H** | ~~3NP nemá prenajímateľnú zónu~~ — fáza 5c, §15. **Premisa „nová zóna = vyrobiť geometriu" bola nesprávna** — `IfcZone` je podtyp `IfcSystem`/`IfcGroup`, nie `IfcProduct`, a spec hovorí doslova *„A zone does not have its own shape representation"* a *„it can not define an own geometric representation and placement"*. Rozhodnuté — vnorený `IfcZone` s 11 nájomnými priestormi 3NP (584.06 m² podľa legendy `D.1.1.03`) vložený do `IfcZone` `Pronajmutelné`. WR1 `IfcSpace` aj `IfcZone` ako členov výslovne povoľuje |
| Q2 | O | `PZ01`–`PZ10` majú vlastnú geometriu a `PredefinedType = OCCUPANCY`, ale **nereferencujú ani jeden prvok či priestor** (`IfcRelReferencedInSpatialStructure` 0×). Prenajímateľnosť tak dnes nesie iba objem, nie väzba na miestnosti. Nájdené sondou §14. Rozhodnuté (§29): väzbu **odvodiť geometricky aj logicky**, fáza 13 |
| R | **H** | ~~súčet plôch vs 2031.95 z handoveru~~ — zosúhlasené: 1NP 613.55 + 2NP 665.74 + 3NP 664.11 + 4NP 69.47 = **2012.88 m²** na 69 priestoroch. Rozdiel 19.07 m² je v handoveri, nie v modeli |
| AW | **H** | ~~85 častí fasády súčasne agregovaných aj kontajnovaných~~ — fáza 6a, časti odobrané z kontajnmentu po overení, že ich celok v priestorovej štruktúre je. Pôvodne: **85 častí** — 70 `IfcMember` `LOP02` a 9 `AZ01`, 6 `IfcPlate` `TI06.01`. Časti sedia o podlažie vyššie než ich `IfcCurtainWall` (`PL01` v 3NP → časti v 4NP; `LP03.01` v 4NP → časti v 5NP). Invariant 7 na základni zlyháva, nie až po fáze 1 |

### Materiály a skladby
| # | | vec |
|---|---|---|
| AH | **H** | ~~164 `IfcMaterialConstituent` bez `IfcShapeAspect`~~ — 0 na occurrence úrovni, `70d17af` |
| AI | **H** | ~~„Dřevo obecné" na krídle LOP~~ — vyriešilo sa rozhodnutím 27, `70d17af` |
| AQ | **D** | ~~layer sety nesedia s výpisom~~ — **prvá polovica bola nesprávne prečítaná**, viď §21. Spádové kliny v modeli **sú**: `ST01.10a` (23 ks) nesie `Izolace EPS spádové kliny`, `ST01.10b` (2 ks) rovné dosky. Hydroizolácia patrí do druhej vrstvy strechy a v modeli tam aj je — `ST01.20` a `ST01.21` nesú po dvoch asfaltových pásoch. Zostáva ETICS: krytina nesie 1 vrstvu (izoláciu) zo 6 vo výpise; lepidlo, stierka, sieťka a omietka nemajú vlastnú geometriu a podľa §2 a §3 sa hrúbkový rozdiel **dokumentuje, nedopĺňa** |
| AU | O | deklarovaná vs geometrická hrúbka: `FS01.10` 210/180, `FS01.11` 141/120, `FS01.12` 80/50, `FS01.20` 210/180, `ST01.10` 234–354/204 |
| AS | O | materiál „Výchozí" ako dutinová podlaha v `PD03.*` |
| AT | O | λ, ρ, c, μ z výpisu nie sú v `Pset_Material*` — samostatná fáza |

### Zdokumentovať, neopraviť
| # | | vec |
|---|---|---|
| AR | **D** | `IH01` — chýba vodorovná plocha pod doskou. Doska končí na −0.800, podkladný betón začína na −0.800; na 8.2 mm nie je miesto. Vytvoriť ju by znamenalo posunúť existujúcu geometriu |
| — | **D** | 9 prvkov s degenerovanou extrúziou (nulová výška) |
| AV | **D** | výpis skladieb `S8` uvádza `SD02` tam, kde má byť `SN05.01` |
| — | **D** | legenda 1NP: `PD02.31` vs `.30`; `1.17 WC Muži` má skopírovaný riadok elektrorozvodne |
| — | **D** | súčet hrúbok prvkov skladby nikdy nedá hodnotu z výpisu (vzduchové medzery sa nemodelujú) |

### AIM Viewer
| # | | vec |
|---|---|---|
| AG | **V** | neprechádza `IfcRelAggregates` — chýba 2051 prvkov fasády, 8 schodiska, 36 strechy |
| AG2 | **V** | počítadlo ráta vykresliteľné tvary, nie occurrences → zostavy ukazujú 0 |
| AG3 | **V** | pri konštituente bez `IfcShapeAspect` nehádať farbu |

---

## 4. Kedy agregovať a kedy nie

Test: **je časť fyzicky zviazaná s celkom a bez neho neexistuje?**

| skladba | vrstva | agregát | prečo |
|---|---|---|---|
| S4, S5, S8, S9 | ETICS na `SN02` / `SN05` | **áno** | mechanicky kotvené a lepené |
| atika | `ST01.30/.31/.32`, `KV01` na `SN02.01` | **áno** | to isté |
| S1, S2 | `ST01.10` + `ST01.20/.21` do `IfcRoof` | **áno** | súvrstvia natavené na seba |
| S3 | `PD02` na doske, `IH01` pod doskou | **áno** | lepené, natavené celoplošne |
| S3 | `DZ01` podkladný betón | **nie** | samostatná konštrukcia |
| S1, S2, S6 | `PH01` podhľad | **nie** | zavesený, vzduchová medzera |
| S6 | `PD03.30` dutinová podlaha | **nie** | na rektifikovateľných stojkách |

Nezviazané vrstvy sa spájajú do `IfcGroup` pomenovanej `S1`…`S9` cez
`IfcRelAssignsToGroup`. Skupina a agregácia sa nevylučujú — prvok môže byť
časťou agregátu a zároveň členom skupiny.

**Vrstva nie je podprvok.** `IfcWall` agregujúci `IfcWall` ako „vrstvy" je zlý
vzor — vrstvy sú `IfcMaterialLayerSet`, podprvky sú pre panelizované
konštrukcie. IFC4.3 zrušilo `IfcWallElementedCase` aj `IfcSlabElementedCase`,
teda práve tie entity, ktoré ten vzor pomenúvali.

---

## 5. Návrh `PredefinedType` pre `IfcWall`

| kód | popis | návrh |
|---|---|---|
| `SN07.01–.05` | Stěna_SDK_100…320 | `PARTITIONING` |
| `SN02.01` | Atika 150 | `PARAPET` |
| `SN02.02/.03` | JADRO ŽB | `SHEAR` |
| `SN05.01` | Stena keramická 250 | `SOLIDWALL` |
| `SN11.01/.02` | Skleněná deska 100 mm | `PARTITIONING` |

---

## 6. Prečíslovanie 14 MEP priestorov

Poradie určené pravidlom podlažie → Y → X. Čísla nadväzujú na existujúci rad
podlažia bez medzier.

| podlažie | staré | **nové** | plocha m² | šírka × dĺžka | `LongName` |
|---|---|---|--:|---|---|
| 2NP | `1.31` | **`2.15`** | 2.89 | 1.70 × 1.70 | **Výťahová šachta** |
| 2NP | `1.34` | **`2.16`** | 1.23 | 0.60 × 2.05 | Inštalačná šachta |
| 2NP | `1.36` | **`2.17`** | 1.29 | 0.55 × 2.35 | Inštalačná šachta |
| 2NP | `1.35` | **`2.18`** | 5.05 | 2.15 × 2.35 | **Výťahová šachta** |
| 2NP | `1.28` | **`2.19`** | 0.75 | 0.33 × 2.27 | Inštalačná šachta |
| 2NP | `1.29` | **`2.20`** | 19.71 | 2.70 × 7.30 | Schodiskový priestor |
| 3NP | `2.22` | **`3.15`** | 2.89 | 1.70 × 1.70 | **Výťahová šachta** |
| 3NP | `2.29` | **`3.16`** | 1.29 | 0.55 × 2.35 | Inštalačná šachta |
| 3NP | `2.28` | **`3.17`** | 5.05 | 2.15 × 2.35 | **Výťahová šachta** |
| 3NP | `2.20` | **`3.18`** | 0.75 | 0.33 × 2.27 | Inštalačná šachta |
| 3NP | `2.27` | **`3.19`** | 1.48 | 0.55 × 2.70 | Inštalačná šachta |
| 3NP | `2.26` | **`3.20`** | 17.82 | 2.70 × 6.60 | Schodiskový priestor |
| 4NP | `3.21` | **`4.05`** | 1.48 | 0.55 × 2.70 | Inštalačná šachta |
| 4NP | `3.20` | **`4.06`** | 17.15 | 2.70 × 6.35 | Schodiskový priestor |

**Oprava po fáze 5b:** štyri zvýraznené riadky dostali pôvodne `LongName`
„Inštalačná šachta", ale výkresy `D.1.1.01` aj `D.1.1.02` ich značia `VT01 02`
(1700 × 1700) a `VT01 01` (2150 × 2350) — sú to **výťahové šachty**, nie
inštalačné. Rozmery sedia na milimeter. `Name` ani umiestnenie sa nemení,
opravuje sa len `LongName` na štyroch priestoroch (`2.15`, `2.18`, `3.15`,
`3.17`). Rozhodnutie Samuela; opora: výkres.

Umiestnenie sa **nemení**, mení sa len `Name` a `LongName`. `PredefinedType`
zostáva `INTERNAL`. Chýbajúci `Pset_SpaceCoveringRequirements` sa nedopĺňa —
tieto priestory skladby podláh nemajú.

Kompromis, ktorý stojí za zmienku: schodisko dostane na každom podlaží iné
číslo (`1.23`, `2.20`, `3.20`, `4.06`). Alternatíva je rezervovať pevnú
pozíciu, napr. `x.20` na všetkých podlažiach, za cenu medzier v rade 4NP.
Zvolený je súvislý rad.

---

## 7. Plán

Poradie nie je ľubovoľné: triedy pred psetmi, zlúčenie typov pred INST,
rozhodnutie o UOT pred INST, čistenie priestorov pred kontajnmentom
a boundaries, sweep a zaokrúhlenie posledné.

| fáza | skript | obsah |
|---|---|---|
| **0** | `tests/test_invariants.py` | testy invariantov, `AUDIT.md` a `BEP_ANNEX.md` do repa — **doplnené**: `BEP_ANNEX.md` vznikol po fáze 8, `data/ASR.ifc` po nej, viď §24 |
| **1** | `14_fix_classes.py`, `15_fix_roof_assembly.py` | #T #V #AL #AB #AC #AN #AM; dve `FLAT_ROOF`; atika do `SN02.01` |
| **2** | `16_fix_psets.py` | #A #B #E #AH #AI (117 occurrence setov) |
| **3** | `17_dedup_types.py` | #AE #O #AK #AA #AF |
| **4** | `18_snim_inst.py` | #M #N #P #S #Y #AP; `LOP02` → `LP02`; swap dverí na 3NP |
| **5a** | `19_fix_type_names.py` | #AF — zlúčenie 4 dvojíc `IfcCoveringType`, typ `DD01.05` → `DD01.04` |
| **5b** | `20_fix_spaces.py` | #I #J (prečíslovanie §6, šachty na 1NP) #Z #Q #R |
| **5c** | `21_fix_spaces_jq.py` | #J #Q; šachtové priestory, zóny šácht, zóna 3NP |
| — | | *poradie ďalej: 6, 7, 10, 9, 8 — viď §20* |
| **6** | `22_fix_containment.py`, `23_space_boundaries.py` | #G #H #K #L #AO; agregáty skladieb |
| **7** | `24_lop_fields.py` | 48 vnorených `IfcCurtainWall`, `Ucw`, `Qto` |
| **8** | `25_layer_sets.py` | #AQ #AU #AS; layer sety na typoch; `IfcGroup` S1–S9 |
| **9** | `26_fix_numeric.py`, `27_sweep_orphans.py` | #AJ #F + finálna kontrola |
| **10** | `28_sanitary.py` | pôvodný krok 13 |
| **11** | `30_fix_classes_2.py` | triedny model podruhé — 21 `IfcFurniture` a 8 `IfcSlab`, ktoré tou triedou nie sú; §29 |
| **12** | `31_predefined_types.py` | `PredefinedType` schodísk, zábradlí a prekvalifikovaných prvkov — uzavrie #AM; §29 |
| **13** | `32_zones_pz.py` | #Q2 — `PZ01`–`PZ10` naviazať na priestory |
| **14** | | 7× `FS03.01` bez steny — čaká na rozhodnutie, §29 |

Fáza 5c pribudla po sonde k #J — pôvodný plán s ňou nerátal, lebo predpokladal,
že #J aj #Q sú len rozhodnutia, nie samostatný krok. Kroky 22–28 sa tým posunuli
o jedno; čísla skriptov ostávajú súvislé od `ASR.ifc`.
| neskôr | | #AT fyzika materiálov |

**Fáza 10, rozsah:** v modeli **nie je ani jeden kus potrubia**. Jediný podtyp
`IfcDistributionElement` je `IfcFlowTerminal` (69). `IfcRelConnectsPorts` nie je
vykonateľné (51 portov, 0 segmentov), `DOMESTICCOLDWATER` nemá oporu (všetkých
51 portov je `SOURCE`/`SEWAGE`), 18 terminálov nemá port vôbec. Systémy budú
zoskupením zariadení, nie sieťou, a treba to tak pomenovať.
Mapovanie: `WC01` `URINAL` 5, `WC02`/`WC04` `TOILETPAN` 20, `WC03`/`WC05`
`WASHHANDBASIN` 18, `WC07` `SINK` 3, `OV01.01` `IfcWasteTerminal` 5,
`OV04.*` `ROOFDRAIN` 18.

---

## 8. Pravidlá práce

- Autoritou pre triedu a `PredefinedType` je **dokumentácia a rozhodnutie
  Samuela**, nie excel — ten neexistuje. Každé rozhodnutie do BEP s odôvodnením.
- Jediný autoritatívny zdroj pre schému: **ifc43-docs**, fetchnúť pred odpoveďou.
  Sieťová politika prostredia však `standards.buildingsmart.org` blokuje už na
  `CONNECT` (403). Náhrada, ktorá je tým istým textom: publikované docs
  z `github.com/buildingSMART/IFC4.3.x-output-2`, adresár
  `IFC/RELEASE/IFC4_3/lexical` — git proxy verejné repo pustí. Sparse klon robí
  `.claude/hooks/session-start.sh` pri štarte session, cesta je v `$IFC_DOCS`.
  Pozor na rozdiel: `IFC4.3.x-development` je podľa vlastnej LICENSE *vývojová*
  verzia, autorita je tá publikovaná. Overené citácie sa medzi nimi zhodujú
  slovo za slovom, ale citovať treba publikovanú.
- Vendor dokumentáciu označovať `⚠️ vendor, nie spec`.
- **Nefabrikovať geometriu**, ktorá v modeli nie je. Chýbajúce prvky sa
  dokumentujú, nedopĺňajú. Výnimka: priestory, kde už precedens existuje
  (`build_1np_spaces.py`).
- **Každý skript overí, čo tvrdí.** Pôvodný handover uvádzal 0 osirelých entít,
  0 stratených dát a konvertovaný `Status` — ani jedno neplatilo, lebo kontrola
  merala zámer. Testy merajú výsledok.
- Skripty: `DRY_RUN` default, vstup sa neprepisuje, idempotentné.
- Odchýlky od dokumentovaného IFC vzoru do BEP. Zatiaľ dve: vnorený
  `IfcCurtainWall` a agregácia krytiny do steny s vlastným tvarom celku.
- Register je živý. Uzavretá položka dostane odkaz na commit a na výsledok
  kontroly.

---

## 9. Fáza 0 — výsledok brány

Merané `tests/test_invariants.py` proti `out/ASR_final_v2.ifc`,
`ifcopenshell` 0.8.5. **Brána nesplnená, fáza 1 nezačatá.**

| inv | | očakávané | namerané |
|---|---|---|---|
| 1 geometria | ⛔ | prejde | **nedá sa spustiť** — `data/ASR.ifc` v repe nie je |
| 2 EXPRESS | ✅ | prejde | 0 hlásení (71 s) |
| 3 GUID | ⚠️ | prejde | 0 duplicít z 24 268 `IfcRoot`; polovica proti referencii nespustená (viď inv 1) |
| 4 osirelé | ⚠️ | 48 | **49** — 48 sedí do kusa, navyše `#16` (#AY) |
| 5 prázdne SET | ✅ | prejde | 0 |
| 6 jednoznačnosť | ⛔ | zlyhá na 2 | **zlyhá na 5** — + `DD01.02.01/.02/.03` (#AX) |
| 7 kontajnment | ⛔ | prejde | **85 porušení** (#AW) |

Zosúhlasenie, ktoré sedí a potvrdzuje čítanie SNIM kódu: 305 occurrences nesie
INST = 154 `DD*`/`PD*`/`OV*` (149 unikátnych + 5 duplicít) + 151 `LP01`
(#O, UOT zneužitý ako počítadlo). Netypovaných occurrences 44 = 36 `IfcRoof`
+ 8 prvkov tretieho `SC01` (#AA), otvory sa nerátajú.

Otvorené otázky pred fázou 1: chýbajúca referencia geometrie, whitelist #AY,
rozhodnutie o #AX, rozhodnutie o #AW.

---

## 10. Fáza 1 — výsledok brány

`out/ASR_final_v2.ifc` → `out/ASR_v3_a.ifc` (`45ea35d`) → `out/ASR_v3.ifc` (`50c26c5`).
Dotknutých 45 SNIM kódov, tabuľka „pred → po" cez `src/report_diff.py`.

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = vstup fázy) |
| 2 EXPRESS | 0 hlásení |
| 3 GUID | 360 zrušených a 12 nových, všetky vysvetlené v `out/ASR_v3.ifc.allowlist.json` |
| 4 osirelé | 48 — #F nezmenené, sweep nepridal ani jednu |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 5 kódov — #AP + #AX nezmenené, rieši fáza 4 |
| 7 kontajnment | 0 mimo #AW |

Idempotencia oboch skriptov overená (druhý beh 0 zmien).

**Zámerne neurobené vo fáze 1**

* jedna `ST01.10` v 3NP (z 13250–13454, tesne pod doskou 4NP) ostáva mimo
  strešnej agregácie — je to #G a patrí do fázy 6;
* prekvalifikovaním vznikli 4 dvojice rovnomenných `IfcCoveringType`
  (`ST01.10a`, `.20`, `.21`, `.31`) — ten istý výrobok bol modelovaný raz ako
  `IfcRoof` a raz ako `IfcSlab`. Patrí to k #AF; zlúčenie nie je v rozsahu
  fázy 3, ktorá rieši len `OK01`, `LP01` a `SC01`;
* nové `IfcRoof` dostali `Name = 'ST01'` — kód nadradenej skladby. V AUDIT
  pre ne meno určené nebolo, treba potvrdiť.

---

## 11. Fázy 2–4 — výsledok brán

`ASR_v3.ifc` → `ASR_v4.ifc` (`70d17af`) → `ASR_v5.ifc` (`bddef62`)
→ `ASR_v6.ifc` (`7ea9241`).

| | fáza 2 | fáza 3 | fáza 4 |
|---|---|---|---|
| 1 geometria | 0 zmenených | 0 zmenených | 0 zmenených |
| 2 EXPRESS | 0 | 0 | 0 |
| 3 GUID | 117 zruš. / 0 nov. | 51 / 0 | 0 / 0 |
| 4 osirelé | 48 (#F) | 48 (#F) | 48 (#F) |
| 5 prázdne SET | 0 | 0 | 0 |
| 6 jednoznačnosť | 5 kódov | 5 kódov | **0 — prešlo** |
| 7 kontajnment | 0 mimo #AW | 0 mimo #AW | 0 mimo #AW |

Ďalšie merania brán: `Status` na 209 prvkoch (bolo 181); 0
`IfcMaterialConstituent` bez `IfcShapeAspect` na occurrence úrovni;
`IfcTypeObject` 149 → 124; 0 `IfcMappedItem` mimo máp vlastného typu;
netypovaných occurrences 44 → 2; 2611 z 2611 occurrences má plný SNIM
kód a žiadny nie je duplicitný. Idempotencia všetkých skriptov overená.

**Čísla, ktoré sa oproti zadaniu posunuli, a prečo**

| zadanie | skutočnosť | dôvod |
|---|---|---|
| INST na 2491 occurrences | **2460** | fáza 1 zrušila 36 strešných obalov a pridala 2 `IfcRoof`; 2491 − 36 + 2 = 2457, plus 3 prečíslované pri kolízii |
| netypovaných 44 → 36 | **44 → 2** | tých 36 boli práve strešné obaly, ktoré zanikli vo fáze 1 |
| `PredefinedType` na 383 occurrences | **314** | 383 = 314 `NOTDEFINED` + 69 `IfcFlowTerminal`, ktoré atribút v IFC4X3 nemajú |
| 203 occurrences v (0,0,0) | **149** | po fáze 1; na závere nič nemení, poradie sa aj tak počíta z geometrie |

**Otvorené po fáze 4**

* #F — 48 osirelých entít, sweep vo fáze 9;
* #AW — 85 častí fasády agregovaných aj kontajnovaných, fáza 6/7;
* #AM — 67 occurrences bez pravidla pre `PredefinedType` v §5;
* #AO — fasádne zateplenia, fáza 6;
* #AF — 4 nové dvojice rovnomenných `IfcCoveringType` z fázy 1;
* #G — jedna `ST01.10` v 3NP mimo strešnej agregácie.

---

## 12. Fáza 5a — identita typov

`out/ASR_v6.ifc` → `out/ASR_v7.ifc`. `IfcTypeObject` 124 → 120.

Zlúčené 4 dvojice `IfcCoveringType`, ktoré vznikli vo fáze 1
prekvalifikovaním toho istého výrobku raz z `IfcRoof` a raz z `IfcSlab`:
`ST01.10a` (23 occ), `ST01.20` (18), `ST01.21` (25), `ST01.31` (8).
Zhodovali sa v triede, popise, `PredefinedType` aj materiáli a žiadny
nemal `RepresentationMap`.

Typ `DD01.05` → `DD01.04` — nedotiahnutý koniec #AP: fáza 4 premenovala
occurrences sklenených dvojkrídlových dverí, typ ostal starý.

**Zámerne nezlúčené**, lebo kód nesie užitie a nie výrobok:
`DD01.02`, `DD02.03`, `DD03.03`, `DD04.03` (dvojkrídlové vs
jednokrídlové) a `DD01.06` (dva `Exteriér_Retail` s inou geometriou,
4 vs 1 `RepresentationMap`, plus `Exteriér_Chodba`).

**Otvorené — meno typu sa nezhoduje s kódom occurrences (5).**
Všeobecné pravidlo „typ sa volá podľa kódu occurrences" sa **nepoužilo**,
lebo by samo vyrobilo nové duplicity. Treba rozhodnutie:

| typ | occurrences | ks | prečo to nejde mechanicky |
|---|---|--:|---|
| `ST01.10a` | `ST01.10` | 23 | `ST01.10b` má tie isté occurrences → kolízia |
| `ST01.10b` | `ST01.10` | 2 | to isté |
| `ZD02.03` | `ZD02.02` | 2 | typ `ZD02.02` už existuje → kolízia |
| `IH01` | `IH01.01` | 4 | bez kolízie, ale mimo zadania |
| `DZ01` | `DZ01.01` | 3 | bez kolízie, ale mimo zadania |

Brána: inv 1 geometria 0 zmenených, inv 2 EXPRESS 0, inv 3 GUID 8/0,
inv 5 OK, inv 6 OK, inv 7 OK; inv 4 = 48 (#F). Idempotencia 0/0.

---

## 13. Fáza 5b — priestory

`out/ASR_v7.ifc` → `out/ASR_v8.ifc`.

* **#I** — 14 MEP priestorov prečíslovaných podľa §6. Každý presun overený
  proti kontrolnej ploche z tabuľky (tolerancia 0.02 m²), inak by skript
  zastal. Umiestnenie sa nemenilo, len `Name` a `LongName`.
* **#Z** — `Qto_BodyGeometryValidation` (`NetSurfaceArea`, `NetVolume`)
  doplnený na 22 priestorov 1NP z ich vlastnej trianguláce. Výpočet
  overený proti 47 priestorom, ktoré ten `Qto` už mali — zhoda na dve
  desatinné miesta.
* **#R** — zosúhlasené, viď register.

Brána: inv 1 geometria 0 zmenených, inv 2 EXPRESS 0, inv 3 GUID 0 zrušených
a 44 nových, inv 5 OK, inv 6 OK, inv 7 OK; inv 4 = 48 (#F). Idempotencia 0/0.

**Zostáva pred fázou 6:** #J (šachty na 1NP) a #Q (zóna pre 3NP) — obe
vyžadujú rozhodnutie. Rozhodnuté, viď §14; ani jedno nakoniec geometriu
nevyrába tak, ako sa pôvodne predpokladalo.

---

## 14. Pred fázou 6 — #J a #Q

### Zosúhlasenie, ktoré overuje inventár priestorov

Súčty legiend výkresov proti plochám z registra. Sedí to natoľko, že inventár
priestorov v modeli je tým doložený nezávisle od modelu:

| podlažie | legenda | + MEP z §6 | = | register | Δ |
|---|--:|--:|--:|--:|--:|
| 2NP | 634.82 (14 miest.) | 30.92 (6) | 665.74 | 665.74 | **0.00** |
| 3NP | 634.82 (14 miest.) | 29.28 (6) | 664.10 | 664.11 | 0.01 |
| 1NP | 613.09 (23 miest.) | — | 613.09 | 613.55 | 0.46 |

Počet 23 + 20 + 20 + 6 = **69**, presne ako §13. Na 1NP má teda legenda aj
model 23 miestností a **ani jednu šachtu**.

### Sonda `src/probe_shafts.py` — čo v modeli naozaj je

Otázka znela, či šachty nie sú v modeli ako jeden priestor cez celý objekt,
ktorý orezáva všetko — „inak by tam diera nebola".

**Diera tam je, ale nereže ju priestor, reže ju otvor.**

* **Žiadny `IfcSpace` nepresahuje jedno podlažie** a žiadny nevisí mimo
  podlažia. Teória „jeden vysoký priestor" neplatí.
* Dieru reže **`IfcOpeningElement` `SD02` s rozsahom 0 … 21000 mm**, teda cez
  celú výšku objektu, po jednom na každú prerazenú dosku
  (`SD02.03.0001`–`.0004`). To je vzor Revit „Shaft Opening".
* Pri oboch výťahových šachtách ide otvor **aj pod základovú škáru**:
  `ZD02.01` −800 … −300 (základová doska) a `DZ01.01` −900 … −800 (podkladný
  betón). Hypotéza „prelieza pod základy" teda platí — len to nesie otvor.
* **Žiadna zóna šachty nedrží.** V modeli je 5 `IfcZone` (`Pronajmutelné`,
  `Nájomný priestor`, `Zóna 1`, `Zóna 4`, `Zóna 5`) a 10 `IfcSpatialZone`
  `PZ01`–`PZ10`; ani jedna nemá `ObjectType` z hodnôt odporúčaných spec a ani
  jedna neobsahuje šachtový priestor.

Stĺpce sa nesmú hľadať len podľa priestorov — šachta, ktorá priestor nemá na
žiadnom podlaží, by tak zostala neviditeľná. Semienkom je preto aj zvislý
otvor. Zlučovať sa musí podľa **podobnosti** pôdorysov (prienik voči väčšiemu),
nie podľa vnorenia, inak schodiskový otvor pohltí šachtu, ktorá v ňom leží.

| stĺpec | pôdorys mm | plocha | priestor je na | prerazí dosku 1NP | čo to je |
|--:|---|--:|---|:-:|---|
| 1 | 7300 × 2700 | 19.71 m² | — | áno | schodiskový otvor, nie šachta |
| 2 | 2150 × 2350 | 5.05 m² | 2NP, 3NP | áno | **výťah `VT01 01`** |
| 3 | 1700 × 1700 | 2.89 m² | 2NP, 3NP | áno | **výťah `VT01 02`** |
| 4 | 3450 × 800 | 2.76 m² | **nikde** | áno | inštalačná šachta |
| 5 | 550 × 2700 | 1.48 m² | 3NP, 4NP | nie | inštalačná šachta, bez otvoru |
| 6 | 550 × 2350 | 1.29 m² | 2NP, 3NP | áno | inštalačná šachta |
| 7 | 2050 × 600 | 1.23 m² | 2NP | áno | inštalačná šachta |
| 8 | 330 × 2270 | 0.75 m² | 2NP, 3NP | nie | inštalačná šachta, bez otvoru |

Ďalších 8 zvislých prestupov pod 0.10 m² (160 × 160) sú prestupy potrubia,
nie šachty — z výpočtu vynechané.

**Na 1NP nemá priestor ani jeden stĺpec.** Inštalačných šácht je päť (4–8),
výťahové sú dve (2, 3).

### Ako sa v tomto modeli modeluje teleso priestoru

Spodok priestoru sedí na úrovni podlažia (medián 0 mm), výška je slab-to-slab:
šachty na 2NP `5000 … 8800`, na 3NP `9200 … 13000` — konštrukčná výška 4200
mínus doska 400. Pre 1NP (`0 … 5000`) tomu zodpovedá `0 … 4600`. Spec
geometrický rozsah `IfcSpace` **nemandátuje** (je to vec MVD), takže nový
priestor sa riadi susedmi, nie knihou.

### Rozhodnutia

| vec | rozhodnutie |
|---|---|
| #J rozsah | dokresliť **len inštalačné šachty** na 1NP; výťahové nie |
| #J pôdorys | prevziať z existujúceho otvoru `SD02`, ktorý má **presne pôdorys šachty**, a orezať na pásmo 1NP (`0 … 4600`) — nefabrikuje sa, void v modeli už je |
| #J názvy | `2.15`, `2.18`, `3.15`, `3.17` → `LongName` **„Výťahová šachta"** podľa výkresu |
| #Q | vnorený `IfcZone` s 11 nájomnými priestormi 3NP do `IfcZone` `Pronajmutelné` |

**Čaká na rozhodnutie:** spec ponúka pre zvislé zoskupenie priestorov
`IfcZone` s `ObjectType` `'RisingDuct'` („A collection of vertical airspaces")
a `'ElevatorShaft'` („a collection of spaces within an elevator, **potentially
going through many storeys**"). Tým by sa každý zo 6 stĺpcov stal jednou vecou
bez akejkoľvek geometrie — vrátane výťahových, ktoré nekreslíme. Zoznam je
v spec uvedený vetou *„in case of a zone denoting a (fire) compartment"*, takže
rámec je požiarny; do BEP to treba napísať tak, ako to je.

**Nový nález, ktorý mení rozsah #J.** Sonda odhalila vec, ktorú pohľad cez
priestory nevidel: **stĺpec 4 (3450 × 800, 2.76 m²) nemá `IfcSpace` na žiadnom
podlaží**, hoci prerazí každú dosku vrátane 1NP. Na výkresoch je to ten
čiarkočiarkový box severne od `1.05` a `2.14`, ktorý sa pri prvom čítaní
legendy nedal priradiť k žiadnemu číslu miestnosti — legenda ho nemá, lebo
miestnosť to nie je. Otázka teda už nie je len „doplniť 1NP", ale aj **či
tento stĺpec dostane priestory na všetkých podlažiach**. To je rozhodnutie
navyše, nie súčasť pôvodného #J.

Kandidáti na 1NP sú preto tri inštalačné šachty, ktorých void 1NP doskou
naozaj prechádza: **stĺpce 4 (2.76 m²), 6 (1.29 m²) a 7 (1.23 m²)**. Stĺpce 5
a 8 dosku neprerážajú vôbec — pre ne dôkaz o pokračovaní na 1NP neexistuje
a bez neho sa priestor nekreslí. Čísla nadviažu na rad 1NP od `1.24`.

Pred kreslením musí skript pri každom kandidátovi overiť obvodové steny na
1NP a zastať, ak nesedia — inak by vyrobil priestor tam, kde šachta
nepokračuje.

### Ako skript rozozná výťah od inštalačnej šachty

Nie podľa mena — meno je práve to, čo je zle. Rozhoduje **šachtová jama**:
otvor v základovej doske `ZD02` alebo v podkladnom betóne `DZ01` pod tým istým
pôdorysom. Inštalačná šachta pod základovú škáru nejde, výťahová áno. Test
vybral presne dva stĺpce, 5.05 a 2.89 m², čo sedí s `VT01 01` a `VT01 02`
z výkresu.

### Brána `ASR_v8.ifc` pred fázou 6

inv 2 EXPRESS 0, inv 3 GUID OK, inv 5 OK, inv 6 OK, inv 7 OK (mimo #AW,
85 menovite); inv 4 = 48 (#F). inv 1 sa nedá spustiť — `data/ASR.ifc` v repe
stále nie je.

---

## 15. Fáza 5c — #J a #Q

`out/ASR_v8.ifc` → `out/ASR_v9.ifc`, `src/21_fix_spaces_jq.py`.

**#J — názvy.** `LongName` štyroch priestorov (`2.15`, `2.18`, `3.15`, `3.17`)
opravený na „Výťahová šachta". `Name`, umiestnenie ani geometria sa nedotkli.

**#J — chýbajúce priestory.** Pravidlo: *šachta je na podlaží, ktorého strop
prerazí jej void*. Vzniklo 6 priestorov, každý overený proti pôdorysu a pásmu,
z ktorých vznikol, na 1 mm:

| priestor | plocha | podlažie | stĺpec |
|---|--:|---|---|
| `1.24` | 1.23 m² | 1NP | 2050 × 600 |
| `1.25` | 1.29 m² | 1NP | 550 × 2350 |
| `1.26` | 2.76 m² | 1NP | 3450 × 800 |
| `2.21` | 2.76 m² | 2NP | 3450 × 800 |
| `3.21` | 1.23 m² | 3NP | 2050 × 600 |
| `3.22` | 2.76 m² | 3NP | 3450 × 800 |

Stĺpce 1.48 a 0.75 m² priestor na 1NP **nedostali** — ich void neprerazí žiadnu
dosku, takže dôkaz o pokračovaní neexistuje a bez neho sa nekreslí.

Tvar sa robil vzorom rekonštruovaných priestorov 1NP: `IfcArbitraryClosedProfileDef`
+ extrúzia, placement k podlažiu, polyline vo svetových XY. Extrúzia 1NP je
`4600` — presne ako u `1.05` z `build_1np_spaces.py`.

**#J — zóny šácht.** Každý stĺpec dostal `IfcZone`, takže šachta je jedna vec
naprieč podlažiami bez jediného milimetra novej geometrie. `ObjectType` podľa
spec (IFC4.3 §5.4.3.82): 2× `'ElevatorShaft'`, 5× `'RisingDuct'`. Zoznam je
v spec uvedený vetou *„in case of a zone denoting a (fire) compartment"* —
rámec je požiarny a do BEP to patrí napísať tak, ako to je.

**#Q.** `IfcZone` „Nájomné priestory 3NP" s 11 priestormi, 584.07 m² (legenda
`D.1.1.03` uvádza 584.06), vložená do `IfcZone` `Pronajmutelné`. Skript zastane,
ak sa súčet od legendy odchýli o viac než 0.05 m². Geometria žiadna — `IfcZone`
ju niesť nemôže.

### Plochy po fáze 5c

| podlažie | pred | po | priestorov |
|---|--:|--:|--:|
| 1NP | 613.55 | **618.83** | 26 |
| 2NP | 665.74 | **668.50** | 21 |
| 3NP | 664.11 | **668.10** | 22 |
| 4NP | 69.47 | 69.47 | 6 |
| spolu | 2012.88 | **2024.91** | **75** |

Zosúhlasenie s legendami tým prestáva byť rovnosť na cent — pribudlo 12.03 m²
šachiet, ktoré legendy neuvádzajú, lebo šachta nie je miestnosť. Legendy
nikdy neuvádzali ani pôvodných 14 MEP priestorov; rozdiel je teraz
dokumentovaný, nie neznámy.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = `ASR_v8.ifc`, 6 nových tvarov v allowliste) |
| 2 EXPRESS | **0 hlásení** — vrátane `IfcZone_WR1` na siedmich nových zónach |
| 3 GUID | 0 zrušených, 58 nových, všetky v `out/ASR_v9.ifc.allowlist.json` |
| 4 osirelé | 48 (#F) — rozpad nezmenený, skript nepridal ani jednu |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 0 |
| 7 kontajnment | 0 mimo #AW |

Idempotencia overená: druhý beh 0 zmien, 0 nových GlobalId.

---

## 16. Fáza 6a — kontajnment a agregácia

`out/ASR_v9.ifc` → `out/ASR_v10.ifc`, `src/22_fix_containment.py`.

**#AW.** 85 častí fasády (79 `IfcMember`, 6 `IfcPlate`) odobraných
z kontajnmentu. Skript najprv overí, že **celok** v priestorovej štruktúre
je — inak by sa časť odobratím stratila. Brána bola preto pustená
**bez** `--known AW` a invariant 7 prešiel, takže vada je vyriešená, nie
zamaskovaná. Menovitý allowlist v `tests/known_baseline.json` zostáva —
platí pre základňu `ASR_final_v2.ifc`, kde vada reálne je.

**#AO.** 14 fasádnych zateplení `FS01` vložených cez `IfcRelAggregates`
do 10 stien a odobraných z kontajnmentu — tá istá deprecation ako pri
atike vo fáze 1.

**#G + #H — jedno pravidlo namiesto dvoch opráv.** Kontajnment sa pre
triedy z rozhodnutia 24 prepočítal z geometrie. 95 presunov:

| smer | ks | čo to je |
|---|--:|---|
| podlažie → miestnosť | 60 | #H, vlastný cieľ rozhodnutia 24 |
| miestnosť → podlažie | 17 | #G, strešné vpuste `OV04` von z openspace |
| miestnosť → miestnosť | 16 | krytiny priradené zlej miestnosti |
| podlažie → podlažie | 2 | prvky v zlom podlaží |

Prvkov v miestnostiach **93 → 136**.

### Dva testy, nie jeden — a prečo

Prvý pokus použil jednotné pravidlo „ťažisko vnútri priestoru" a vyhodil
z miestností 43 krytín. Nebola to chyba modelu, ale testu: **krytina leží
mimo objemu miestnosti** — podlaha pod ňou, podhľad nad ňou — takže
ťažiskový test ju vždy pošle do podlažia. Rozhodnutie 24 to menuje
„Z-filtrom" a myslí tým presne toto.

* **zariaďovacie predmety** (`IfcFlowTerminal`, `IfcSanitaryTerminal`,
  `IfcFurniture`, `IfcRailing`) — ťažisko vnútri, vyhráva **najmenší**
  priestor, inak by chodba pohltila prvky priľahlých miestností;
* **krytiny** (`IfcCovering`) — najprv **zvislá priľahlosť** (vrch krytiny
  ≈ spodok priestoru, alebo spodok krytiny ≈ vrch priestoru, tolerancia
  300 mm), až potom prekryv pôdorysu ≥ 0.5 z plochy krytiny.

Opačné poradie nefunguje: bbox openspace prekrýva v XY takmer všetko, takže
párovanie podľa prekryvu trafí cudzie podlažie. Zmerané — medzery pri
takom párovaní vychádzali +0 až +8650 mm.

**#G, zvyšok.** `ST01.10.0001` visela od fázy 1 mimo strešnej agregácie,
lebo bola kontajnovaná v 3NP, kým zvyšok súvrstvia na 4NP. Doplnená do
`ST01.0001` (65 → **66 dielov**). Dôkaz: jej vrch je `13454` a stoh
strechy presne tam začína, pri zhodnom pôdoryse (30285…62985 vs
30135…63135).

### Otvorené

**7 z 9 `FS03.01` sa nepodarilo priradiť k stene** (2 áno —
`SN05.01.0005` a `SN02.02.0019`), zostávajú kontajnované v 1NP.
Pravdepodobné vysvetlenie je v registri #A: `FS03.01` bolo pôvodne
`IfcWall` prekvalifikované na `IfcCovering`, takže nemusí ísť o krytinu
steny, ale o samostatný pás. **Neoverené** — skript nič nedomýšľa
a nechal ich tak.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = `ASR_v9.ifc`) |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | 36 nových, 12 zrušených, všetky v allowliste kroku |
| 4 osirelé | 48 (#F) — rozpad nezmenený |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 0 |
| 7 kontajnment | **0 — bez allowlistu `AW`** |

Idempotencia overená: druhý beh 0 zmien, 0 nových GlobalId.

**Zostáva vo fáze 6:** #L `IfcRelSpaceBoundary` — `23_space_boundaries.py`,
rozhodnutie 23 (1. úroveň, bez `ConnectionGeometry`, `ParentBoundary` pre
dvere a okná).

---

## 17. Fáza 6b — hranice priestorov

`out/ASR_v10.ifc` → `out/ASR_v11.ifc`, `src/23_space_boundaries.py`.

**649 `IfcRelSpaceBoundary1stLevel` na všetkých 75 priestoroch**, bez
`ConnectionGeometry`, podľa rozhodnutia 23. 2. úroveň sa nerobí —
energetické zónovanie je mimo rozsah.

| trieda | hraníc |
|---|--:|
| `IfcWall` | 345 |
| `IfcSlab` | 108 |
| `IfcDoor` | 103 |
| `IfcColumn` | 65 |
| `IfcCurtainWall` | 28 |

Na priestor medián 7, minimum 5, maximum 26. `ParentBoundary` napojený na
83 výplní, z toho **52 s hostiteľom odvodeným z polohy** (viď #AZ nižšie).

### Ako sa hranica hľadá

Hranica odpovedá na otázku „čo stojí tesne za touto stenou miestnosti".
Z každého trojuholníka obalu priestoru sa vystrelí lúč von po normále
a berie sa **najbližší** zásah. Tri veci, na ktorých to najprv stálo zle:

* **lúč, nie bod.** Test „bod je vnútri bboxu" priradil jednej stene
  miestnosti tri prvky naraz, lebo bbox veľkej dosky obsahuje aj body,
  ktoré v doske nie sú. Lúč berie prvý zásah, čo je presne to, čo slovo
  hranica znamená.
* **plocha, nie počet trojuholníkov.** Prah „aspoň 3 trojuholníky" zmazal
  hranice 30 priestorov — kvádrová miestnosť má na stenu presne dva.
  Prah je preto plošný (0.05 m²) a na tvare nezávislý.
* **zásah sa mapuje na celok.** Lúč trafí konkrétny panel fasády, ale
  hranicou je `IfcCurtainWall`; bez toho mal openspace 79 hraníc na tú
  istú fasádu. Výnimkou sú dvere a okná — tie zostávajú samy sebou,
  pretože celok je ich `ParentBoundary`.

Krytiny, nábytok a zariaďovacie predmety hranicou nie sú. Ich vzťah
k miestnosti nesie kontajnment z fázy 6a a druhý raz by to bola duplicita.
Hranica hovorí, čo miestnosť uzatvára, nie čo v nej stojí.

### Čo sa pritom našlo

**Okná nemajú ani jednu hranicu.** Všetkých 26 `IfcWindow` je agregovaných
do `IfcCurtainWall` bez `FillsVoids`, takže z miestnosti lúč trafí najprv
panely fasády. Geometricky je to pravda a spec to nezakazuje, ale znamená
to, že okenné hranice v modeli nebudú, kým sa fasáda nerozdelí na polia
(fáza 7).

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = `ASR_v10.ifc`) |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | 649 nových, 0 zrušených, všetky v allowliste kroku |
| 4 osirelé | 48 (#F) — rozpad nezmenený |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 0 |
| 7 kontajnment | 0 |

Kontrola zápisu: 649 `IfcRelSpaceBoundary1stLevel`, `ConnectionGeometry`
nenulových **0**, všetky `PHYSICAL`, 587 `INTERNAL` / 62 `EXTERNAL`,
83 s `ParentBoundary` a funkčným inverzom `InnerBoundaries`. Priestor
`1.05` je ohraničený 6 stenami, doskou pod (`ZD02.01.0001`) aj nad
(`SD02.03.0001`) a dverami — sedí s výkresom. Idempotencia: druhý beh
hranice našiel a skončil bez zmeny.

**Fáza 6 je tým uzavretá.** Ďalej je fáza 7 — `24_lop_fields.py`, 48
vnorených `IfcCurtainWall`, `Ucw` a `Qto`. Tá zároveň otvorí okenné
hranice, ktoré dnes chýbajú.

---

## 18. Fáza 7 — podklad k LOP, zisťovanie pred zásahom

Model sa zatiaľ **nemenil**. Toto je zhrnutie toho, čo je overené, a jednej
veci, ktorú bez rozhodnutia určiť nemožno.

### Čo sedí

**48 polí je potvrdených z dvoch nezávislých strán.** Výkres `D.1.1.08`
delí fasádu na 5 polí na východe, 5 na západe, 3 na juhu a 3 na severe,
teda 16 na podlažie × 3 podlažia. V modeli to sedí na osnovu: zhluky
stĺpov dávajú **6 osí v X po 6500 mm** (30385…62885) a **4 osi v Y**
(−7641, −1141, 6359, 12859). Šesť osí = 5 polí, štyri osi = 3 polia.
Červené deliace čiary na výkrese ležia na tých istých osiach, takže
delenie sa nemusí odčítavať z rastra — dá sa odvodiť z geometrie.

**`Ucw` je v podkladoch, ktoré máme.** Poznámka výkresu `D.1.1.08`:
*„uvažovaný súčiniteľ prestupu tepla podľa teplo-technickej analýzy
U_cw = 0,64 W/m²K"*. Chýbajúca zložka `3 – Tepelná technika LOP` teda
nie je pre `Pset_CurtainWallCommon.ThermalTransmittance` nutná. Plochy sa
aj tak majú merať z geometrie, nie prepisovať.

Tá istá poznámka uvádza systém **`SCHUECO FWS 50.SI`** — patrí do
`Description` alebo do BEP.

**12 `PL01` sedí:** 4 na podlažie, dve dlhé po 33500 mm (5 polí) a dve
krátke po 21500 mm (3 polia). Súčet obálok 1579.51 m²; s `LP03` a `OV06`
na 4NP 1761.57 m². Tepelná technika uvádzala 1603.63 m² — rozdiel patrí
do zosúhlasenia, keď budú polia hotové.

**Orientácia východ–západ je istá z modelu:** `2.02 Openspace - Východ`
leží na `Y = −2703`, `2.01 Openspace - Západ` na `Y = +7922`, takže
**−Y je východ a +Y západ**. Fasády `PL01.0001/.0005/.0009` sú východné,
`.0004/.0008/.0012` západné.

### Názvy polí z výkresu

| pohľad | 1NP | 2NP | 3NP |
|---|---|---|---|
| východ | `I1-V` `K1-V` `L1-V` `K1-V` `D1-V` | `M2-V` `E2-V` `E2-V` `E2-V` `C2-V` | `M3-V` `E3-V` `E3-V` `E3-V` `C3-V` |
| sever | `C1-S` `B1-S` `A1-S` | `C2-S` `B2-S` `A2-S` | `C3-S` `B3-S` `A3-S` |
| juh | `A1-J` `B1-J` **`C1-S`** | `A2-J` `B2-J` `C2-J` | `A3-J` `B3-J` `C3-J` |

Kód teda **nie je jedinečný na pole, ale na typ poľa** — `E3-V` je na
východe trikrát. Pomenovanie inštancií preto potrebuje index.

### Dve veci, ktoré bez rozhodnutia nejdú

**1 · `C1-S` na južnom pohľade.** Systematicky tam patrí `C1-J`, ale
výkres tam má `C1-S` a kód `C1-J` sa v celom výkrese nevyskytuje.
Overené priblížením oboch pohľadov, nejde o preklep v čítaní. Je to vada
podkladu rovnakej povahy ako #AV. Buď sa pole pomenuje `C1-J` s poznámkou
o odchýlke, alebo `C1-S` dvakrát a padne jedinečnosť mena.

**2 · Ktorá strana modelu je sever.** Východ a západ sú isté, sever a juh
nie. Kompas na `D.1.1.01` ukazuje **šikmo**, teda objekt nie je natočený
podľa svetových strán a názvy fasád sú priradené k najbližšej svetovej
strane. Pôdorys je navyše kreslený tak, že `+X` ide doľava, čo smer
z kompasu obracia. Určiť to odhadom by znamenalo označiť 18 zo 48 polí
možno naopak, preto to nechávam otvorené. Rozhodne to jedna veta od
Samuela alebo chýbajúca zložka `3 – Tepelná technika LOP`, ktorá polia
vymenúva záväzne.

---

## 19. Fáza 7 — polia LOP

`out/ASR_v11.ifc` → `out/ASR_v12.ifc`, `src/24_lop_fields.py`.

**48 vnorených `IfcCurtainWall`** pod 12 `PL01`. Rodičia už neagregujú
jednotlivé panely, ale polia; panely visia na poliach. `IfcCurtainWall`
pod `IfcCurtainWall` je legálne, ale nedokumentované — odchýlka patrí do
BEP, ako hovorí §2.

**Delenie z modelu, nie z rastra.** Zhluky stĺpov dávajú 6 osí v X po
6500 mm a 4 osi v Y; červené deliace čiary na `D.1.1.08` ležia práve na
nich. Dlhá fasáda sa delí na 5 polí, krátka na 3 — 16 na podlažie, 48
spolu.

**Orientácia.** `2.02 Openspace - Východ` na `Y = −2703` a `2.01 Západ` na
`Y = +7922` dávajú **−Y = východ**. Pri klasickej konvencii (sever hore,
východ vpravo) z toho vychádza **sever = +X** — rozhodnutie Samuela.
Poradie názvov je v smere rastúcej súradnice, čo pre západ a juh znamená
opačné poradie než na výkrese: tie pohľady sa kreslia zrkadlovo.

Kontrola, ktorá tomu dáva váhu: severné a južné polia vyšli rozmerovo
zhodné (6735 / 7525 / 7290 mm) a východné so západnými tiež. Symetria
objektu sa v priradení odrazila sama.

**Odchýlka od podkladu.** Južný pohľad má v treťom poli 1NP kód `C1-S`,
hoci systematicky tam patrí `C1-J`, a `C1-J` sa vo výkrese nevyskytuje.
Model používa `C1-J` — rozhodnutie Samuela, do BEP s odôvodnením.

**Mená inštancií.** Kód nesie typ poľa, nie kus: `E3-V` je na východe
trikrát. Za kód sa preto pridáva poradie, tým istým princípom ako INST
pri SNIM, len na dve miesta — `E3-V.01`. Duplicitné meno nevzniklo ani
raz.

**`Ucw` a plochy.** `Pset_CurtainWallCommon` nesie
`ThermalTransmittance = 0.64 W/m²K` z poznámky výkresu, `Reference` s kódom
poľa a `IsExternal`. `Qto_CurtainWallQuantities` sa počíta z geometrie
dielov, neprepisuje sa z tabuľky. `Description` nesie systém
`SCHUECO FWS 50.SI`.

Súčet plôch polí **1583.00 m²**, tepelná technika uvádza 1603.63 m² —
rozdiel 20.63 m², teda 1.3 %. Plochy sú merané z geometrie a nedoťahujú
sa na tabuľku; zdroj rozdielu (iná vzťažná rovina) sa overí, až keď bude
zložka `3 – Tepelná technika LOP` k dispozícii.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = `ASR_v11.ifc`) |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | 300 nových, 12 zrušených, všetky v allowliste kroku |
| 4 osirelé | 48 (#F) — rozpad nezmenený |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 0 |
| 7 kontajnment | 0 |

`IfcCurtainWall` v modeli 19 → **67** (19 pôvodných + 48 polí), duplicitné
meno ani jedno. Idempotencia overená.

**Zostáva:** fáza 8 (`25_layer_sets.py`, #AQ #AU #AS a `IfcGroup` S1–S9),
fáza 9 (sweep #F #AJ), fáza 10 (`27_sanitary.py`). Otvorené položky
registra: #AM, #AT, #AZ, #Q2, 7× `FS03.01` bez steny.

---

## 20. Fázy 10 a 9 — sanita, číselný šum, sweep

Poradie oproti §7 zamenené: fáza 8 (skladby) potrebuje prečítať
desaťstranový výpis a nesie rozhodnutia do BEP, kým fázy 10 a 9 sú
v pláne rozpísané do detailu. Spravili sa preto skôr; sweep zostal
posledný, ako plán zamýšľal. Skripty sú prečíslované podľa poradia
vykonania: `25_sanitary.py`, `26_fix_numeric.py`, `27_sweep_orphans.py`,
skladby zostávajú na `28_layer_sets.py`.

### Fáza 10 — `ASR_v12.ifc` → `ASR_v13.ifc`

69 `IfcFlowTerminal` prekvalifikovaných na podtypy, ktoré
`PredefinedType` v IFC4X3 majú. Súčty sedia s §7 do kusa:

| kód | trieda | `PredefinedType` | ks |
|---|---|---|--:|
| `WC01` | `IfcSanitaryTerminal` | `URINAL` | 5 |
| `WC02`, `WC04` | `IfcSanitaryTerminal` | `TOILETPAN` | 20 |
| `WC03`, `WC05` | `IfcSanitaryTerminal` | `WASHHANDBASIN` | 18 |
| `WC07` | `IfcSanitaryTerminal` | `SINK` | 3 |
| `OV01.01` | `IfcWasteTerminal` | `GULLYTRAP` | 5 |
| `OV04.*` | `IfcWasteTerminal` | `ROOFDRAIN` | 18 |

`IfcFlowTerminal` po behu **0**, `IfcSanitaryTerminal` 46,
`IfcWasteTerminal` 23. `GlobalId` sa nemenili — `util.schema.reassign_class`
zachováva `id()`.

**`GULLYTRAP` pre `OV01.01`** §7 neurčovala; rozhodla definícia zo spec
proti legende. Výkres: *„Vpusť podlahová, DN110, krytá pochôdznou
mriežkou"*. IFC4.3 `GULLYTRAP`: *„…fitted with a grating or sealed cover
that discharges water through a trap."* `FLOORTRAP` je definovaný cez
zápachovú uzáveru a `FLOORWASTE` cez odvedenie do samostatnej uzávery —
ani jeden nespomína mriežku, ktorú výkres uvádza ako určujúcu.

**Zoskupenia.** Tri `IfcSystem`, nie `IfcDistributionSystem`: model má
51 portov a **0 `IfcFlowSegment`**, takže sieť neexistuje a entita by ju
sľubovala. Názvy to hovoria priamo — „Zoskupenie zariadení —
zdravotechnika" (46), „— strešné vpuste" (18), „— podlahové vpuste" (5).
Každý je cez `IfcRelServicesBuildings` naviazaný na budovu.

### Fáza 9a — `ASR_v13.ifc` → `ASR_v14.ifc`, #AJ

Zaokrúhlenie na 6 desatinných miest. V milimetroch je to nanometer, teda
rádovo pod presnosťou, s akou model vznikol; skript navyše zastane, ak by
niektorá oprava presiahla `1e-4`.

Opravených **15135** hodnôt (14834 `Qto`, 242 `Overall*`, 59 property),
najväčšia oprava **5e-07**. Register uvádzal 2653 — rozdiel nie je v
modeli, ale v kritériu: register počítal užšiu množinu. Ukážka toho, čo
sa deje: `33250.000000000124 → 33250.0`, `4849.999999999999 → 4850.0`,
`24.999999999999996 → 25.0`, `161.26250000000059 → 161.2625`.

### Fáza 9b — `ASR_v14.ifc` → `ASR_v15.ifc`, #F

Koreňov **48** a rozpad sedí s registrom na kus (31 `IfcLocalPlacement`,
11 `IfcRectangleProfileDef`, 5 `IfcArbitraryClosedProfileDef`,
1 `IfcSurfaceStyle`) — skript to porovnáva proti
`tests/known_baseline.json` a inak zastane.

Zametalo sa v **3 kolách, spolu 204 entít**: po zmazaní placementu
osireli aj jeho `IfcAxis2Placement3D` a body, po profile jeho polyline.
48 je počet koreňov, nie zmazaných entít. Zdieľané entity prežili — počet
inverzov sa po každom kole ráta nanovo. Zrušených `GlobalId` **0**, lebo
ani jedna z nich nie je `IfcRoot`.

**Po zametaní 0 osirelých entít, čiže invariant 4 prvýkrát prechádza
bez známej vady.**

### Brána `ASR_v15.ifc`

| inv | výsledok |
|---|---|
| 1 geometria | **0 zmenených** (referencia = `ASR_v13.ifc`, teda cez obe časti fázy 9) |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | 0 zrušených, 0 nových, allowlist prázdny |
| 4 osirelé | **0** |
| 5 prázdne SET | 0 |
| 6 jednoznačnosť | 0 |
| 7 kontajnment | 0 |

**zlyhalo 0 z 7** — prvýkrát v projekte prejde brána celá, bez známej
vady v allowliste. Idempotencia oboch skriptov overená.

---

## 21. #AQ — overenie skladby strechy

Podnet Samuela: buď je skladba v PDF vypísaná zle, alebo je hydroizolácia
až v druhej vrstve strechy, teda v `ST01.20`. Odmerané na `ASR_v15.ifc`:

| typ | ks | layer set v modeli |
|---|--:|---|
| `ST01.10a` | 23 | `Izolace EPS spádové kliny 30` |
| `ST01.10b` | 2 | `Izolace EPS 100`, `Izolace EPS 100`, `Hydroizolace — asfaltový pás 4` |
| `ST01.20` | 18 | `Terén hlína 79`, `Hydrofílna vata 50`, `HDPE nopová fólia 26`, `Hydroizolace 2`, `Hydroizolace 3` |
| `ST01.21` | 25 | `Kamenivo 129`, `HDPE nopová fólia 23`, `Hydroizolace 5`, `Hydroizolace 3` |

**Prvá polovica #AQ bola nesprávne prečítaná.** Spádové kliny nechýbajú —
sú to priamo prvky `ST01.10a` a materiál sa tak aj volá. Šikmosť teda
nesie geometria týchto prvkov, nie zoznam vrstiev, a delenie na `a`/`b`
je práve rozdiel medzi klinovou a rovnou časťou.

**Hydroizolácia sedí tam, kde ju Samuel čakal.** `ST01.20` aj `ST01.21`
nesú po dvoch asfaltových pásoch — to sú vrstvy 7 a 8 skladby S1. Vo
výpise sú uvedené nad tepelnou izoláciou (vrstvy 9 a 10), čo pri teplej
plochej streche sedí, a model to tak má. Rozpor teda nie je.

Nemodelované zostávajú tenké vrstvy bez vlastnej geometrie: vegetačná
rohož a dve geotextílie (1 a 2 mm). To je ten istý prípad ako vzduchová
medzera podľa §2 — dokumentuje sa, nedopĺňa.

**Čo z #AQ zostáva.** ETICS: krytina nesie jednu vrstvu — `FS01.10`
`Izolace minerální 180`, `FS01.11` `Izolace XPS 120`, `FS01.12`
`Izolace minerální 50`, `FS03.01` `Izolace XPS 120` — kým výpis uvádza
šesť. Chýbajú lepidlo, kotvy, stierka so sieťkou a omietka, teda vrstvy
bez vlastnej geometrie. Doplniť ich do layer setu by rozišlo súčet hrúbok
s hrúbkou prvku a §2 hovorí, že `IfcMaterialLayerSetUsage` patrí len tam,
kde hrúbka sedí. Preto sa to zapisuje, neopravuje — položka mení kategóriu
na **D**.

Stena pod krytinou nesie svoju vlastnú vrstvu (`SN02.02`
`Beton — Železobeton 250`), takže skladba ako celok je v modeli čitateľná
z agregácie z fázy 6a: stena + krytina.

---

## 22. Fáza 8 — vzduchová dutina a skupiny skladieb

`out/ASR_v15.ifc` → `out/ASR_v16.ifc`, `src/28_layer_sets.py`.

### #AS — v dutine je vzduch

Rozhodnutie Samuela: *„ak to je dutina tak tam je vzduch."* Schéma na to
má presný zápis, `IfcMaterialLayer` §8.10.3.6.1:

> Air gaps within a material layer set are represented as an
> `IfcMaterialLayer` with the attribute `IsVentilated` having the value
> TRUE or UNKNOWN. Such air gaps shall be interpreted as **voids (not
> having a material)**.

Štyri layer sety `PD03.*` mali druhú vrstvu s materiálom `Výchozí`.
Vrstva teraz materiál nemá, nesie `IsVentilated = UNKNOWN` a meno
„Vzduchová dutina". `UNKNOWN` a nie `TRUE` zámerne — dokumentácia
nehovorí, že dutina je vetraná, len že tam je.

Hrúbka sa nemenila, takže súčet vrstiev naďalej sedí s hrúbkou prvku
a `IfcMaterialLayerSetUsage` ostáva platné podľa §2. Zároveň to napĺňa
pravidlo „`IsVentilated` platí len vnútri jedného prvku" — vrstva je
vnútri jedného layer setu, nie samostatný prvok.

### S1–S9 ako `IfcGroup`

Výpis `D.1.1.09` má **osem** skladieb, nie deväť: S7 v ňom nie je.
Každá strana uvádza svoje SNIM kódy.

| skupina | prvkov | zloženie |
|---|--:|---|
| `S3` Skladba základovej dosky a podlahy v 1NP | 54 | 50 krytín, 4 dosky |
| `S4` Skladba ETICS, plocha výlezu | 8 | 4 krytiny, 4 steny |
| `S5` Skladba ETICS, sokol výlezu | 8 | 4 krytiny, 4 steny |
| `S8` Skladba ETICS, odpadové hospodárstvo | 2 | 1 krytina, 1 stena |
| `S9` Skladba ETICS, odpadové hospodárstvo | 6 | 3 krytiny, 3 steny |

**Prečo len päť z ôsmich.** Kódy `SD02` (9 dosiek), `PH01` (24 podhľadov),
`ST01.10` (25) a `SN02` (73 stien) zdieľa viac skladieb naraz. Priradenie
„všetky prvky kódu" by dalo tú istú stenu do `S4` aj `S5`, hoci ETICS na
nej je jedno, a všetkých 9 dosiek `SD02` do štyroch skupín. Pri ETICS sa
to rieši presne — substrát sa neberie z kódu, ale z **agregácie z fázy
6a**, ktorá hovorí, na ktorej stene daná krytina naozaj je. `S3` je
jednoznačná sama od seba, lebo ani jeden z jej kódov nezdieľa iná skladba.

`S1`, `S2` a `S6` takú oporu nemajú a **nezaložili sa**. Rozlíšiť ich
geometricky by šlo — `ST01.20` je vegetačná a `ST01.21` kačírková vrstva,
takže `ST01.10`, `PH01` a `SD02` pod nimi by sa dali priradiť podľa
pôdorysného prekryvu — ale je to odvodenie, nie údaj z podkladu.
Nechávam ho na rozhodnutie.

### Čo z #AU

Register #AU (deklarovaná vs geometrická hrúbka) je ten istý prípad ako
ETICS v #AQ: rozdiel vzniká vrstvami bez vlastnej geometrie a §3 ho už
vedie v kategórii „zdokumentovať, neopraviť". Meranie fázy 8 to
potvrdzuje — `FS01.20` nesie 180 mm a výpis S8 uvádza pre tepelnú
izoláciu tiež 180 mm, `FS01.12` nesie 50 a S9 uvádza 50. **Izolačná
vrstva sedí na milimeter**; rozdiel v celkovej hrúbke robia omietky,
lepidlá a penetrácia, teda presne to, čo geometriu nemá.

### Brána `ASR_v16.ifc`

inv 1 geometria 0 zmenených, inv 2 EXPRESS 0, inv 3 10 nových v allowliste,
inv 4 **0**, inv 5 OK, inv 6 OK, inv 7 OK — **zlyhalo 0 z 7**.
Idempotencia overená.

---

## 23. Stav po fázach 1–10

`out/ASR_v16.ifc`, brána celá zelená.

**Uzavreté v registri:** A, B, C, E, F, G, H, I, J, K, L, M, N, O, P, Q, R,
T, V, Y, Z, AA, AB, AC, AE, AF, AH, AI, AJ, AK, AL, AN, AO, AP, AS, AW, AX.

**Zdokumentované, neopravované (D):** AQ, AR, AU, AV a štyri položky bez
kódu z §3.

**Otvorené:**

| # | čo treba |
|---|---|
| AM | 67 occurrences bez pravidla pre `PredefinedType` v §5 — 8 `IfcSlab DZ02`, 19 `IfcCurtainWall`, 22 `IfcFurniture`, 12 `IfcRailing`, 5 `SC01` |
| AT | fyzika materiálov (λ, ρ, c, μ) — vyhradená samostatná fáza |
| AZ | 80 z 97 `IfcDoor` nemá `FillsVoids` |
| BA | `C1-J` vo výkrese `D.1.1.08` chýba |
| Q2 | `PZ01`–`PZ10` nereferencujú ani jeden prvok |
| — | 7× `FS03.01` bez priradenej steny |
| — | `S1`, `S2`, `S6` — skupiny skladieb so zdieľanými kódmi |
| — | okenné hranice, otvorí ich delenie fasády na polia |

**Trvalá medzera:** `data/ASR.ifc` v repe nie je, takže invariant 1 sa
reťazí (referencia = vstup fázy) namiesto porovnania s pôvodným exportom.

---

## 24. Kontrola proti pôvodnému exportu

`data/ASR.ifc` je v repe (Revit 2027, `IFC4X3_ADD2`, 21 MB). Tým sa
zaviera diera otvorená v §9 — invariant 1 sa už nereťazí, ale porovnáva
sa s originálom.

### Geometria: nula

| porovnanie | tvarov | zmenených | stratených | pribudnutých |
|---|--:|--:|--:|--:|
| `ASR.ifc` → `ASR_v16.ifc`, `IfcBuiltElement` | 2495 | **0** | **0** | **0** |
| `ASR.ifc` → `ASR_final_v2.ifc`, `IfcBuiltElement` | 2495 | 0 | 0 | 0 |
| `ASR.ifc` → `ASR_v16.ifc`, `IfcSpace` | 89 → 75 | **0** | 42 | 28 |

**Cez celý reťazec od surového exportu po `ASR_v16.ifc` sa neposunul ani
jeden prvok.** Bboxy sa zhodujú na 6 desatinných miest, čo je v
milimetroch nanometer. To je tvrdenie, na ktorom celý audit stojí, a
prvýkrát je overené proti pravej referencii, nie proti vstupu fázy.

Priestory sú jediné, kde sa geometria hýbala, a ani tam nie zmenou —
42 pôvodných zrušených a 28 nových. Z toho 42 + 22 pripadá na kroky 1–13
(`build_1np_spaces.py`, mimo repa) a 6 na fázu 5c (šachty). Ani jeden
prežívajúci priestor nemá iný tvar.

### Počty, ktoré sedia

`IfcBuiltElement` 2554 → 2568: mínus 36 strešných obalov (fáza 1), plus
2 `IfcRoof` (fáza 1), plus 48 polí LOP (fáza 7). Sedí do kusa.

### GUID účtovníctvo

| úsek | zmizlo | pribudlo | mimo allowlistu |
|---|--:|--:|--:|
| kroky 1–13 (`ASR.ifc` → `ASR_final_v2.ifc`) | 7468 | 3792 | neúčtovateľné |
| **fázy 1–10** (`ASR_final_v2.ifc` → `ASR_v16.ifc`) | **560** | **1118** | **0** |

560 + 1118 = 1678, čo je presne veľkosť kumulatívneho allowlistu zo
všetkých krokov. **Každý GUID, ktorý tento repo zrušil alebo vytvoril, je
vysvetlený.**

Kroky 1–13 v repe nie sú, takže ich 11 260 zmien nemá zapísané očakávania
a účtovať sa voči nim nedá — test by meral cudziu prácu. Účtovníctvo
tohto repa preto začína pri `ASR_final_v2.ifc`. Zapísané v
`tests/known_baseline.json` ako `PIPELINE_1_13`, aby invariant 1 vedel,
čo nie je jeho.

### Testy

`pytest` **9 z 9 prechádza**, vrátane pomalej kontroly geometrie proti
`data/ASR.ifc`.

---

## 25. `BEP_ANNEX.md` a stav #AM

**`BEP_ANNEX.md`** doplnený. §7 ho žiadal už vo fáze 0 a v repe nebol.
Zbiera rozšírenia SNIM, šesť odchýlok od dokumentovaného IFC vzoru,
rozhodnutia o triede a type bez excelu, zápis vzduchovej dutiny, vady
podkladu a zoznam toho, čo model nemá.

**#AM sa zmenšilo o schémový nález.** `IfcCurtainWallTypeEnum` obsahuje
iba `USERDEFINED` a `NOTDEFINED`, takže na 67 fasádach a poliach LOP nie
je čo nastaviť — `NOTDEFINED` je jediná zmysluplná hodnota, ak sa nezavedie
vlastný `ObjectType`. Tá časť #AM je uzavretá schémou, nie rozhodnutím.

Zvyšok #AM na `ASR_v16.ifc` (114 occurrences bez `PredefinedType`, z toho
67 fasád vyššie):

| trieda | kód | ks | čo k tomu treba |
|---|---|--:|---|
| `IfcFurniture` | `VP02`, `OV02`, `OV04` | 21 | enum ponúka len nábytok (`CHAIR`, `DESK`, …); tieto sú stavebné výrobky, takže otázka je skôr na triedu než na typ |
| `IfcRailing` | `ZV01`, `KV02` | 12 | legenda hovorí „schodišťové zábradlie výšky 1000 mm" — `GUARDRAIL` alebo `BALUSTRADE`, rozhodnutie |
| `IfcSlab` | `DZ02` | 8 | §5 pravidlo nemá |
| `IfcStair`, `IfcStairFlight` | `SC01`, `SD04` | 5 | enum má 15 hodnôt podľa tvaru ramena, treba výkres |

---

## 26. S1, S2, S6 — pokus o geometrické odvodenie a prečo neprešiel

Skúsil som priradiť zdieľané kódy tou istou metódou, akou fáza 7 rozdelila
polia LOP: nájsť značkovú vrstvu (`ST01.20` vegetácia, `ST01.21` kačírek,
`PD03.30` dutinová podlaha) a zobrať pod ňou prvky `ST01.10`, `SD02`
a `PH01`, ktoré s ňou pôdorysne prekrývajú.

**Nefunguje to a skript som zahodil.** Výsledok bol na prvý pohľad zlý:
do `S1` padli 2 z 25 `ST01.10`, kým `S6` pritiahlo 21 podhľadov od dvoch
značiek. Meranie ukazuje prečo:

| kód | ks | zvislý rozsah | plocha jedného prvku |
|---|--:|---|---|
| `ST01.10` | 25 | 13250 … 17343 | 1.0 – 676.9 m² |
| `ST01.20` | 18 | 13483 … 17503 | 24.0 – 102.9 m² |
| `ST01.21` | 25 | 13484 … 17144 | **0.1 – 17.8 m²** |
| `SD02.03` | 4 | 4600 … 13250 | 693 m² |
| `PH01.10` | 14 | 2600 … 12263 | 2.3 – 693 m² |

Vrstvy nie sú po jednej na plochu, ale rozsekané na kusy od decimetra
štvorcového po sedemsto metrov, a rozprestierajú sa cez **obe** úrovne
strechy naraz. Prekryv „menší v väčšom" preto spája veci, ktoré spolu
nesúvisia, a zároveň míňa tie, ktoré súvisia.

**Vyriešené v §28** — pravidlo od Samuela („kačírek je pri atikách asi
600 mm od kraja") sa ukázalo byť v modeli už zakódované a chybu v mojom
teste odhalilo.

Zvyšných päť skupín z fázy 8 tým nie je dotknutých — tie stoja na
jednoznačných kódoch a na agregácii, nie na tomto odhade.

---

## 27. Akceptačné meranie `ASR_v16.ifc`

`src/report_final.py` — prejde tvrdenia registra a odmeria ich naraz.
Nič nemení, dá sa pustiť na ktorýkoľvek medzivýstup.

| vec | hodnota |
|---|---|
| occurrences spolu | 2802 |
| z toho s plným SNIM kódom | **2611** |
| duplicitných plných kódov | **0** |
| `IfcTypeObject` | 120 |
| typov s viac než jedným `IfcRelDefinesByType` | **0** |
| netypovaných prvkov | **0** (porty a strešné obaly sa nerátajú) |
| rovnomenných typov | 5 — zámerne, kód nesie užitie |
| priestorov | 75, spolu **2024.91 m²** |
| bez `Qto_BodyGeometryValidation` | **0** |
| prvkov v miestnostiach / v podlažiach | 136 / 405 |
| `IfcRelSpaceBoundary` | 649, z toho 83 s `ParentBoundary` |
| `IfcZone` / `IfcSystem` / `IfcGroup` | 13 / 16 / 21 |
| prázdnych `IfcPropertySet` | **0** |
| vlastností `Status` | **209** |
| vzduchových vrstiev (void + `IsVentilated`) | 4 |
| occurrences bez `PredefinedType` | 114, z toho 67 `IfcCurtainWall` |

**Dve čísla, ktoré najprv vyzerali ako strata dát a neboli.** `Status`
vyšiel na nulu, lebo som ho hľadal medzi `IfcPropertySingleValue` — je to
`IfcPropertyEnumeratedValue` a je ho 209, presne ako uvádza §11.
A „53 netypovaných" bolo 51 `IfcDistributionPort`, ktoré sa netypujú, plus
2 agregujúce `IfcRoof` z fázy 1, ktoré typ nemajú zámerne. Skutočný počet
je 0. Obe merania sú v skripte opravené aj s poznámkou, aby na to
nenaletel nikto ďalší.

---

## 28. Fáza 8b — S1, S2 a S6 doriešené

`out/ASR_v16.ifc` → `out/ASR_v17.ifc`, `src/29_skladby_geom.py`.

Podnet Samuela: *„kačírek je pri atikách a stenách asi 600 mm od kraja"*,
plus otázka, či plochy nerozlišuje sufix `a`/`b` v názve vrchnej vrstvy.

### Čo z toho platí a čo nie

**Sufix nepomáha.** `a`/`b` majú len typy `ST01.10a` a `ST01.10b`
a rozlišujú klinovú izoláciu od rovných dosiek. Vrchné vrstvy majú typy
`ST01.20` a `ST01.21` bez sufixu.

**Pravidlo so 600 mm platí a je merateľné.** Menší rozmer pôdorysu:

| kód | n | min | medián | max |
|---|--:|--:|--:|--:|
| `ST01.20` vegetácia | 18 | 4195 | 4555 | 9750 mm |
| `ST01.21` kačírek | 25 | **360** | **520** | 3975 mm |

Dvadsaťtri z 25 kačírkových kusov má menší rozmer do 1000 mm — úzke pásy
po obvode, presne ako hovorí pravidlo. Ktorá plocha je ktorá sa teda
nemusí odvodzovať z pôdorysu strechy; model to už nesie.

### Prečo prvý pokus zlyhal

Podmienka znela „vrch prvku pod spodkom značky". Lenže klinová izolácia
sa s krytinou **prerastá** — medzera vychádza medián **−144 mm** — takže
tá podmienka vylúčila skoro všetko. Nová podmienka pracuje s **pásmom**:
prvok patrí do skladby, ak pôdorysne prekrýva značku a jeho zvislý rozsah
zasahuje do pásma od spodku značky nadol.

### Hĺbka pásma z citlivostnej skúšky

| hĺbka | S1 | S2 | S6 |
|--:|--:|--:|--:|
| 1200 | 43 | 51 | 15 |
| 1500 | 44 | 52 | 16 |
| **2000** | **45** | **53** | **17** |
| 3000 | 45 | 53 | **30** |

`S1` a `S2` sú stabilné celé pásmo. `S6` skočí zo 17 na 30 medzi 2000
a 3000 — jeho značkou je celá podlahová doska, takže hlbšie pásmo
prepadne do podlažia pod ňou. Zvolených **2000 mm**, čo je vnútri
stabilnej oblasti pre všetky tri. Skúšku vie ktokoľvek zopakovať cez
`--hlbka`.

### Výsledok

| skupina | prvkov | zloženie |
|---|--:|---|
| `S1` vegetácia | 45 | 18 `ST01.20` + 23 `ST01.10` + 2 `SD02` + 2 `PH01` |
| `S2` kačírek | 53 | 25 `ST01.21` + 24 `ST01.10` + 2 `SD02` + 2 `PH01` |
| `S6` kancelárie | 17 | 2 `PD03.30` + 7 `SD02` + 8 `PH01` |

**Skupiny sa prekrývajú a majú.** Dvadsaťtri izolačných dosiek patrí do
`S1` aj `S2` naraz, lebo kačírkový pás je 600 mm okraj tej istej strešnej
plochy, pod ktorou je vegetácia. Práve preto sa priraďovalo po kuse,
nie po kóde.

Všetkých **osem skladieb** z výpisu je tým založených.

Brána: inv 1 geometria 0 zmenených, inv 2 EXPRESS 0, inv 3 6 nových
v allowliste, inv 4–7 OK — **zlyhalo 0 zo 7**. Idempotencia overená.

---

## 29. Pred fázou 11 — sonda k triedam a rozhodnutia z 10. 8.

Vstup fázy 11 je `out/ASR_v17.ifc`. Reťaz `ASR_final_v2 → v3_a → v3 → … →
v16 → v17` je neprerušená, každý skript berie výstup predošlého; `v17` je
posledný a `report_final.py` na ňom prešiel.

Sonda odpovedala na desať otázok, ktoré zostali po fáze 8b. Tri z nich
odpovedali inak, než znel predpoklad — pri každej je uvedené meranie, nie
dojem.

### Čo sonda namerala

**`DZ02` nie je doska a nie je podklad pod karuselom.** Osem kusov sú
**zvislé pásy 100 mm hrubé a 700 mm vysoké** na kóte −1600…−900, teda pod
základovou doskou `ZD02` (−800…−300) aj pod podkladným betónom `DZ01`
(−900…−800). Tvoria dva uzavreté obdĺžniky a tie sú **súosé s výťahovými
šachtami**: stred (42510, −166) sedí so šachtou `2.15` (`VT01 02`), stred
(38785, 2109) so šachtou `2.18` (`VT01 01`) — obe na milimeter. Je to
podkladný betón na stenách dvoch **výťahových jám**. Potvrdzuje to §14,
kde už bolo namerané, že otvor `SD02` prelieza pod základovú škáru.

**`FS03.01` nie je hydroizolácia a `IfcCovering` nie je dedičstvo.** Popis
je `Izolace_ZD_120`, materiál `Izolace XPS` 120 mm, kóta −800…0. Je to
**obvodová izolácia základovej dosky**: zvislé pásy po celom obvode budovy —
33500 sever, 21380 východ, 21260 západ, 16385 + 14560 juh, plus výbežok
2555 × 1100 na juhu a jeden vnútorný kus pri jadre. `IfcCovering /
INSULATION` je teda vecne správne. Otvorené zostáva len to, do čoho má
tých 7 voľných kusov agregovať — nelieha na stenu, ale na hranu základovej
dosky, preto ich fáza 6a nenašla.

**Schodisko už zgrupené je.** Tri `IfcStair` (`SC01.0001`–`.0003`), každé
agreguje **2 ramená + 2 podesty + 3 zábradlia**. Strešné `SH04.03.0001` na
4NP je zvlášť a agreguje 2 schodnice + rameno + 2 zábradlia `KV02`. Obava,
že sú prvky porozdeľované podľa toho, čo dovolil Revit, sa nepotvrdila —
delenie je vecné. Ramená sú 4500 mm na 2NP a 3NP a 4650/5100 mm na 1NP,
čo je rozdiel podlažnej výšky, nie chyba. Chýba jediné: `PredefinedType`.

**#AZ bolo v origináli.** `data/ASR.ifc` má tých istých **80 z 97**
`IfcDoor` bez `FillsVoids`, rovnako **26 z 26** `IfcWindow` a **61**
`IfcOpeningElement` — číslo do jedného sedí s `ASR_v17.ifc`. Pipeline vadu
nespôsobila ani nezmenila. Prakticky to znamená, že hostiteľská stena sa
nedá prečítať zo vzťahu; fáza 6b ju pri 52 dverách odvodila z polohy
a zapísala cez `IfcRelSpaceBoundary.ParentBoundary`, čo je väzba, ktorú
model nesie namiesto `FillsVoids`.

**`VP02` potvrdil model sám.** Popis je doslova `Bezbariérové WC – madlo
sklopné`, materiál `Chrom`, 12 kusov po dvoch v šiestich bezbariérových WC.

**`OV02` sú prístrešky vstupov.** Sedem kusov na kóte 3720…4310, vyložené
1500 mm **von** z obvodu budovy (obvod je X 29885…63385, Y −8141…13239),
vždy nad vstupom. `IfcFurniture` je zjavne zlé.

**Dvadsiaty druhý `IfcFurniture`.** §25 uvádzalo 21 a menovalo `VP02`,
`OV02`, `OV04`. Chýbal `ZV04.01` „Žebřík s košem" — rebrík s ochranným
košom na strechu.

### Rozhodnutia Samuela z 10. 8.

| vec | rozhodnutie |
|---|---|
| `ZV01.01` (4 ks, „Zábradlí 1000 se svislou výplní") | **`GUARDRAIL`** — spec: *„designed to guard human or vehicle occupants from falling off a stair, ramp or landing"* |
| `ZV01.02` (6 ks, „Madlo 1000") | **`HANDRAIL`** — spec: *„structural support for loads applied by human occupants (at hand height). Generally located adjacent to ramps and stairs"* |
| `VP02` | sklopné madlá bezbariérového WC, teda **nie nábytok** |
| `OV04.03` | zástupný kváder, na nič sa nenapája — je to **diera s rúrkou v atike** |
| #Q2 | väzbu zón odvodiť **geometricky aj logicky** |
| #AT fyzika materiálov | **zatiaľ neriešiť** |
| rozsah | fázy postupne, po jednej, brána po každej |

`KV02` (2 ks, „Madlo – kovové", zábradlia strešného schodiska) spadá pod to
isté pravidlo ako `ZV01.02` → `HANDRAIL`. Rozhodnutie o `ZV01` sa ho
menovite netýkalo, treba ho potvrdiť spolu s fázou 12.

### Návrhy, ktoré čakajú na potvrdenie

| vec | návrh | opora / čo ešte treba |
|---|---|---|
| `SC01` (3 ks) | `IfcStair / HALF_TURN_STAIR` | spec: *„a stair making a 180° turn, consisting of two straight flights connected"* — sedí na geometriu dvoch ramien s podestou medzi nimi |
| `SD04.0005/.0006` | `STRAIGHT` | ostatné 4 ramená ho už majú, aj ich typ |
| `ZV04.01` | `IfcStair / LADDER` | IFC4.3 hodnotu má: *„a series of bars or steps between two upright elements used for climbing"* |
| `OV02` (7 ks) | `IfcShadingDevice / AWNING` | spec: *„a rooflike shelter … extending over a doorway … in order to provide protection"*. Pred zápisom porovnať ešte s `IfcCovering` a `IfcBuiltElement` |
| `OV04.03` (2 ks) | `IfcWasteTerminal`, `PredefinedType` otvorený | enum má `ROOFDRAIN`, `GULLYSUMP`, `FLOORWASTE` — ani jeden nie je „prepad". `USERDEFINED` + `ObjectType = 'Poistný prepad'` je čestnejšie než natiahnuť `ROOFDRAIN` |
| `DZ02` (8 ks) | trieda otvorená | `IfcSlab` pre zvislý pás nesedí; `DZ01` (vodorovný podkladný betón) je `IfcSlab`, takže rozhodnutie ovplyvní oba |
| `FS03.01` (7 ks) | agregácia otvorená | buď do `ZD02`, alebo nechať samostatné a zdokumentovať |
| #AZ | nechať zdokumentované | oprava by znamenala vyrobiť 80 `IfcOpeningElement`, čo §8 zakazuje. Rozhodnutie o rozsahu zatiaľ nepadlo |

### Rozdelenie na fázy

| fáza | skript | obsah |
|---|---|---|
| **11** | `30_fix_classes_2.py` | prekvalifikovanie: `OV02` 7, `VP02` 12, `OV04.03` 2, `ZV04.01` 1, `DZ02` 8 |
| **12** | `31_predefined_types.py` | `PredefinedType` na schodiskách, zábradliach a prekvalifikovaných prvkoch — uzavrie #AM |
| **13** | `32_zones_pz.py` | #Q2 |
| **14** | | `FS03.01` — až po rozhodnutí |

Prečo triedy a `PredefinedType` zvlášť, keď ide o tie isté prvky:
`reassign_class` na occurrence **kaskádovo prepíše zdieľaný typ**, takže
prekvalifikovanie je zásah s vlastným rizikom a vlastnou bránou. Nastavenie
atribútu je proti tomu lacné. Spojiť ich by znamenalo, že pri zlyhaní brány
nevieme ktoré z dvoch ho spôsobilo — presne to, pred čím varuje
`CLAUDE_CODE_START.md` § „Poradie a čo nerobiť naraz".

---

## 30. Fáza 11 — triedny model podruhé

`out/ASR_v17.ifc` → `out/ASR_v18.ifc`, `src/30_fix_classes_2.py`.
Prekvalifikovaných **30 occurrences a 6 typov**.

| kód | ks | pred | po |
|---|--:|---|---|
| `DZ02` | 8 | `IfcSlab` | `IfcWall / SOLIDWALL` |
| `VP02` | 12 | `IfcFurniture` | `IfcRailing / HANDRAIL` |
| `OV02.01`, `OV02.02` | 7 | `IfcFurniture` | `IfcBuiltElement`, `ObjectType = 'Prístrešok vstupu'` |
| `OV04.03` | 2 | `IfcFurniture` | `IfcWasteTerminal / USERDEFINED`, `ObjectType = 'Poistný prepad'` |
| `ZV04.01` | 1 | `IfcFurniture` | `IfcStair / LADDER` |

**`IfcFurniture` je v modeli 0.** Všetkých 22 kusov, ktoré tú triedu niesli,
sú stavebné výrobky a majú teraz triedu podľa toho, čím sú.

### `DZ02` — návrat, nie zmena

Rozhodnutie Samuela znelo *„výťahové jamy sú normálne betón, doska a stena,
netreba to komplikovať, proste nosná konštrukcia"*. Model to potvrdil sám:
v `data/ASR.ifc` je `DZ02` **`IfcWall` s `Pset_WallCommon.LoadBearing = True`**
a vlastným `IfcWallType`. Na `IfcSlab` ju prepísala **pôvodná pipeline
(kroky 1–12, mimo tohto repa)** — trasa naprieč verziami je jednoznačná:
`ASR.ifc` 8× `IfcWall`, `ASR_final_v2.ifc` už 8× `IfcSlab`, a odvtedy
nezmenene až po `v17`. Naše fázy 1–10 sa jej nedotkli.

Fáza 2 potom v dobrej viere premenovala `Pset_WallCommon` na
`Pset_SlabCommon` (#B) a zahodila pri tom `ExtendToStructure`, ktoré je
vlastnosť len steny. Fáza 11 vracia oboje: pset sa volá znova
`Pset_WallCommon` a `ExtendToStructure = False` je prečítané späť
z originálu, nie vymyslené.

`SOLIDWALL` podľa spec: *„A massive wall construction … often masonry or
concrete walls (both cast in-situ or precast) that are load bearing and fire
protecting."* Zvažovaný `RETAININGWALL` (*„supporting wall used to protect
against soil layers behind"*) by tiež sedel na jamu, ale rozhodnutie znelo
nosná konštrukcia, nie oporná.

### `OV02` — prečo nie `IfcShadingDevice`

`AWNING` v `IfcShadingDeviceTypeEnum` znie ako trafa — *„a rooflike shelter …
extending over a doorway … in order to provide protection"*. Entita ako celok
je však definovaná ako ochrana *„from the sunlight, from natural light, or
screening them from view"* a jej vlastná NOTE hovorí, že prvky s **iným
primárnym účelom** patria na `IfcSlab` alebo iné podtypy `IfcBuiltElement`.
Sklenený prístrešok netieni — chráni pred zrážkami. Preto `IfcBuiltElement`,
ktorý je v IFC4.3 inštancovateľný (overené proti schéme, `is_abstract()`
= `False`) a `PredefinedType` **nemá**; význam nesie `ObjectType`, na type
`ElementType`. Docs ten prípad menujú: *„when the concrete entity instantiated
does not have a PredefinedType attribute … in some exceptional leaf classes."*

### `OV04.03` — trieda áno, enum nie

`IfcWasteTerminalTypeEnum` hodnotu pre prepad nemá. `ROOFDRAIN` je *„pipe
fitting … that collects rainwater for discharge into the rainwater system"* —
poistný prepad do systému neústi, ústi voľne von. Preto `USERDEFINED`
s `ObjectType`. Trieda drží rodinu `OV04` pokope; zvyšných 18 kusov ju má
z fázy 10.

**Do `IfcSystem` „Zoskupenie zariadení — strešné vpuste" sa `OV04.03`
nepridal.** Prepad vpusť nie je a názov skupiny by prestal platiť. Členstvo
je samostatné rozhodnutie, nie dôsledok triedy.

### Allowlist a čo v ňom je

Invariant 1 meria bboxy `IfcBuiltElement` a `IfcSpace`. `IfcFurniture` do tej
množiny nepatrí, `IfcRailing`, `IfcStair` a `IfcBuiltElement` áno — takže
**20 prvkov** (12 `VP02` + 7 `OV02` + 1 `ZV04.01`) sa invariantu javí ako
nové tvary. Geometria je pritom nedotknutá a je to zmerané: bboxy všetkých
30 dotknutých prvkov sú v `v17` aj `v18` zhodné na 6 desatinných miest,
množina `GlobalId` je identická, `IfcBuiltElement` neubudlo ani jedno.
Allowlist skript generuje sám z rozdielu tých dvoch množín, nie ručne.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **OK** — 20 v allowliste, 0 zmenených bboxov |
| 2 EXPRESS | **0 hlásení** — vrátane nových `IfcBuiltElement` a `IfcBuiltElementType` |
| 3 GUID | **OK** — 0 zrušených, 0 nových; `reassign_class` zachováva `GlobalId` |
| 4 osirelé | OK |
| 5 prázdne SET | OK |
| 6 jednoznačnosť | OK |
| 7 kontajnment | OK |

**Zlyhalo 0 zo 7.** Idempotencia overená: druhý beh hlási, že všetkých
6 typov triedu už má. `pytest` 8 prešlo.

Pozn. k referencii: `src/gate.py` má default `--reference data/ASR.ifc`, čo
je správne pre reťazovú kontrolu, ale pre fázovú bránu treba
`--reference out/ASR_v17.ifc`. Bez toho brána vypíše všetko, čo spravili
fázy 1–10, a vyzerá to ako 12 778 porušení.

### Posun oproti §29

§29 plánovalo `PredefinedType` **všetkých** prvkov až do fázy 12. Pri
prekvalifikovaní sa to ale oddeliť nedá — na `IfcStair` sa nedá prejsť bez
toho, aby sme povedali `LADDER`. Fáza 11 preto nastavuje enum tam, kde je
súčasťou rozhodnutia o triede. Fáze 12 zostáva **17 occurrences, ktoré si
triedu ponechávajú**: `SC01` 3, `SD04` 2, `ZV01.01` 4, `ZV01.02` 6,
`KV02` 2.

Occurrences bez `PredefinedType`: 114 → **84**, z toho 67 `IfcCurtainWall`
uzavretých schémou (§25) a 17 pre fázu 12.
