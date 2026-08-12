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
| — | skladba vs jej výskyt | **dvojúrovňovo**: `S1` je predpis, `S1.01` a `S1.02` výskyty na nosičoch. Väzba `IfcRelAggregates`, členstvo **len na výskytoch**. Nie `IfcRelDefinesByType` — typ skupiny v schéme neexistuje | Samuel + spec, §43 |
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
| AY | **H** | ~~`#16` `IfcGeometricRepresentationSubContext` „Box" nepoužitý (0 reprezentácií). Má 0 inverzov, lebo väzbu na rodiča drží **dopredný** `ParentContext`, nie inverzný `HasSubContexts` — do whitelistu invariantu 4 patrí alebo sa má zmazať~~ — **zmazaný**, fáza 18, §37. Rozhodnutie Samuela: *„tak ho zmaž, keď to nič nepokazí."* Overené: 0 reprezentácií, 0 detí, 0 inverzov |
| AJ | **H** | ~~2653 hodnôt s FP šumom~~ — fáza 9a, zaokrúhlené na 6 desatinných miest. Opravených **15135** (širšie kritérium než pôvodný odhad), najväčšia oprava 5e-07 |

### Triedny model
| # | | vec |
|---|---|---|
| T | **H** | ~~`ST01.*` vrstvy skladby vedené ako `IfcRoof`~~ — 92 vrstiev + 10 typov na `IfcCovering`, `50c26c5` |
| V | **H** | ~~36 prázdnych `IfcRoof` obalov 1:1 nad `IfcSlab`~~ — zrušené, `50c26c5` |
| AL | **H** | ~~`IH01.01` ako `IfcWall / STANDARD`~~ → `IfcCovering / MEMBRANE`, 4 occ + typ, `45ea35d` |
| AB | **H** | ~~blok 0.41×1.25×0.30 ako `IfcStair`~~ → `IfcFooting / PAD_FOOTING`, `ZD02.05`, `45ea35d` |
| AC | **H** | ~~`ZD02.03/.04` `FLOOR`; occurrence `ZD02.01` typovaná `ZD02.04`~~ — typ premenovaný, `BASESLAB`, `45ea35d` |
| AM | **H** | ~~`PredefinedType` chýba na 383~~ — steny hotové (`45ea35d`): 159 occ podľa §5 + všetkých 12 `IfcWallType`. Číslo 383 = **314** `NOTDEFINED` + **69** `IfcFlowTerminal`, ktoré atribút v IFC4X3 nemajú vôbec (fáza 10). Otvorených ostáva **67** occurrences bez pravidla v §5: 8 `IfcSlab DZ02`, 19 `IfcCurtainWall`, 22 `IfcFurniture`, 12 `IfcRailing`, 5 `SC01`. **Odmerané na `ASR_v17.ifc` (§29):** 114 = 67 `IfcCurtainWall` (uzavreté schémou, §25) + 22 `IfcFurniture` + 12 `IfcRailing` + 8 `IfcSlab` + 3 `IfcStair` + 2 `IfcStairFlight`. §25 uvádzalo 21 `IfcFurniture` — chýbal v ňom `ZV04.01`. Rozhodnutia sú v §29. **Fáza 11 (§30) uzavrela 30 z nich** prekvalifikovaním — 114 → 84 bez `PredefinedType`, z toho 67 `IfcCurtainWall` uzavretých schémou. Fáza 12 (§31) doplnila zvyšných 17 a **#AM je tým uzavreté**: bez `PredefinedType` zostalo 67 occurrences a všetkých 67 je `IfcCurtainWall` |
| AN | **H** | ~~`KV01` `MOLDING`~~ → `COPING`, 2 occ + typ, `45ea35d` |
| AO | **H** | ~~fasádne zateplenia mimo agregácie~~ — atika fáza 1 (`50c26c5`, 8× `IfcRelAggregates`, 18 dielov); zateplenia fáza 6a, 14 dielov `FS01` do 10 stien. ~~Otvorené zostáva 7 `FS03.01`~~ — stena sa nenašla, lebo žiadnu nepokrývajú: dosadajú na základovú dosku. Agregované do `ZD02.01.0001`, fáza 14, §33. **#AO uzavreté** |

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
| BA | O | **`C1-J` vo výkrese `D.1.1.08` chýba** — južný pohľad má v treťom poli 1NP kód `C1-S`, ktorý zároveň patrí severnému poľu. Vada podkladu rovnakej povahy ako #AV. Model používa `C1-J` (rozhodnutie Samuela), odchýlka **nejde do BEP** — rozhodnutie Samuela 10. 8.: *„nedávaj nič do BEPu, netreba, stačí v nejakých podporných dokumentoch.“* Zostáva teda tu |
| AZ | **D** | ~~80 z 97 `IfcDoor` nemá `FillsVoids`~~ — **vypustené z rozsahu**, rozhodnutie Samuela 10. 8.: *„vypustiť celé, ak to rovnako bolo aj v `ASR.ifc`.“* Bolo: originál má tých istých 80 z 97, rovnako 26 z 26 `IfcWindow` a 61 `IfcOpeningElement` (§29). Vada prišla z Revit exportu, oprava by znamenala vyrobiť 80 `IfcOpeningElement`, čo §8 zakazuje. Ani 20 dverí bez `ParentBoundary` sa nedopĺňa |
| Z | **H** | ~~22 rekonštruovaných priestorov bez `Qto_BodyGeometryValidation`~~ — dopočítané z geometrie, `20_fix_spaces.py` |
| Q | **H** | ~~3NP nemá prenajímateľnú zónu~~ — fáza 5c, §15. **Premisa „nová zóna = vyrobiť geometriu" bola nesprávna** — `IfcZone` je podtyp `IfcSystem`/`IfcGroup`, nie `IfcProduct`, a spec hovorí doslova *„A zone does not have its own shape representation"* a *„it can not define an own geometric representation and placement"*. Rozhodnuté — vnorený `IfcZone` s 11 nájomnými priestormi 3NP (584.06 m² podľa legendy `D.1.1.03`) vložený do `IfcZone` `Pronajmutelné`. WR1 `IfcSpace` aj `IfcZone` ako členov výslovne povoľuje |
| Q2 | **H** | ~~`PZ01`–`PZ10` nereferencujú ani jeden priestor~~ — fáza 13, §32. Pôvodne: — majú vlastnú geometriu a `PredefinedType = OCCUPANCY`, ale **nereferencujú ani jeden prvok či priestor** (`IfcRelReferencedInSpatialStructure` 0×). Prenajímateľnosť tak dnes nesie iba objem, nie väzba na miestnosti. Nájdené sondou §14. Rozhodnuté (§29): väzbu **odvodiť geometricky aj logicky**. Doplnených 10 `IfcRelReferencedInSpatialStructure` na 42 priestorov; zón bez väzby 0 |
| R | **H** | ~~súčet plôch vs 2031.95 z handoveru~~ — zosúhlasené: 1NP 613.55 + 2NP 665.74 + 3NP 664.11 + 4NP 69.47 = **2012.88 m²** na 69 priestoroch. Rozdiel 19.07 m² je v handoveri, nie v modeli |
| AW | **H** | ~~85 častí fasády súčasne agregovaných aj kontajnovaných~~ — fáza 6a, časti odobrané z kontajnmentu po overení, že ich celok v priestorovej štruktúre je. Pôvodne: **85 častí** — 70 `IfcMember` `LOP02` a 9 `AZ01`, 6 `IfcPlate` `TI06.01`. Časti sedia o podlažie vyššie než ich `IfcCurtainWall` (`PL01` v 3NP → časti v 4NP; `LP03.01` v 4NP → časti v 5NP). Invariant 7 na základni zlyháva, nie až po fáze 1 |
| BC | **H** | ~~117 prvkov visí o podlažie vedľa, lebo pásmo sa počítalo z `Elevation`~~ — fáza 19, §39. `Elevation` je čistá podlaha, ale stĺp aj priečka toho istého podlažia začínajú na **vrchu nosnej dosky**, teda 150 mm nižšie. Preto bolo 24 stĺpov, 83 stien a 8 strešných vpustí zaradených o podlažie nižšie a **tá istá rada stĺpov bola rozdelená medzi dve podlažia** — to je „random" z Samuelovho hlásenia. #G z fázy 6a vpuste z openspace dostalo, ale do 3NP namiesto 4NP. Pásmo sa odteraz počíta z dosiek; stráži to invariant 8 |
| BD | **H** | ~~dvere a stĺpy len na podlaží, nie v miestnostiach~~ — fáza 20, §40. **Rozhodnutie 24 sa mení**: exkluzivita kontajnmentu neznamená „žiadna miestnosť", ale „jedna miestnosť". 84 dverí kontajnovaných do obsluhovanej miestnosti (nie do chodby), 35 stĺpov do miestnosti, v ktorej stoja, 17 stĺpov na rozhraní ostáva na podlaží s referenciami na obe miestnosti. Plus 22 skladieb podlahy a podhľadov k správnej miestnosti, 2 podlahové vpuste a 48 chýbajúcich hraníc dverí |

