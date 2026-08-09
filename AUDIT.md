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
| — | šachty na 1NP | v rozsahu, tou istou metódou ako `build_1np_spaces.py` |

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
| F | O | 48 osirelých entít (31 `IfcLocalPlacement`, 16 profilov, 1 `IfcSurfaceStyle`) — potvrdené do kusa |
| AY | O | `#16` `IfcGeometricRepresentationSubContext` „Box" nepoužitý (0 reprezentácií). Má 0 inverzov, lebo väzbu na rodiča drží **dopredný** `ParentContext`, nie inverzný `HasSubContexts` — do whitelistu invariantu 4 patrí alebo sa má zmazať |
| AJ | O | 2653 hodnôt s FP šumom (2502 `Qto`, 145 `Overall*`, 18 property) |

### Triedny model
| # | | vec |
|---|---|---|
| T | **H** | ~~`ST01.*` vrstvy skladby vedené ako `IfcRoof`~~ — 92 vrstiev + 10 typov na `IfcCovering`, `50c26c5` |
| V | **H** | ~~36 prázdnych `IfcRoof` obalov 1:1 nad `IfcSlab`~~ — zrušené, `50c26c5` |
| AL | **H** | ~~`IH01.01` ako `IfcWall / STANDARD`~~ → `IfcCovering / MEMBRANE`, 4 occ + typ, `45ea35d` |
| AB | **H** | ~~blok 0.41×1.25×0.30 ako `IfcStair`~~ → `IfcFooting / PAD_FOOTING`, `ZD02.05`, `45ea35d` |
| AC | **H** | ~~`ZD02.03/.04` `FLOOR`; occurrence `ZD02.01` typovaná `ZD02.04`~~ — typ premenovaný, `BASESLAB`, `45ea35d` |
| AM | O | `PredefinedType` — steny hotové (`45ea35d`): 159 occ podľa §5 + všetkých 12 `IfcWallType`. Číslo 383 = **314** `NOTDEFINED` + **69** `IfcFlowTerminal`, ktoré atribút v IFC4X3 nemajú vôbec (fáza 10). Otvorených ostáva **67** occurrences bez pravidla v §5: 8 `IfcSlab DZ02`, 19 `IfcCurtainWall`, 22 `IfcFurniture`, 12 `IfcRailing`, 5 `SC01` |
| AN | **H** | ~~`KV01` `MOLDING`~~ → `COPING`, 2 occ + typ, `45ea35d` |
| AO | O | atika hotová (`50c26c5`): 8× `IfcRelAggregates` na `SN02.01`, 18 dielov, časti odobrané z kontajnmentu. Fasádne zateplenia zostávajú — fáza 6 |

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
| I | O | 14 MEP priestorov s `LongName = 'Space'` a číslom o podlažie nižšie; +78.83 m² |
| J | O | schodisko a 2 šachty existujú na 2NP–4NP nepomenované; §5 #1 pôvodného handoveru uzavretá zle; na 1NP chýbajú |
| H | O | 1NP: 2 prvky z 247 v miestnostiach |
| G | O | 16 z 18 strešných vpustí v `IfcSpace` na 3NP; 2 `ST01.10` v zlom podlaží |
| K | O | 10 dverí bez priestorového kontajnera |
| L | O | `IfcRelSpaceBoundary` 0× |
| Z | O | 22 rekonštruovaných priestorov bez `Qto_BodyGeometryValidation` |
| Q | O | 3NP nemá prenajímateľnú zónu |
| R | O | súčet plôch 2012.88 m² vs 2031.95 z handoveru — rozdiel 19.07 m² |
| AW | O | **85 častí fasády je súčasne agregovaných aj kontajnovaných** — 70 `IfcMember` `LOP02` a 9 `AZ01`, 6 `IfcPlate` `TI06.01`. Časti sedia o podlažie vyššie než ich `IfcCurtainWall` (`PL01` v 3NP → časti v 4NP; `LP03.01` v 4NP → časti v 5NP). Invariant 7 na základni zlyháva, nie až po fáze 1 |