### Materiály a skladby
| # | | vec |
|---|---|---|
| AH | **H** | ~~164 `IfcMaterialConstituent` bez `IfcShapeAspect`~~ — 0 na occurrence úrovni, `70d17af` |
| AI | **H** | ~~„Dřevo obecné" na krídle LOP~~ — vyriešilo sa rozhodnutím 27, `70d17af` |
| AQ | **D** | ~~layer sety nesedia s výpisom~~ — **prvá polovica bola nesprávne prečítaná**, viď §21. Spádové kliny v modeli **sú**: `ST01.10a` (23 ks) nesie `Izolace EPS spádové kliny`, `ST01.10b` (2 ks) rovné dosky. Hydroizolácia patrí do druhej vrstvy strechy a v modeli tam aj je — `ST01.20` a `ST01.21` nesú po dvoch asfaltových pásoch. Zostáva ETICS: krytina nesie 1 vrstvu (izoláciu) zo 6 vo výpise; lepidlo, stierka, sieťka a omietka nemajú vlastnú geometriu a podľa §2 a §3 sa hrúbkový rozdiel **dokumentuje, nedopĺňa** |
| AU | **D** | ~~deklarovaná vs geometrická hrúbka~~ — **zdokumentované, neopravuje sa.** Rozhodnutie Samuela 10. 8.: *„v `Qto` musí byť geometria, do `Description` keď tak rozsah, ale asi ani to nie — proste tam je sklon.“* Sú to **dve rôzne príčiny**: `ST01.10` 234–354/204 je spádový klin, teda sklon, a jedna hodnota hrúbky preň neexistuje; `FS01.10` 210/180, `FS01.11` 141/120, `FS01.12` 80/50 a `FS01.20` 210/180 je ETICS, kde lepidlo, stierka, sieťka a omietka vlastnú geometriu nemajú — to je #AQ. `Qto` v oboch prípadoch nesie skutočnú geometriu |
| AS | **H** | ~~materiál „Výchozí" ako dutinová podlaha v `PD03.*`~~ — fáza 8, §22: štyri vrstvy `PD03.*` nesú `IsVentilated` a materiál nemajú, ako žiada `IfcMaterialLayer` §8.10.3.6.1. Overené na `ASR_v21.ifc`: 0 vrstiev s materiálom „Výchozí". Riadok registra zostal omylom na **O**, hoci §23 ho medzi uzavretými uvádza |
| BB | **H** | **fyzika materiálu platí pre jednu skladbu, materiál ju nesie pre všetky.** IFC vlastnosti visia na `IfcMaterial`, nie na vrstve, takže `Izolace XPS` nesie λ=0,036 z `FS01.11` aj v `FS03.01`, `ST01.32` a `PD02.11` — a tie tri **výpis `D.1.1.09` neuvádza vôbec**. To isté pri `Izolace minerální` (doložené `FS01.10/.12/.20`, použité aj v `TI06.01`) a `Izolace EPS` (doložené `PD02`). **Rozhodnuté** (Samuel, 10. 8.): *„ber to tak, že majú rovnaké vlastnosti všetky XPS."* Materiál sa nerozdeľuje; to isté sa uplatňuje na minerálnu izoláciu a EPS. Zistené vo fáze 17 |
| AT | **H** | ~~λ, ρ, c, μ z výpisu nie sú v `Pset_Material*`~~ — fáza 17, §36. Deväť materiálov, 15 `IfcMaterialProperties`, plus tri chýbajúce odvodené jednotky do `IfcUnitAssignment` |
| BF | **H** | ~~skladby striech sú jedna skupina na veľkej aj malej streche~~ — fáza 21, §43. `S1` sa rozdelila na `S1.01` (4NP, 38 prvkov) a `S1.02` (5NP, 7), `S2` na `S2.01` (48) a `S2.02` (5). Všetkých osem skladieb je dvojúrovňových: 8 predpisov, 15 výskytov, 193 členstiev. Stráži invariant 9 |
| BE | **H** | ~~`S3` obsahuje 22 prvkov mimo 1NP~~ — fáza 22, §45. Skladba sa volá „Skladba základovej dosky a podlahy v 1NP", ale fáza 21 ju rozložila na 1NP 32, 2NP 9, 3NP 9, 4NP 4. Členstvo prišlo z fázy 8 pravidlom „všetky prvky kódu", čo odpovedá na inú otázku než „patrí do tejto skladby". **Podklady skontrolované, tri nezávislé doklady:** `PD02` je vo výpise `D.1.1.09` presne raz a je to S3; S3 stojí na základovej doske `ZD02.01` (vrstva 7), ktorá je v modeli jediná a na 1NP, kým podlahy vyšších podlaží ležia na stropných doskách `SD02`; a výpis predpisuje EPS **200 mm**, kým všetkých 22 prvkov na 2NP–4NP má EPS **50 mm**. **Rozhodnutie Samuela (12. 8.):** prvky zo skupiny vypadli a novú skupinu nedostali — výpis pre ne skladbu nemá. `S3` má 32 prvkov a jediný výskyt `S3.01` |

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

**Agregujú sa aj skupiny, a to je iná os.** Od fázy 21 je `S1` predpis
a `S1.01` s `S1.02` sú jeho výskyty, zavesené cez `IfcRelAggregates`
(§43). Tabuľka vyššie sa týka prvkov — otázka „je časť fyzicky zviazaná
s celkom" na skupiny nesadá, lebo skupina teleso nemá. Tam rozhoduje
`Decomposes : SET [0:1]`: výskyt patrí práve jednej skladbe.

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
| — | ~~`S1`, `S2`, `S6` — skupiny skladieb so zdieľanými kódmi~~ — založené vo fáze 8b (§28), rozdelené na výskyty vo fáze 21 (§43) |
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

---

## 31. Fáza 12 — `PredefinedType`, #AM uzavreté

`out/ASR_v18.ifc` → `out/ASR_v19.ifc`, `src/31_predefined_types.py`.
Nastavených **21 hodnôt** na 17 occurrences a 4 typoch.

| kód | trieda | `PredefinedType` | occ | typ |
|---|---|---|--:|--:|
| `SC01` | `IfcStair` | `HALF_TURN_STAIR` | 3 | 1 |
| `SD04` | `IfcStairFlight` | `STRAIGHT` | 2 | — (typ ho už mal) |
| `ZV01.01` | `IfcRailing` | `GUARDRAIL` | 4 | 1 |
| `ZV01.02` | `IfcRailing` | `HANDRAIL` | 6 | 1 |
| `KV02` | `IfcRailing` | `HANDRAIL` | 2 | 1 |

**Bez `PredefinedType` zostalo 67 occurrences a všetkých 67 je
`IfcCurtainWall`** — uzavreté schémou v §25, nie rozhodnutím. Sedemnásť
`OV02` a spol. atribút nemá vôbec, lebo `IfcBuiltElement` ho nedefinuje
(§30). **#AM je tým uzavreté.**

### `HALF_TURN_STAIR` je doložený geometriou, nie popisom

Skript pre každé `SC01` spočíta smer stúpania oboch ramien — ťažisko XY
vrcholov v spodnej desatine výšky proti ťažisku v hornej desatine — a
vyžaduje, aby zvierali viac než 150°. Namerané **180,0° na všetkých troch**.
Keby ramená stúpali rovnakým smerom, správna hodnota by bola
`TWO_STRAIGHT_RUN_STAIR` a skript by zastal.

Skript sa navyše pred zápisom presvedčí, že popis typu sedí s očakávaním
(`'Zábradlí 1000 se svislou výplní'`, `'Madlo 1000'`, `'Madlo – kovové'`).
Keby sa kód medzitým použil na iný výrobok, zastane radšej, než by nastavil
enum naslepo.

### Pasca, na ktorú prvý beh naletel

`np.array(create_shape(settings, e).geometry.verts)` v jednom výraze vracia
pohľad do pamäte **dočasného** objektu, ktorý medzitým zanikne. Numpy potom
číta uvoľnenú pamäť: bboxy vychádzajú s nulami a hodnotami rádu `1e260`.
Prvý beh kvôli tomu namemeral medzi ramenami 1,8° a skript správne zastal —
ale z nesprávneho dôvodu. Shape sa musí držať v premennej.

To isté sa týka overenia geometrie v §30. Bolo **premerané znova** správnou
metódou a záver platí: 30 dotknutých prvkov, **0 so zmenenou geometriou**,
množina `GlobalId` identická. Do `CLAUDE_CODE_START.md` § „Pravidlá pre
skripty" patrí k pravidlu *„`geom.iterator`, nie opakované `geom.create_shape`"*
ešte veta o držaní shape v premennej.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **OK** — allowlist prázdny, `PredefinedType` geometriu nemení |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | **OK** — 0 zrušených, 0 nových |
| 4–7 | OK |

**Zlyhalo 0 zo 7.** Idempotencia overená (druhý beh 0 zmien), `pytest` 8/8.

---

## 32. Fáza 13 — #Q2, zóny `PZ01`–`PZ10` naviazané na priestory

`out/ASR_v19.ifc` → `out/ASR_v20.ifc`, `src/32_zones_pz.py`.
Doplnených **10 `IfcRelReferencedInSpatialStructure`** na **42 priestorov**.
Zón bez väzby: **0**.

### Schéma to výslovne povoľuje

`IfcRelReferencedInSpatialStructure` má pravidlo `AllowedRelatedElements`,
ktoré vkladanie priestorových prvkov do priestorových prvkov zakazuje —
s výnimkou, ktorá je presne náš prípad: *„an `IfcSpace` can be referenced by
another spatial structure element, in particular by an `IfcSpatialZone`.
IFC4-CHANGE The relaxation to allow IfcSpace has been included."*
Že to platí aj v praxi, potvrdila EXPRESS validácia — 0 hlásení.

### Prečo nie bbox

`PZ01` má bbox celého pôdorysu budovy (33500 × 21500), ale jej skutočná
plocha je **611.54 m²**. Bboxom by pohltila `PZ03`, `PZ07`, `PZ08` aj
`PZ09`, ktoré ležia vedľa nej. Pôdorys sa preto zostavuje ako únia
trojuholníkov telesa premietnutých do XY a priradzuje sa podľa **podielu
plochy priestoru vnútri zóny**, pri prekryve zvislých rozsahov.

| zóna | plocha | priestorov | najmenší podiel |
|---|--:|--:|--:|
| `PZ01` Zóna 1 – Retail + Lobby | 611.54 m² | 18 | 1.00 |
| `PZ02` Zóna 4 – Spoločné | 43.95 m² | 2 | 1.00 |
| `PZ03` Zóna 4 – Spoločné | 43.04 m² | 2 | 1.00 |
| `PZ04`–`PZ09` Zóna 5 – Technické | 96.11 m² | 8 | 0.84 |
| `PZ10` Nájomný priestor | 590.31 m² | 12 | 0.97 |

Prah je **necitlivý**: 0.3, 0.5 aj 0.7 dávajú rovnakých 42 väzieb, lebo
namerané podiely sú 0.84 až 1.00. Skript citlivosť vypisuje a zastane,
ak by zóna vyšla prázdna alebo ak by priestor spadol do dvoch zón —
ani jedno nenastalo, prekryv zón je nulový.

### Čo zónu nedostalo a prečo to nie je vada

Z 75 priestorov dostalo zónu 42. Zvyšných 33:

| koľko | čo | prečo |
|--:|---|---|
| 22 | celé 3NP | `PZ01`–`PZ10` na kóte 3NP teleso **nemajú**. Prenajímateľné priestory 3NP nesie `IfcZone` „Nájomné priestory 3NP" z fázy 5c (#Q, §15) — tam je zdrojom legenda, nie geometria |
| 9 | služobné priestory 2NP | elektrorozvodňa, výťahová lobby, technická miestnosť, štyri šachty, schodisko. `PZ10` sa volá „Nájomný priestor" a tie do nej nepatria |
| 2 | šachty `1.25` a `4.05` | ležia mimo telies zón; obe sú už členmi šachtových `IfcZone` z fázy 5c |

**Model má teda dva súbežné mechanizmy prenajímateľnosti** — geometrický
(`IfcSpatialZone` na 1NP, 2NP a 4NP) a logický (`IfcZone` na 3NP). Nie je
to nedôslednosť tejto fázy, ale stav, ktorý fáza 5c zdedila a doplnila;
do BEP patrí popísaný tak, ako je.

### Nesúmernosť, ktorá je vedomá

`2.19` je inštalačná šachta 0.75 m², ktorá geometricky leží vnútri `PZ10`
(podiel 1.00), takže väzbu dostala. Jej náprotivok na 3NP (`3.18`) v zóne
3NP nie je, lebo tá vznikla z legendy, kde šachty nie sú. Vzťah znamená
„referenced in", nie „je prenajímateľná", takže priradenie je vecne
v poriadku — ale rozdiel oproti 3NP je zaznamenaný, nie prehliadnutý.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **OK** — žiadna nová geometria, `IfcZone` ani `IfcSpatialZone` sa nedotkla |
| 2 EXPRESS | **0 hlásení** — vrátane `AllowedRelatedElements` na desiatich nových vzťahoch |
| 3 GUID | **OK** — 0 zrušených, 10 nových, všetky v allowliste |
| 4–7 | OK |

**Zlyhalo 0 zo 7.** Idempotencia overená, `pytest` 8/8.
`IfcRelReferencedInSpatialStructure` je v modeli 15: 629 prvkov do
podlaží z fázy 6a a **42 priestorov do zón** z tejto fázy.

---

## 33. Fáza 14 — sedem `FS03.01` dostalo celok

`out/ASR_v20.ifc` → `out/ASR_v21.ifc`, `src/33_fs03_aggregate.py`.
Agregovaných **7 kusov do `ZD02.01.0001`**, odobraných z kontajnmentu 7.

### Prečo ich fáza 6a minula

Hľadala **stenu**, ktorú krytina pokrýva. Tieto žiadnu nepokrývajú.
Zmerané na `ASR_v20.ifc`: všetkých deväť kusov `FS03.01` dosadá na ten istý
prvok — **základovú dosku `ZD02.01.0001`** (Z −800…−300). Sedem z nich sa
nedotýka ničoho iného. Izolácia má Z −800…0, takže pokrýva celú zvislú
hranu dosky (prekryv 500 mm = plná hrúbka dosky) a pokračuje 300 mm nad ňu.

Typ sa volá `Izolace_ZD_120` — izolácia ZD, teda základovej dosky. Meno,
geometria aj dotyk hovoria to isté.

§4 test *„je časť fyzicky zviazaná s celkom a bez neho neexistuje?"* je
kladný a precedens v §4 existuje: *„S3 | `PD02` na doske, `IH01` pod doskou
| áno"*. Skript navyše pri každom kuse dosadanie **overí** a zastane, ak by
väzba mala byť vymyslená.

### Nesúmernosť, ktorá zostáva otvorená

`FS03.01.0008` a `.0009` fáza 6a agregovala do stien (`SN02.02.0019`,
`SN05.01.0005`) a stena, ktorú pokrývajú, tam naozaj je. Deväť kusov toho
istého výrobku má tým dva rôzne celky — sedem dosku, dva stenu. `.0009` je
pritom obvodový pás dlhý 33 500 mm, teda tá istá vec ako `.0004`–`.0007`.

**Zjednotiť by znamenalo prerobiť časť fázy 6a**, čo je nad rámec položky
registra, ktorá znie „7× `FS03.01` bez priradenej steny". Skript preto
rieši tých sedem a nesúmernosť hlási. **Čaká na rozhodnutie Samuela:**
nechať ako je, alebo presunúť `.0008` a `.0009` pod dosku tiež.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | **OK** |
| 2 EXPRESS | **0 hlásení** |
| 3 GUID | **OK** — 1 nový `IfcRelAggregates` v allowliste |
| 7 kontajnment | **OK** — sedem kusov odobraných z podlažia, inak by boli agregované aj kontajnované |
| 4, 5, 6 | OK |

**Zlyhalo 0 zo 7.** Idempotencia overená, `pytest` 8/8.
Prvkov kontajnovaných v podlažiach 405 → 398, `IfcRelAggregates` 96 → 97.

---

## 34. Reťazová kontrola proti pôvodnému exportu

Otázka, na ktorú §24 odpovedalo len čiastočne: **posunula sa niekde
geometria medzi `data/ASR.ifc` a dnešným stavom?**

Merané `bbox_map` z `tests/test_invariants.py` — tou istou funkciou, akú
používa invariant 1 — na `data/ASR.ifc` proti `out/ASR_v21.ifc`:

| vec | hodnota |
|---|---|
| tvarov v `ASR.ifc` | 2584 |
| tvarov v `ASR_v21.ifc` | 2590 |
| spoločných | 2542 |
| **bboxov, ktoré sa posunuli** | **0** |
| tvarov zaniklo | 42, všetko `IfcSpace` |
| tvarov vzniklo | 48, z toho 26 v allowlistoch krokov |