### Materiály a skladby
| # | | vec |
|---|---|---|
| AH | **H** | ~~164 `IfcMaterialConstituent` bez `IfcShapeAspect`~~ — 0 na occurrence úrovni, `70d17af` |
| AI | **H** | ~~„Dřevo obecné" na krídle LOP~~ — vyriešilo sa rozhodnutím 27, `70d17af` |
| AQ | O | layer sety nesedia s výpisom: `ST01.10` chýbajú spádové kliny, ETICS majú 1 zo 6 vrstiev |
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
| 2NP | `1.31` | **`2.15`** | 2.89 | 1.70 × 1.70 | Inštalačná šachta |
| 2NP | `1.34` | **`2.16`** | 1.23 | 0.60 × 2.05 | Inštalačná šachta |
| 2NP | `1.36` | **`2.17`** | 1.29 | 0.55 × 2.35 | Inštalačná šachta |
| 2NP | `1.35` | **`2.18`** | 5.05 | 2.15 × 2.35 | Inštalačná šachta |
| 2NP | `1.28` | **`2.19`** | 0.75 | 0.33 × 2.27 | Inštalačná šachta |
| 2NP | `1.29` | **`2.20`** | 19.71 | 2.70 × 7.30 | Schodiskový priestor |
| 3NP | `2.22` | **`3.15`** | 2.89 | 1.70 × 1.70 | Inštalačná šachta |
| 3NP | `2.29` | **`3.16`** | 1.29 | 0.55 × 2.35 | Inštalačná šachta |
| 3NP | `2.28` | **`3.17`** | 5.05 | 2.15 × 2.35 | Inštalačná šachta |
| 3NP | `2.20` | **`3.18`** | 0.75 | 0.33 × 2.27 | Inštalačná šachta |
| 3NP | `2.27` | **`3.19`** | 1.48 | 0.55 × 2.70 | Inštalačná šachta |
| 3NP | `2.26` | **`3.20`** | 17.82 | 2.70 × 6.60 | Schodiskový priestor |
| 4NP | `3.21` | **`4.05`** | 1.48 | 0.55 × 2.70 | Inštalačná šachta |
| 4NP | `3.20` | **`4.06`** | 17.15 | 2.70 × 6.35 | Schodiskový priestor |

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
| **0** | `tests/test_invariants.py` | testy invariantov, `AUDIT.md` a `BEP_ANNEX.md` do repa — **brána nesplnená**, viď §9 |
| **1** | `14_fix_classes.py`, `15_fix_roof_assembly.py` | #T #V #AL #AB #AC #AN #AM; dve `FLAT_ROOF`; atika do `SN02.01` |
| **2** | `16_fix_psets.py` | #A #B #E #AH #AI (117 occurrence setov) |
| **3** | `17_dedup_types.py` | #AE #O #AK #AA #AF |
| **4** | `18_snim_inst.py` | #M #N #P #S #Y #AP; `LOP02` → `LP02`; swap dverí na 3NP |
| **5a** | `19_fix_type_names.py` | #AF — zlúčenie 4 dvojíc `IfcCoveringType`, typ `DD01.05` → `DD01.04` |
| **5b** | `20_fix_spaces.py` | #I #J (prečíslovanie §6, šachty na 1NP) #Z #Q #R |
| **6** | `21_fix_containment.py`, `22_space_boundaries.py` | #G #H #K #L #AO; agregáty skladieb |
| **7** | `23_lop_fields.py` | 48 vnorených `IfcCurtainWall`, `Ucw`, `Qto` |
| **8** | `24_layer_sets.py` | #AQ #AU #AS; layer sety na typoch; `IfcGroup` S1–S9 |
| **9** | `25_fix_numeric.py`, `26_sweep_orphans.py` | #AJ #F + finálna kontrola |
| **10** | `27_sanitary.py` | pôvodný krok 13 |
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