**Zvyšných 42 + 22 je jedna jediná udalosť.** Pôvodná pipeline (kroky
1–13, mimo tohto repa) prekreslila priestory 1NP skriptom
`build_1np_spaces.py`: 42 pôvodných `IfcSpace` zaniklo a 22
rekonštruovaných `1.01`–`1.23` vzniklo. §8 tú výnimku menuje
(*„Výnimka: priestory, kde už precedens existuje"*) a #Z ju rieši, ale
v žiadnom allowliste nebola, lebo sa stala pred týmto repom.

Doplnené ako **`tests/allowlist_prepipeline.json`** s vysvetlením priamo
v súbore. Až s ním sa dá reťazová kontrola spustiť:

```
python src/gate.py out/ASR_v21.ifc --reference data/ASR.ifc --skip 3 \
    --allow-file tests/allowlist_prepipeline.json \
    $(for f in out/ASR_v*.ifc.allowlist.json; do echo --allow-file $f; done)
```

`--allow-file` sa dá odteraz uviesť **viackrát** a allowlisty sa zlúčia;
reťazová kontrola potrebuje základňu aj allowlisty všetkých krokov.
Takto spustená hlási **zlyhalo 0 zo 6** — celá cesta od pôvodného Revit
exportu po `ASR_v21.ifc` je tým overená jedným príkazom.

`--skip 3` je nutné: GUID účtovníctvo cez prechod `ASR.ifc` →
`ASR_final_v2.ifc` pokrýva 11 000 entít pôvodnej pipeline, ktorá
allowlisty nikdy nepísala. Reťazovo má zmysel **geometria**, nie GUID —
a tá je čistá.

**36 `IfcRoof`**, ktoré fáza 1 zrušila (#V, prázdne obaly 1:1 nad
`IfcSlab`), v `bbox_map` nefigurujú vôbec a v allowliste kroku sú.

Nič z tohto nespôsobili fázy 11–14: množina stratených tvarov je
konštantná od `ASR_v3.ifc`.

---

## 35. Fázy 15 a 16 — systémy a prístrešky

Rozhodnutia Samuela z 10. 8. k bodom 1–8; tie, ktoré menia model, sú dve.

### Fáza 15 — `IfcDistributionSystem`

`out/ASR_v21.ifc` → `out/ASR_v22.ifc`, `src/34_systems.py`.

*„Takýto systém určite nie, skôr asi distribution system a pridaj tam
všetky."* Tri `IfcSystem` prekvalifikované, dva poistné prepady doplnené:

| systém | nové meno | `PredefinedType` | členov |
|---|---|---|--:|
| Zoskupenie zariadení — zdravotechnika | Zdravotechnika | `SEWAGE` | 46 |
| Zoskupenie zariadení — strešné vpuste | Odvodnenie strechy | `RAINWATER` | 18 **+ 2** |
| Zoskupenie zariadení — podlahové vpuste | Podlahové vpuste | `DRAINAGE` | 5 |

`SEWAGE` nie je dohad — všetkých **51 `IfcDistributionPort` nesie
`SystemType = SEWAGE`**. `RAINWATER` zvolené proti `STORMWATER`, ktoré je
*„runs off or travels over the ground surface"*, kým strešná vpusť
zachytáva zrážky priamo. `DRAINAGE` pre podlahové vpuste, lebo `OV01.01`
ležia **vnútri budovy** (1NP, `1.07`, `3.14`, `4.01`), nie na streche.

**Toto prebíja rozhodnutie fázy 10**, ktorá zvolila `IfcSystem` zámerne
s odôvodnením, že sieť neexistuje (51 portov, 0 `IfcFlowSegment`).
Schéma to nezakazuje: `IfcDistributionSystem` je podtyp `IfcSystem`, teda
zoskupenie, a žiadne pravidlo nevyžaduje segmenty. Tvrdenie o chýbajúcej
sieti zostáva pravdivé — presunulo sa z odôvodnenia triedy do poznámky
o rozsahu. `BEP_ANNEX.md` §2.5 prepísané.

Mená sa menili tiež: „Zoskupenie zariadení — …" bolo zvolené práve preto,
aby netvrdilo, že ide o systém.

### Fáza 16 — `OV02` na markízu

`out/ASR_v22.ifc` → `out/ASR_v23.ifc`, `src/35_ov02_shading.py`.

*„`IfcBuiltElement` podľa mňa takto schéma nepovoľuje, daj radšej shading
… alebo niečo iné na markízu."* Sedem `OV02` a dva typy prešli na
**`IfcShadingDevice / AWNING`**.

Poznámka k premise: **schéma `IfcBuiltElement` pripúšťa** — overené proti
`IFC4X3_ADD2`, `is_abstract()` je `False` pre entitu aj typ. Zmena je teda
voľbou konkrétnejšej entity pred všeobecnou, nie opravou nelegálneho
zápisu. Vecná opora pre `AWNING` je pritom silná: *„A rooflike shelter…
extending over a doorway… in order to provide protection."* Napätie je len
medzi tou vetou a definíciou nadradenej entity, ktorá hovorí o ochrane
pred slnkom.

`ObjectType` zmazaný — význam nesie enum; pri `USERDEFINED` by ho niesol
`ObjectType`, pri `AWNING` by bol duplicitný.

### Brány

| | fáza 15 | fáza 16 |
|---|---|---|
| 1 geometria | OK | OK |
| 2 EXPRESS | 0 | 0 |
| 3 GUID | 0 / 0 | 0 / 0 |
| 4–7 | OK | OK |

**Zlyhalo 0 zo 7** v oboch. Idempotencia overená. Allowlisty prázdne:
`IfcDistributionSystem` ani `IfcShadingDevice` nemenia množinu tvarov,
ktorú stráži invariant 1 — na rozdiel od fázy 11, kde prvky do nej
z `IfcFurniture` vstupovali.

### Rozhodnutia, ktoré model nemenia

| bod | rozhodnutie |
|---|---|
| `FS03.01` dva celky | *„budú oddelené, proste to nie je skladba, ale len nalepené na základovú dosku."* Zostáva sedem pod doskou, dva v stenách — zámer, nie nedôslednosť |
| #AZ dvere | **vypustiť celé**, keďže to rovnako bolo v `ASR.ifc`. Ani 20 dverí bez `ParentBoundary` sa nedopĺňa |
| #AU hrúbky | zdokumentovať; `Qto` nesie geometriu. Dve príčiny: `ST01.10` je sklon spádového klina, `FS01.*` je nemodelovaný ETICS (#AQ) |
| #BA `C1-J` | **nedávať do BEP**, stačí v podporných dokumentoch — zostáva v registri |
| #AT fyzika materiálov | **áno**, podľa IFC schémy — samostatná fáza |

---

## 36. Fáza 17 — #AT, fyzika materiálov

`out/ASR_v23.ifc` → `out/ASR_v24.ifc`, `src/36_material_physics.py`.
Deväť materiálov, **15 `IfcMaterialProperties`**, tri doplnené jednotky.

### Kam to podľa schémy patrí

`Pset_MaterialThermal`, `Pset_MaterialCommon` aj `Pset_MaterialHygroscopic`
sú **`PSET_MATERIALDRIVEN`**: *„The property sets defined by this
IfcPropertySetTemplate are to be encoded in an `IfcMaterialProperties`
entity and assigned to an `IfcMaterialDefinition`."* Nie sú to teda
`IfcPropertySet` na prvku — pôvodná otázka predpokladala opak.

**μ v `Pset_MaterialThermal` nie je.** Schéma preň má
`Pset_MaterialHygroscopic` s dvojicou `Upper`/`LowerVaporResistanceFactor`,
čo mimochodom rieši aj rozsahy.

| materiál | λ | ρ | c | μ |
|---|--:|--:|--:|--:|
| `Beton - Železobeton` | 1,430 | 2300 | 1020 | 24 |
| `Zdivo nosné` | 0,093 | — | — | 20 |
| `Izolace EPS spadove kliny` | 0,035 | **23–28** | — | **30–70** |
| `Izolace EPS` | 0,035 | — | — | — |
| `Izolace minerální` | 0,035 | — | — | — |
| `Izolace XPS` | 0,036 | — | — | — |
| `Hydrofílna vata` | 0,037 | — | — | — |
| `Hydroizolace - asfaltový pás` | — | — | — | 29000 |
| `podlahový potěr/mazanina + kari síť KH 20` | — | 2100 | — | 19 |

Každá hodnota nesie v `Specification` riadok výpisu, z ktorého pochádza.
Priradenie stojí na tom, **ktorý materiál je v ktorej skladbe** — napr.
`Izolace minerální` je v `FS01.10/.12/.20`, kde výpis uvádza reakciu na
oheň A1, kým `Izolace XPS` je v `FS01.11` s reakciou E a λ 0,036.

### Rozsahy

`μ = 30–70` → `Lower = 30`, `Upper = 70`. Výpis neuvádza, ktorý koniec
platí pri akej vlhkosti, kým schéma áno (*„measured in high/low relative
humidity"*), takže sa priraďuje číselne a `Specification` to hovorí.
Pri jedinej hodnote nesú oba konce to isté číslo.

`ρ = 23–28` → **`IfcPropertyBoundedValue`**. Šablóna psetu predpisuje
`IfcPropertySingleValue`, ale jedna hodnota by rozsah zahodila. Odchýlka
od šablóny, nie od schémy.

### Jednotky, ktoré v modeli neboli

Model deklaroval len `LENGTHUNIT` (mm), `AREAUNIT`, `VOLUMEUNIT`,
`PLANEANGLEUNIT` a jednu `THERMALTRANSMITTANCEUNIT`. Pre λ, ρ ani c
jednotka neexistovala, takže by ich čitateľ musel hádať — a pri
milimetrovom projekte je hádanie medzi kg/m³ a kg/mm³ rozdiel šiestich
rádov. Doplnené ako `IfcDerivedUnit` do `IfcUnitAssignment`:

* `THERMALCONDUCTANCEUNIT` = kg·m·s⁻³·K⁻¹
* `MASSDENSITYUNIT` = kg·m⁻³
* `SPECIFICHEATCAPACITYUNIT` = m²·s⁻²·K⁻¹

Metre z `IfcSIUnit` **bez prefixu**, nie z dĺžkovej jednotky projektu.

### Čo fyziku nedostalo

Z 47 materiálov deväť. Zvyšok výpis neuvádza a tabuľková hodnota by bola
vymyslená (§8). Menovite sa **nepriradil** parotesniaci pás s AL fóliou
(λ=0,21, c=1470, ρ=1400, μ=370 000) — vo výpise je, ale samostatný
materiál preň v modeli nie je.

### Dve veci, na ktorých skript spadol

**`IfcProperty` nemá `Description`.** V IFC4.3 sa ten atribút volá
**`Specification`**; `IfcMaterialProperties` `Description` naopak má.

**Invariant 4 ohlásil 15 osirelých.** `IfcMaterialProperties` drží väzbu
**dopredným** atribútom `Material` a materiál ju vidí len cez inverz
`HasProperties`, takže má vždy 0 inverzov — presne ten istý prípad ako
`IfcRepresentationContext` (#AY). Pred zásahom do testu overené: 15 z 15
má `Material` vyplnený a všetkých 15 je dosiahnuteľných cez
`HasProperties`. Až potom doplnené do `ORPHAN_WHITELIST`.

### Brána

inv 1 OK, inv 2 EXPRESS **0 hlásení**, inv 3 0/0, inv 4–7 OK.
**Zlyhalo 0 zo 7.** Idempotencia overená, `pytest` 8/8.

---

## 37. Fáza 18 — #AY, subkontext „Box" zmazaný

`out/ASR_v24.ifc` → `out/ASR_v25.ifc`, `src/37_sweep_box_context.py`.

Revitovský `IfcGeometricRepresentationSubContext` `'Box'` zmazaný.
Rozhodnutie Samuela: *„tak ho zmaž, keď to nič nepokazí."* Skript pred
zmazaním overil tri veci nezávisle — **0 reprezentácií na ňom, 0 detských
subkontextov, 0 inverzných odkazov** — a zastavil by sa, keby čokoľvek
z toho nesedelo. Zostali `Axis` (617 reprezentácií), `Body` (3282)
a `FootPrint` (185).

`IfcRepresentationContext` zostáva v `ORPHAN_WHITELIST`: pravidlo platí
ďalej, lebo ktorýkoľvek subkontext by pri prestaní používania hlásil
falošne to isté.

Brána: **zlyhalo 0 zo 7.**

**Register je tým vyčerpaný** — otvorená zostáva jediná položka, #BA,
a tá je rozhodnutá (zostáva zápisom, do BEP nejde).

---

## 38. Zadanie pre revíziu

Cieľ, ako ho určil Samuel: **model validný voči IFC schéme, ktorý správne
nesie všetky podstatné vzťahy, atribúty a informácie.** Register je
vyčerpaný, ale to znamená len „všetko, čo sme si zapísali, je vybavené" —
nie „nič sme neprehliadli". Táto kapitola je zadanie pre nezávislé
prejdenie, nie zhrnutie.

### Čo netreba robiť znova

| tvrdenie | ako je overené |
|---|---|
| geometria sa od pôvodného exportu neposunula | 0 posunutých bboxov na 2542 spoločných tvaroch, `bbox_map` proti `data/ASR.ifc` (§34) |
| model je schémovo platný | `validate(express_rules=True)` = 0 hlásení po každej fáze |
| GUID účtovníctvo sedí | allowlist ku každému kroku, inv 3 čistý |
| kontajnment je exkluzívny | inv 7 = 0 |
| plný SNIM kód je jedinečný | inv 6 = 0, 2611 z 2611 |
| každá fáza je idempotentná | druhý beh 0 zmien, overené pri všetkých 18 |

### Kde by som hľadal chyby ako prvé

**1 · Psety a `Qto` proti triede prvku, systematicky.** Toto je najsilnejší
kandidát na nález. Vieme, že vada existovala (#A, #B, #E) a že sme ju
opravili len tam, kde sme ju **hľadali menovite**. Že to nebolo úplné,
dokázala fáza 11: `DZ02` niesla `Qto_WallBaseQuantities` celý čas, čo bol
odtlačok jej pôvodnej triedy `IfcWall`, a nikto si toho nevšimol tri fázy
po sebe. Systematická kontrola „nesie prvok len tie psety a Qto, ktoré
jeho trieda pripúšťa" nikdy nebežala.

**2 · Rozhodnutia o triede bez excelu.** Je ich vyše dvadsať a autoritou
bola dokumentácia plus rozhodnutie Samuela, nie číselník. `BEP_ANNEX.md`
§3 ich má aj s citáciami — každé si zaslúži druhý pohľad. Menovite tie,
kde sa rozhodovalo z popisu typu, nie z výkresu.

**3 · `DZ02` — popis a vlastnosť si protirečia.** Typ sa volá „Podkladný
betón", čo je podkladová vrstva, ale originál nesie
`Pset_WallCommon.LoadBearing = True` a rozhodnutie znelo „nosná
konštrukcia". Sto milimetrov hrubá stena výťahovej jamy môže byť oboje —
ale zhodnúť by sa mali. `SOLIDWALL` proti `RETAININGWALL` je otvorená
otázka, jama zeminu naozaj zadržiava.

**4 · Hodnoty fyziky proti PDF.** Čítané cez `pdftotext`, ktorý vie
zlúčiť stĺpce. Deväť materiálov, každý má v `Specification` riadok
pôvodu — dá sa to prejsť očami za pár minút a stojí to za to.

**5 · `IfcRelSpaceBoundary`.** 649 hraníc, z toho 83 s `ParentBoundary`
a 52 dverí, ktorým fáza 6b odvodila hostiteľa **z polohy**, lebo
`FillsVoids` chýba (#AZ). Odvodenie nebolo nezávisle preverené.

> Táto kapitola je zadanie napísané po fáze 18. Fázy 19 a 20 (§39–§41) na
> tri jej body odpovedali — hraníc je dnes 697 a priestorové zaradenie má
> vlastný invariant. Zvyšok zadania platí ďalej.

**6 · Rekonštruované priestory 1NP.** Dvadsaťdva priestorov `1.01`–`1.23`
vzniklo v pôvodnej pipeline mimo tohto repa; 42 pôvodných zaniklo (§34).
Plochy sedia s legendou na 0,46 m², ale tvary nikto neporovnal s výkresom.

**7 · Polia LOP.** 48 vnorených `IfcCurtainWall`, `Ucw` a plochy zo
samostatného podkladu. Súčet 1603,63 m² bol zosúhlasený, jednotlivé polia
nie.

**8 · Čo sme nespustili vôbec.** Model neprešiel oficiálnym validátorom
buildingSMART ani žiadnym IDS. `validate(express_rules=True)` overuje
schému, nie zmysluplnosť pre konkrétny MVD.

### Ako to spustiť

```
python src/report_final.py --in out/ASR_v27.ifc          # vecné meranie
python src/gate.py out/ASR_v27.ifc --reference data/ASR.ifc --skip 3 \
    --allow-file tests/allowlist_prepipeline.json \
    $(for f in out/ASR_v*.ifc.allowlist.json; do echo --allow-file $f; done)
```

---

## 39. Fáza 19 — #BC, pásma podlaží z nosných dosiek

`out/ASR_v25.ifc` → `out/ASR_v26.ifc`, `src/38_storey_zones.py`.

Samuel hlásil tri veci: strešné vpuste na 3NP, stĺpy „úplne random" na
podlaží a dvere len na podlaží. Prvé dve sú **jedna vada** a majú jednu
príčinu.

### Príčina

Každé doterajšie pravidlo, ktoré rozhodovalo „do ktorého podlažia prvok
patrí", počítalo pásmo ako ⟨`Elevation(N)`, `Elevation(N+1)`). To je zle,
lebo `Elevation` je v tomto modeli **čistá podlaha**, kým prvky toho istého
podlažia začínajú na **vrchu nosnej dosky**, teda o hrúbku podlahovej
skladby nižšie:

| podlažie | `Elevation` | vrch nosnej dosky | rozdiel |
|---|--:|--:|--:|
| 2NP | 5000 | 4850 | 150 |
| 3NP | 9200 | 9050 | 150 |
| 4NP | 13400 | 13250 | 150 |
| 5NP | 16954 | 16750 | 204 |

Stĺp `SL02.01.0030` má rozsah `4850…8800`. V naivnom pásme 1NP má **4 %**
svojej výšky, v 2NP 96 % — a bol v 1NP. Presne tak vyzeralo všetkých 24
stĺpov a 83 stien. Rozdiel nie je konštanta, ktorú by sa dalo uhádnuť
(150 vs 204), preto sa vrchy dosiek **čítajú z modelu**: `IfcSlab`
s `PredefinedType` `FLOOR`, `BASESLAB` alebo `ROOF`.

### Prečo to v strome vyzeralo ako náhoda

Pôvodný export nebol nedôsledný v jednom smere, ale v oboch. Šestnásť
stĺpov `SL02.01` s **rovnakým** rozsahom `9050…13000` je 6× v 2NP a 10×
v 3NP. Rovnaká rada, rovnaký typ, rovnaká výška — dve podlažia. To je to,
čo Samuel videl.

Strešné vpuste sú ten istý prípad na rozhraní: telo vpuste sedí
v súvrství `13040…13836`, ktoré ide cez rozhranie 3NP/4NP, takže ťažisko
raz padlo pod a raz nad. Osem skončilo v 3NP a osem v 4NP, hoci obe
skupiny prechádzajú tou istou strechou `ST01.0001`, ktorá je v 4NP.
Fáza 6a (#G) ich z openspace dostala von — ale do 3NP.

### Čo sa spravilo

| presun | ks |
|---|--:|
| `IfcWall` 2NP → 3NP | 44 |
| `IfcWall` 1NP → 2NP | 19 |
| `IfcColumn` 1NP → 2NP | 18 |
| `IfcWall` 3NP → 4NP | 16 |
| `IfcWasteTerminal` 3NP → 4NP | 8 |
| `IfcColumn` 2NP → 3NP | 6 |
| `IfcWall` 4NP → 5NP | 4 |
| `IfcCovering` 1NP → 2NP | 1 |
| `IfcWasteTerminal` 1NP → 2NP | 1 |
| **spolu** | **117** |

Plus **226 nadbytočných `IfcRelReferencedInSpatialStructure`** — referencií
na to isté podlažie, v ktorom je prvok kontajnovaný. Spec hovorí, že
referencia je *„in addition to those levels …, but **not primarily
contained**"*, takže referencia na vlastný kontajner nehovorí nič.

### Čo pravidlo zámerne neurobilo

Prah presunu je 20 percentuálnych bodov a nie je zvolený od oka:

* prvky, ktoré presunúť treba, vyhrávajú aspoň o **23 bodov** —
  najtesnejšia je vpusť `OV04.01.197`, 38 % v 3NP proti 62 % v 4NP;
* prvky, ktoré cez rozhranie idú **zámerne**, vyhrávajú najviac o 6 —
  stena schodiska `SN02.03.0013` (49/51) a schodisko `ZV04.01.0001`
  (47/53). Obe zostali, kde boli, a majú referenciu na druhé podlažie.
  To je presne prípad z dokumentácie: *„A curtain wall might span through
  several stories, in this case it can be contained within the ground
  floor, but it would be referenced by all additional stories it spans."*

Skript sa zároveň kontroluje na tom, čo **nesmie** pokaziť. Skladba
podlahy `PD02.44.01` má rozsah `4850…5000`, teda leží celá pod
`Elevation` 2NP, a do 2NP patrí správne — naivné pásmo by ju presunulo do
1NP. Po behu je takých 0.

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | 0 zmenených bboxov |
| 2 EXPRESS | 0 hlásení |
| 4–7 | OK |
| 8 priestorové zaradenie | 13 porušení — skladby podlahy v priestoroch, rieši fáza 20 |

Idempotencia overená: druhý beh hlási 0 presunov a 0 nadbytočných
referencií.

---

## 40. Fáza 20 — #BD, dvere a stĺpy do miestností

`out/ASR_v26.ifc` → `out/ASR_v27.ifc`, `src/39_room_binding.py`.

### Čo na to hovorí schéma

Samuelova otázka znela „čo IFC schéma, kde to má byť priradené". Schéma
má na priestorové zaradenie **tri vzťahy** a každý odpovedá na inú otázku:

| vzťah | otázka | kardinalita |
|---|---|---|
| `IfcRelContainedInSpatialStructure` | v čom prvok **primárne** je | práve jeden kontajner |
| `IfcRelReferencedInSpatialStructure` | kam patrí **okrem toho** | ľubovoľne veľa |
| `IfcRelSpaceBoundary` | čo miestnosť **uzatvára** | z pohľadu miestnosti |

Doslovne: *„The containment relationship of an element within a spatial
structure has to be a hierarchical relationship; an element can only be
contained within a single spatial structure element."* a *„Any element
can be referenced to zero, one or several levels of the spatial
structure … the `IfcRelReferencedInSpatialStructure` is not restricted to
be hierarchical."*

Kontajnerom smie byť ktorýkoľvek `IfcSpatialElement`, teda aj `IfcSpace`;
§4.1.5.13 hovorí len *„with `IfcBuildingStorey` being the **default**
container"* — predvolený, nie predpísaný. Zároveň *„The question, which
level is relevant for which type of element, can only be answered within
the context of a particular project."*

**Rozhodnutie 24 sa tým mení.** Znelo „dvere a steny do miestností nie,
lebo kontajnment je exkluzívny". Exkluzivita platí, ale záver z nej
nevyplýva: schéma sa pýta na **primárnu** miestnosť, nie na žiadnu. Nová
formulácia je v BEP §2.7.

### Dvere

Krídlo nie je vnútri žiadneho priestoru — sedí v otvore steny. Sonda
preto strieľa body **po normále dverí** na obe strany (0,3 / 0,6 / 0,9 m,
vo výške 1 m nad prahom). Normála je +Y ich `ObjectPlacement`, ako určuje
spec: *„the door opening direction (by the positive y-axis of the
`ObjectPlacement`)"*.

Z nájdených miestností sa vyberá **obsluhovaná**: komunikačné priestory
(chodba, schodisko, CHÚC, lobby, openspace — rozoznané z `LongName`, teda
z názvoslovia projektanta) ustúpia, pri zhode rozhodne menšia plocha.
Zvyšné miestnosti dostanú referenciu. To je Samuelovo zadanie doslova:
*„nemusia byť priradené ku chodbe, ale do tej priamej miestnosti áno."*

| | ks |
|---|--:|
| kontajnment do obsluhovanej miestnosti | 84 |
| agregované v LOP — len referencia (invariant 7) | 8 |
| bez priestoru na oboch stranách — ostávajú na podlaží | 5 |

Kontrola na vzorke: `DD01.05.08` → `1.14` WC bezbariérové ženy, referencia
`1.18` chodba hygienického zázemia. `DD03.04.02` → `3.11` kuchynka,
referencia `3.02` openspace. `DD02.04.03` → `2.03` zasadačka, referencia
`2.02` openspace. Kabínkové dvere WC, ktoré majú miestnosť po oboch
stranách, skončili v tej miestnosti.

### Stĺpy

Obal `IfcSpace` je okolo stĺpa **vykrojený**, takže stred stĺpa nie je
v žiadnom priestore a test „bod vnútri" nefunguje — vracia prázdno pre
všetkých 52. Sonda preto stĺp **obchádza po obvode**, 150 mm od plášťa,
v troch výškach.

| | ks |
|---|--:|
| obklopený jednou miestnosťou → kontajnment do nej | 35 |
| na rozhraní dvoch miestností → ostáva na podlaží, referencie na obe | 17 |

Sedemnásť stĺpov stojí v priečke medzi dvomi miestnosťami — `SL02.01.0003`
má z jednej strany `1.01`, z druhej `1.02`. Ktorá z nich by mala byť tá
primárna, sa povedať nedá, a kontajnment je exkluzívny; vynútiť ho by
znamenalo polovicu si vymyslieť. Podlažie je pre ne správna odpoveď —
a väzbu na obe miestnosti nesie referencia a `IfcRelSpaceBoundary`, ktorý
majú všetky od fázy 6b.

### Skladby podlahy a podhľady

Invariant 8 pri prvom behu ukázal ďalších 13 prvkov — a tie odhalili
staršiu vadu. Fáza 6a hľadala priľahlú miestnosť s toleranciou 300 mm na
obe strany, lenže **nosná doska má 250 mm**, takže tolerancia ju
preskočila: skladba podlahy 3NP `9050…9200` sa dala miestnosti **pod ňou**
ako podhľad. Smer teraz určuje `PredefinedType`, teda schéma:

* `FLOORING` patrí miestnosti **nad** sebou,
* `CEILING` miestnosti **pod** sebou.

Presunutých 18 `FLOORING` a 4 `CEILING`. Napr. `PD02.31.01` bola
v openspace `2.01`, patrí do `2.06` WC muži; `PH01.20.0010` bola v `3.02`,
patrí do `3.07`. Štyri prvky nad sebou ani pod sebou miestnosť nemajú
(sú pod prístreškom) a zostali na podlaží — vypísané menovite.

### Podlahové vpuste a hranice

Dve podlahové vpuste (`OV01.01.228`, `OV01.01.233`) fáza 6a nenašla,
lebo ich telo sedí v skladbe podlahy, teda **pod** obalom priestoru.
Sonda nahor ich dala do `2.14` a `1.05` — obe technické miestnosti, presne
kde podlahová vpusť býva.

Doplnených **48 `IfcRelSpaceBoundary1stLevel`** pre dvere, ktoré lúč
fázy 6b minul (47 `INTERNAL`, 1 `EXTERNAL`). Bez jedinej hranice zostali
4 dvere, ktoré nemajú priestor ani z jednej strany: `DD01.06.08`,
`DD04.07.02` a dvoje výťahových dverí na 1NP, kde šachta ako priestor
modelovaná nie je.

### Výsledok

| | pred (`v25`) | po (`v27`) |
|---|--:|--:|
| prvkov kontajnovaných v miestnosti | 136 | **260** |
| prvkov na podlaží | 398 | 274 |
| referencií na priestor | 0 | **99** |
| `IfcRelSpaceBoundary` | 649 | 697 |

### Brána

| inv | výsledok |
|---|---|
| 1 geometria | 0 zmenených bboxov proti `data/ASR.ifc` |
| 2 EXPRESS | 0 hlásení |
| 4–7 | OK |
| 8 priestorové zaradenie | **0 porušení** |

**Zlyhalo 0 z 8.** Idempotencia overená: druhý beh hlási 0 presunov,
0 nových hraníc.

---

## 41. Invariant 8 — aby sa to už nestalo

Táto trojica vád nebola nájdená invariantom, ale okom nad stromom
v prehliadači. To je to, čo treba zmeniť. Invariant 8
(`tests/test_invariants.py::inv8_spatial_fit`) kontroluje dve veci:

**a · prvok leží v pásme podlažia, v ktorom je zaradený.** Aspoň polovicou
svojej výšky. Prvok zámerne rozkročený cez rozhranie výnimku dostane —
ale len ak v pásme má aspoň 20 % **a zároveň** má na druhé podlažie
`IfcRelReferencedInSpatialStructure`. Bez tej druhej podmienky by
kontrolu obišlo práve tých 24 stĺpov: mali 4 % v podlaží, v ktorom viseli,
a referenciu na to, v ktorom naozaj stoja — referencia by zakryla zlé
zaradenie namiesto toho, aby priznala rozkročenie.

**b · geometricky zhodné prvky sú v jednom podlaží.** Rovnaká trieda,
rovnaký typ, rovnaký Z-rozsah (na 50 mm) — a predsa dve podlažia. Táto
kontrola by pôvodnú vadu chytila aj bez pásiem a bez znalosti dosiek,
lebo netvrdí, ktoré podlažie je správne, len že obe naraz správne byť
nemôžu.

Merané na oboch koncoch:

| súbor | porušení inv 8 |
|---|--:|
| `ASR_final_v2.ifc` (základňa) | 161 |
| `ASR_v25.ifc` (pred fázou 19) | 161 |
| `ASR_v26.ifc` (po fáze 19) | 13 |
| `ASR_v27.ifc` (po fáze 20) | **0** |

Test `test_inv8_catches_the_defect_it_was_written_for` beží proti
základni a **vyžaduje**, aby kontrola vadu našla. Kontrola, ktorá prejde
len na opravenom modeli, nedokazuje nič — to je poučenie z pôvodného
handoveru, ktorý meral zámer namiesto výsledku.

### Čo z toho platí všeobecne

1. **Pásmo podlažia nie je `Elevation`.** Vždy sa odvodzuje z geometrie
   konštrukcie. Konštanta „150 mm" by v tomto modeli minula 5NP.
2. **Tolerancia nesmie byť väčšia než to, čo má oddeľovať.** 300 mm
   tolerancia preskočila 250 mm dosku a dala podlahu 3NP miestnosti na
   2NP. Ak tolerancia rozhoduje o smere, smer musí povedať dáta —
   `PredefinedType`, nie vzdialenosť.
3. **Bbox nie je teleso.** Bbox kuchynky prekrýva bbox openspace, bbox
   openspace obsahuje pôdorys každého WC. Každé pravidlo postavené na
   pôdorysnom prekryve bboxu v tomto modeli niečo pomýlilo — fáza 6a
   podlahy, fáza 6b hranice. Otázka „je bod v miestnosti" sa odpovedá
   lúčom cez trojuholníky obalu (`src/spatial.py`).
4. **Rovnaké prvky musia skončiť rovnako.** Najlacnejšia kontrola
   priestorových vzťahov je porovnať súrodencov medzi sebou; nepotrebuje
   vedieť, čo je správne.
5. **Exkluzívny vzťah nie je dôvod nepriradiť nič.** Keď sa prvok týka
   dvoch miestností, schéma má na to referenciu — nie mlčanie.

---

## 42. Smú byť dvere v miestnosti? — rozbor schémy

Samuelova otázka po fáze 20: *„či tie dvere ale takto vôbec môžu byť,
alebo majú byť tým `RelBoundary` a majú sa len inak zobrazovať a nie cez
spatial structure, a je to chyba prehliadača."* Overené proti
`IFC4X3_ADD2`, nie z pamäte.

### 1 · Platnosť — áno, bez výhrad

```
ENTITY IfcRelContainedInSpatialStructure
  RelatedElements   : SET [1:?] OF IfcProduct;
  RelatingStructure : IfcSpatialElement;
 WHERE
  WR31 : SIZEOF(QUERY(temp <* RelatedElements |
         'IFC4X3_ADD2.IFCSPATIALSTRUCTUREELEMENT' IN TYPEOF(temp))) = 0;
```

`IfcSpace` **je** `IfcSpatialElement`. Jediné pravidlo obmedzuje
`RelatedElements` (priestor nesmie byť *obsahom* kontajnmentu — od toho je
`IfcRelAggregates`), nie kontajner. `validate(express_rules=True)` = 0
hlásení, invariant 2 to potvrdzuje po každej fáze.

### 2 · Predvoľba je ale iná — a spec ju hovorí po triedach

Prehľadaných všetkých 2469 stránok `lexical` na vetu *„… is the default
(spatial) container"*. Má ju presne **85 tried**:

| trieda | predvolený kontajner |
|---|---|
| `IfcCovering` | **`IfcSpace`** |
| 83 podtypov `IfcDistributionElement` (`IfcWasteTerminal`, `IfcSanitaryTerminal`, `IfcAirTerminal`, …) | **`IfcSpace`** |
| `IfcTransportElement` | `IfcBuilding` |
| `IfcDoor`, `IfcColumn`, `IfcWall`, `IfcSlab`, `IfcStair`, `IfcRailing`, `IfcFurniture` | **nemajú vlastný záznam** |

Kde vlastný záznam nie je, platí generické §4.1.5.13: *„Subtypes of
`IfcSpatialStructureElement` are valid spatial containers, with
**`IfcBuildingStorey` being the default container**."*

Z toho plynie rozdelenie, ktoré fáza 20 dodržuje:

* **krytiny a distribučné prvky v miestnostiach nie sú odchýlka** — sú
  doslova predvoľba spec-u. Fázy 6a a 20 tu robia presne to, čo docs
  žiadajú;
* **dvere a stĺpy v miestnostiach odchýlka sú.** Predvoľba je podlažie.

### 3 · Čo `IfcDoor` hovorí o sebe

*„A door can: be a 'free standing' door, contained in an
`IfcSpatialElement` **such as an `IfcBuildingStorey`**. / fill an opening,
typically in a wall … `FillsVoids` … / be part of an element assembly,
typically an `IfcCurtainWall` … `Decomposes`."*

Priestor v tom výpočte nefiguruje. Naše dvere sú prevažne druhý prípad —
17 má `FillsVoids`, 80 nie (#AZ), 10 je agregovaných v LOP.

### 4 · Prečo to napriek tomu smie byť

§5.4.3.52 nechá úroveň otvorenú výslovne: *„The question, which level is
relevant for which type of element, can only be answered within the
context of a particular project and might vary within the various
regions."* a *„Occurrences of the same element type can be assigned to
different spatial structure elements depending on the context of the
occurrence."* K tomu `IfcSpace`: *„It also serves as the spatial container
for space related elements."*

Predvoľba teda nie je predpis. Odchýlka od nej je legitímna, ale musí byť
**priznaná** — je v `BEP_ANNEX.md` §2.7.

### 5 · Umiestnenie — vyzerá to ako protiargument, nie je

`IfcLocalPlacement`: *„For `IfcElement` the convention applies that it
shall be placed relative to the local placement of its container, either
`IfcSite`, `IfcFacility`, or `IfcFacilityPart` — **it should be the same
container element** that is referenced by the
`IfcRelContainedInSpatialStructure` containment relationship."*

`IfcSpace` v tom zozname nie je: je **súrodenec** `IfcFacilityPart` pod
`IfcSpatialStructureElement`, nie jeho podtyp. Prvok kontajnovaný
v priestore teda tú vetu splniť **nemôže** — ani vtedy, keď je priestor
predvoľbou. Overené na dátach: `ASR_v25.ifc` mal 136 prvkov v miestnosti
a **94 z nich bolo umiestnených voči podlažiu**, z toho 74 krytín, teda
práve tá trieda, kde je `IfcSpace` predvolený kontajner. Nesúlad je
teda vlastnosťou reťazca site→building→storey, nie následkom fázy 20.

Pre výplne otvorov má navyše to isté miesto vlastnú vetu: *„for elements
that fill an opening (such as doors or windows), as expressed by
`IfcRelFillsElement`"* — a 17 dverí je umiestnených presne takto.

### 6 · Chyba prehliadača? Nie

Priestorový strom je z definície `IfcRelAggregates` (projekt → areál →
budova → podlažie → priestor) plus `IfcRelContainedInSpatialStructure`.
Prehliadač, ktorý ukáže dvere pod podlažím, keď sú na podlaží
kontajnované, sa správa **správne**. Ukázať ich pod miestnosťou bez
kontajnmentu by znamenalo čítať aj `IfcRelSpaceBoundary`
a `IfcRelReferencedInSpatialStructure` — to je funkcia navyše, nie oprava.

### 7 · Rozhodnutie

Skript má prepínač `BOUNDING_ELEMENT_CONTAINER` (CLI `--container
room|storey`). Oba režimy prechádzajú bránou; líšia sa iba tým, kam ich
zaradí strom, informácia sa v žiadnom nestráca:

| | `room` | `storey` |
|---|--:|--:|
| dvere kontajnované v miestnosti / na podlaží | 84 / 3 | 0 / 87 |
| stĺpy v miestnosti / na podlaží | 35 / 17 | 0 / 52 |
| `IfcRelReferencedInSpatialStructure` na priestor | 99 | 218 |
| `IfcRelSpaceBoundary` | 697 | 697 |
| krytiny a vpuste v miestnostiach | áno | áno |

**Rozhodnutie Samuela (12. 8.): `room`.** Model zostáva ako po fáze 20.
Odchýlka je priznaná v BEP §2.7 aj s citáciou predvoľby, aby ten, kto
model preberá, vedel, že podlažie je alternatíva na jeden prepínač.

---

## 43. Fáza 21 — skladby dvojúrovňovo: predpis a výskyt

`out/ASR_v27.ifc` → `out/ASR_v28.ifc`, `src/40_skladby_vyskyty.py`.

Podnet Samuela: *„skladby striech sú jedna grupa aj na streche veľkej aj
na streche malej a ideálne by bolo keby je to rozdelené ako S1.01
a S1.02… zas je to niečo na štýl že type a occurrence."*

Skupina `S1` naozaj obsahovala 45 prvkov, z ktorých 38 patrí veľkej
streche na 4NP a 7 malej na 5NP. Skupina teda nezodpovedala žiadnej
skutočnej konštrukcii — bolo to zjednotenie dvoch nezávislých súvrství
s rovnakým predpisom.

### Čo hovorí schéma

**Type a occurrence to nie je.** `IfcRelDefinesByType` by formálne prešlo:
`RelatedObjects : SET [1:?] OF IfcObject`, `IfcGroup` **je** `IfcObject`,
`IfcTypeObject` nie je `ABSTRACT` a jediné jeho WHERE sú `NameRequired`
a `UniquePropertySetNames`. Lenže sémantika typu je o zdieľaných psetoch
a zdieľanom tvare medzi **produktmi**, a jediné podtypy `IfcTypeObject`
sú `IfcTypeProduct`, `IfcTypeProcess` a `IfcTypeResource` — **typ skupiny
v schéme neexistuje**. Bolo by to legálne, ale bez MVD opory a žiadny
prehliadač to nezobrazí.

**`IfcMaterialLayerSet` tiež nie**, hoci na prvý pohľad sedí: schéma
hovorí *„The IfcMaterialLayerSet, referenced by ForLayerSet, can however
be shared among several occurrence objects"* a `IfcMaterialLayerSetUsage`
je vždy na jednom výskyte. To je správny type/occurrence pár pre skladbu
**jedného prvku**. Tu je skladba rozprestretá cez viac prvkov (`ST01.20`
krytina + `ST01.10` izolácia + `SD02` doska + `PH01` podhľad), z ktorých
každý nesie vlastný layer set. Preto `IfcGroup` — rozhodnutie §2 platí.

**Vzťah `S1` ↔ `S1.01` je celok a časť**, a na to má schéma dve cesty:

| mechanizmus | kardinalita | opora v dokumentácii |
|---|---|---|
| `IfcRelAssignsToGroup` rekurzívne | many-to-many | *„It allows for grouping arbitrary objects within a group, including other groups. The grouping relationship can be applied in a recursive manner."* |
| `IfcRelAggregates` | `Decomposes : SET [0:1]` → strom | `IfcBuiltSystem`: *„From IfcObjectDefinition it inherits IsDecomposedBy pointing to IfcRelAggregates. **It provides the hierarchy between the separate (partial) building systems.**"* |

**Zvolená agregácia** (Samuel, 12. 8.). `Decomposes : SET [0:1]` schémou
vynúti, že `S1.01` patrí práve jednej skladbe — omyl „to isté dieťa pod
`S1` aj `S2`" sa nedá zapísať. `IfcRelAggregates` má v EXPRESS jediné
pravidlo `NoSelfReference` a v dokumentácii **žiadne informal
propositions**, takže agregácia skupín je bez výhrad legálna.

Overené na minimálnom modeli (`IfcGroup` agregujúca dve `IfcGroup`,
členstvo na deťoch): `validate(express_rules=True)` dá **0 hlásení**,
`Decomposes` aj `IsDecomposedBy` sa naplnia. `IfcGroup` navyše **nemá
atribút `ContainedInStructure`** (`hasattr` = False), takže invariant 7
sa na skupinách nemá o čo zaseknúť.

**Členstvo je len na deťoch** (Samuel, 12. 8.). Rodič svoj pôvodný
`IfcRelAssignsToGroup` stráca. Prázdny vzťah by porušil invariant 5, tak
sa maže celý; `IfcGroup.IsGroupedBy : SET [0:?]` prázdnu množinu dovoľuje.
Cena je, že prehliadač, ktorý agregáciu nerozbaľuje, ukáže `S1` prázdnu.
Získa sa tým, že sčítanie prvkov naprieč výpisom dá správne číslo — pri
ponechaní členov aj na rodičovi by sa každý prvok zarátal dvakrát.

### Pravidlo nosiča

**Výskyt = (skladba, podlažie nosiča).** Nosič kotviaceho prvku je koreň
jeho agregácie, ak je agregovaný, inak prvok sám.

Nosič robí dve veci: dá výskytu podlažie a pomenuje ho. Podlažie sa berie
z nosiča, nie z prvku — podhľady `PH01` sú kontajnované v miestnostiach
3NP, hoci patria k streche nad 4NP, takže podľa vlastného podlažia by sa
súvrstvie roztrhalo.

Prečo nie jemnejšie: nosičom `S4` sú štyri steny, ale tvoria dva výlezy —
po stenách by to bolo rozdrobenie. Prečo nie hrubšie: podlažie samotné by
pri `S1` fungovalo len náhodou, lebo obe strechy zhodou okolností ležia
na rôznych podlažiach.

Číslovanie `.01`, `.02` … podľa `Elevation` podlažia — ten istý smer, akým
`18_snim_inst.py` prideľuje `INST`. Pri `S1` tak `.01` vyjde veľká strecha
(4NP, 13400) a `.02` malá (5NP, 16954).

### Výsledok

| skladba | výskyt | nosič | prvkov | rodič |
|---|---|---|--:|--:|
| `S1` vegetácia | `S1.01` | `IfcRoof ST01.0001` Strešné súvrstvie 4NP | 38 | |
| | `S1.02` | `IfcRoof ST01.0002` Strešné súvrstvie 5NP | 7 | **45** |
| `S2` kačírek | `S2.01` | `IfcRoof ST01.0001` | 48 | |
| | `S2.02` | `IfcRoof ST01.0002` | 5 | **53** |
| `S3` doska a podlaha | `S3.01` … `S3.04` | 1NP / 2NP / 3NP / 4NP | 32 / 9 / 9 / 4 | **54** |
| `S4` ETICS plocha výlezu | `S4.01` | steny `SN02.02.0035`, `.0041` 4NP | 4 | |
| | `S4.02` | steny `SN02.01.0004`, `.0007` 5NP | 4 | **8** |
| `S5` ETICS sokol výlezu | `S5.01` | štyri steny `SN02.02` 4NP | 8 | **8** |
| `S6` kancelárie | `S6.01` | `PD03.30.01` 2NP | 8 | |
| | `S6.02` | `PD03.30.02` 3NP | 9 | **17** |
| `S8` ETICS odpad. hosp. | `S8.01` | stena `SN05.01.0005` 1NP | 2 | **2** |
| `S9` ETICS odpad. hosp. | `S9.01` | tri steny `SN05.01` 1NP | 6 | **6** |

Osem predpisov, **15 výskytov, 193 členstiev**. Súčty sedia na kus
a zjednotenia sú disjunktné — žiadny člen sa nestratil ani nezdvojil.
Zmena je rafinácia existujúcich skupín, nie ich preskupenie, a presne to
si krok pred zápisom overuje: pri nezhode o jediný prvok zastane.

Kotviace prvky sú agregované správne — všetkých 18 `ST01.20` (16 + 2)
aj 25 `ST01.21` (24 + 1). Jediný chybne agregovaný prvok `ST01.10.0012`
(izolácia malej strechy visiaca v agregáte veľkej, §39) kotviaci nie je
a priraďuje sa geometricky, takže rozklad neovplyvnil.

### Hĺbka pásma je pripnutá, nie zvolená

Fáza 8b vybrala `HLBKA = 2000` z citlivostnej skúšky ako hodnotu vnútri
stabilného pásma. Tu je silnejší dôkaz: kontrola úplnosti ju **pripne**.

| hĺbka | výsledok |
|--:|---|
| 1200 | `S1`, `S2` stratia po 2 prvkoch, `S6` tiež → **STOP** |
| 1500 | každá po 1 prvku → **STOP** |
| **2000** | **úplný a disjunktný rozklad všetkých ôsmich** |
| 3000 | rovnaké čísla ako 2000 |

Pod 2000 mm sa rozklad rozíde s rodičom a krok odmietne zapísať; nad ním
sa už nič nemení. Skúšku vie ktokoľvek zopakovať cez `--hlbka`.

### Čo rozklad odhalil a neopravuje — `#BE`

`S3` sa volá *„Skladba základovej dosky a podlahy v 1NP"*, ale rozkladá sa
na štyri podlažia: 1NP 32, 2NP 9, 3NP 9, 4NP 4. Základová doska je pritom
len na 1NP — podlahy vyšších podlaží ležia na stropných doskách `SD02`.
Členstvo prišlo z fázy 8 pravidlom „všetky prvky kódu" (`PD02.*`,
`IH01.01`, `DZ01.01`, `ZD02.01`), čo odpovedá na inú otázku než „patrí do
tejto skladby".

Rozklad sa napriek tomu urobil celý. Nie preto, že by 2NP–4NP bolo
správne, ale preto, že ich **zviditeľní**: doteraz to bolo skryté v jednom
čísle 54, teraz je to v strome ako `S3.02`, `S3.03` a `S3.04`. Zúžiť `S3`
na 1NP by znamenalo odobrať 22 prvkov zo skupiny — to je zmena rozsahu
skladby, na ktorú treba `D.1.1.09` a rozhodnutie, nie geometriu.

> **Doriešené vo fáze 22 (§45).** Podklady skontrolované, `S3` zúžená na
> základovú dosku: 32 prvkov a jediný výskyt `S3.01`. Tabuľka a čísla
> vyššie sú stav po fáze 21; po fáze 22 je to 12 výskytov a 171 členstiev.

### Brána `ASR_v28.ifc`

`python src/gate.py out/ASR_v28.ifc --reference out/ASR_v27.ifc
--allow-file out/ASR_v28.ifc.allowlist.json`

| # | výsledok |
|---|---|
| 1 geometria | **OK** — krok sa nedotkol ani jedného `IfcProduct` |
| 2 EXPRESS | **OK**, 0 hlásení vrátane agregácie skupín |
| 3 GUID | **OK** — 38 nových (15 `IfcGroup`, 15 `IfcRelAssignsToGroup`, 8 `IfcRelAggregates`), 8 zmazaných `IfcRelAssignsToGroup`, všetky v allowliste |
| 4 osirelé | **OK**, 0 |
| 5 prázdne SET | **OK** |
| 6 jednoznačnosť | **OK** — `S1.01` sa SNIM kontroly netýka, tá iteruje `IfcProduct` |
| 7 kontajnment vs agregácia | **OK** — `IfcGroup` `ContainedInStructure` nemá |
| 8 priestorové zaradenie | **OK** |
| 9 rozklad skladieb | **OK**, nový |

**Zlyhalo 0 z 9.** Idempotencia overená: druhý beh ohlási osem rozložených
skladieb a skončí bez zápisu.

`pytest` sa proti medzivýstupu na účtovníctvo GUID púšťať nedá a nikdy
nedalo: `test_inv3_guid_accounting` allowlist neprijíma, takže na
`ASR_v28.ifc` ohlási 46 zmien — presne tak, ako ohlási 46 aj na `v27`
proti `v26` a na `v26` proti `v25`. Je to zámer, ktorý test popisuje vo
vlastnom docstringu: *„účtovníctvo tohto repa… robí brána každého kroku
cez `--allow-file`"*. CI preto púšťa `pytest` bez `IFC_REFERENCE`, teda
proti základni, a účtovníctvo necháva bráne.

`IfcGroup` (vrátane podtypov) 24 → 39, `IfcRelAggregates` +8. Počet
occurrences, `IfcRelContainedInSpatialStructure` a všetky bboxy nezmenené.

---

## 44. Invariant 9 — rozklad musí byť partícia

`inv9_skladby_rozklad` v `tests/test_invariants.py`. Kontroluje štvoro:

1. rodič s výskytmi **nemá vlastných priamych členov** — inak sa prvky pri
   sčítaní rátajú dvakrát;
2. **výskyty tej istej skladby sa neprekrývajú** — toto je tá kontrola,
   ktorá by pôvodnú vadu chytila;
3. každý výskyt má aspoň jedného člena;
4. výskyt visí práve na jednom rodičovi.

**Prekryv medzi skladbami sa nekontroluje a nesmie.** 26 izolačných dosiek
patrí do `S1` aj `S2` naraz, lebo kačírkový pás je 600 mm okraj tej istej
strešnej plochy, pod ktorou je vegetácia (§28). Kontrola je vždy vnútri
jednej skladby.

**Rozsah je úzky zámerne.** Naivná definícia „skupina, ktorá má medzi
členmi skupinu, je partícia" by okamžite zlyhala na `IfcZone`
„Pronajmutelné" z fázy 5c: má 10 priestorov **plus** vnorenú zónu
„Nájomné priestory 3NP" s ďalšími 11. Rekurzívne zoskupenie je v IFC bežné
a partíciou byť nemusí. Rozsah preto drží `SKLADBA_PARENT` — presne
`IfcGroup` s menom `S<číslo>` — a `test_inv9_ignores_nested_zones` to
zafixuje, aby to niekto neskôr nerozšíril a nerozbil zóny.

Úplnosť voči pôvodným počtom v invariante **nie je**: to je akceptačné
kritérium kroku 40, a po ňom už niet s čím porovnávať. Že kontrola vadu
naozaj chytí, overuje `test_inv9_catches_the_defect_it_was_written_for` na
modeli postavenom v pamäti — rodič, ktorý si nechal členov, a dva výskyty
zdieľajúce prvok.

Invariant geometriu nepočíta, takže patrí do CI joba `rychle`.

---

## 45. Fáza 22 — `S3` zúžená na základovú dosku, `#BE` uzavreté

`out/ASR_v28.ifc` → `out/ASR_v29.ifc`, `src/41_s3_rozsah.py`.

Podnet Samuela k nálezu `#BE`: *„PD02 môže byť aj kde neviem v konkrétnej
skladbe, skontroluj podklady."* Skontrolované. Nemôže.

### Tri nezávislé doklady

**1. `PD02` je vo výpise `D.1.1.09` presne raz.** V S3. Ani S6 ho
neuvádza — tá má `PD03.30` dutinovú podlahu na `SD02` s podhľadom
`PH01`. Podlaha na stropnej doske s `PD02` **vo výpise nie je vôbec**.

**2. S3 stojí na základovej doske.** Vrstva 7 je `ZD02.01`
„Železobetónová základová doska", 500 mm; pod ňou vrstvy 8–10 `IH01`
hydroizolácia a vrstva 11 `DZ01` podkladný betón. V modeli je `ZD02.01`
**jedna jediná** doska. Podlahy 2NP–4NP ležia na `SD02` stropných
doskách, čo je iný substrát.

**3. Sedí to na hrúbke izolácie.** Výpis predpisuje vrstvu 6 „Podlahové
dosky z EPS 150", hrúbka **200 mm**:

| | izolácia v modeli | ks |
|---|---|--:|
| `PD02` na 1NP | EPS 200; výnimky `PD02.11` XPS 150 a `PD02.54` EPS 100 | 24 |
| `PD02` na 2NP–4NP (`.31`, `.43`, `.44`, `.52`, `.53`) | **EPS 50** | 22 |

Tých 22 teda nie je S3 ani podľa substrátu, ani podľa skladby vrstiev.
Kritérium rozdelenia je zhodou okolností to isté ako podlažie, ale
odvodené je z výpisu, nie z názvu podlažia.

### Rozhodnutie

**Samuel (12. 8.): prvky zo skupiny vypadnú a novú skupinu nedostanú.**
Výpis pre ne skladbu nemá, takže akákoľvek skupina by tvrdila viac, než
podklad hovorí. Zostáva to ako **chýbajúci podklad**, nie ako vada modelu.

Krok zruší `S3.02`, `S3.03` a `S3.04` aj s ich `IfcRelAssignsToGroup`
a previaže `IfcRelAggregates` skupiny `S3` na jediné zostávajúce dieťa.
`S3` má odteraz **32 prvkov a jeden výskyt `S3.01`** — 24 `PD02` na 1NP,
4 `IH01.01`, 3 `DZ01.01` a `ZD02.01`.

Ktorý výskyt zostane, sa **nevyberá podľa mena podlažia**, ale podľa toho,
čo skladbu definuje: zostáva ten, ktorý obsahuje `ZD02.01`. Kritérium je
prevzaté priamo z výpisu, takže sa s ním nemôže rozísť preklepom v názve
podlažia. Ak by dosku obsahoval viac než jeden výskyt, krok zastane.

### Čo zostáva otvorené a komu patrí

Výpis preskakuje práve jedno číslo — za `S6` ide rovno `S8`. Že chýbajúca
`S7` je práve táto podlaha na stropnej doske, je pravdepodobné, ale je to
**domnienka, nie doklad**; potvrdiť ju vie len projektant. Do registra sa
preto nezapisuje ako skladba, ale ako chýbajúci podklad k `#BE`.

Sem patrí aj už vedená vada legendy: legenda 1NP uvádza `PD02.31`, ktorý
je v modeli na 2NP a 3NP. Model to má správne, výkres nie — položka §3
„legenda 1NP: `PD02.31` vs `.30`" je tým doložená druhýkrát.

### Brána `ASR_v29.ifc`

`python src/gate.py out/ASR_v29.ifc --reference out/ASR_v28.ifc
--allow-file out/ASR_v29.ifc.allowlist.json`

Zrušených 6 `GlobalId` (3 `IfcGroup` + 3 `IfcRelAssignsToGroup`), 0
nových. Geometria nedotknutá, 0 osirelých, invariant 9 naďalej zelený —
`S3` má jeden výskyt, žiadnych priamych členov a prekryv nie je s čím
robiť. Idempotencia overená: druhý beh ohlási, že `S3` už má len výskyt
so základovou doskou.

Skladby po fáze 22: **8 predpisov, 12 výskytov, 171 členstiev.**
