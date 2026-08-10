# BEP — príloha k modelu OCB

Zoznam rozšírení SNIM a odchýlok od dokumentovaného IFC vzoru, ktoré
model `ASR_v21.ifc` obsahuje. Každá položka uvádza, čo sa spravilo, prečo,
a o akú oporu sa opiera.

Register vád, meranie a postup sú v `AUDIT.md`; táto príloha je jeho
výťah pre BEP — teda to, čo musí vedieť ten, kto model preberá.

**Schéma:** IFC4X3_ADD2. Autoritatívny zdroj: publikované docs
buildingSMART, `IFC/RELEASE/IFC4_3`. Citácie sú doslovné.

---

## 1. Názvoslovie SNIM

| pravidlo | znenie |
|---|---|
| štruktúra mena | `kód.UOT.INST`, pri dvojúrovňových kódoch `kód.INST` |
| šírka `INST` | pevne 4 znaky (`LP02.0001`) |
| `UOT` | dve číslice |
| poradie `INST` | podľa geometrie: podlažie → Y → X → Z, zaokrúhlenie 10 mm |
| `INST` na typoch | **nie** — `IfcTypeObject` je spoločný pre všetky occurrences |

Dvojúrovňových kódov je v modeli 18, nie 17 ako uvádza
`snim_mapovanie.csv`. Rozlišuje sa **šírkou** `INST`, nie zoznamom kódov —
`PL01.0004` je kód.INST, `PH01.10` je kód.UOT.

**Rozšírenia oproti pôvodnému číselníku**

| kód | čo | dôvod |
|---|---|---|
| `LP02` | bolo `LOP02` | zjednotenie rodiny `LP01` krídlo, `LP02` príčeľ, `LP03` akustická zástena |
| `ZD02.05` | základový blok pod schodiskom | rad `ZD02.01`–`.04` sú dosky, `.05` blok |
| `SD03`, `SD04` | tretie schodisko na 3NP | pôvodne netypované `SC01` |
| `OK01` | krídla LOP, 125 `IfcPlate` | oddelené od `LP01`, ktoré nesie 26 `IfcWindow` |

**Kód nesie užitie, nie výrobok.** Preto zostávajú rovnomenné skupiny
`DD01.02`, `DD02.03`, `DD03.03`, `DD04.03` (dvojkrídlové aj jednokrídlové)
a `DD01.06`. Nie je to duplicita, ale zámer.

---

## 2. Odchýlky od dokumentovaného IFC vzoru

### 2.1 Vnorený `IfcCurtainWall`

48 polí LOP je vnorených pod 12 `PL01` cez `IfcRelAggregates`; panely
visia na poliach, nie na fasáde. Schéma to nezakazuje a `IfcCurtainWall`
je `IfcBuiltElement`, takže agregácia je legálna — vzor je však
nedokumentovaný. Bez neho by sa `Ucw` a plochy nedali viesť po poliach,
ako to žiada teplo-technická analýza.

### 2.2 Agregácia krytiny do steny, ktorá má vlastný tvar

Atika (`ST01.30/.31/.32`, `KV01` → `SN02.01`) a fasádne zateplenia
(`FS01.*` → stena) sú do steny agregované cez `IfcRelAggregates`, hoci
stena má vlastnú reprezentáciu. Dôvod: `IfcRelCoversBldgElements` je
v IFC4.3 **deprecated**, a IFC4.3 zároveň zrušilo `IfcWallElementedCase`
aj `IfcSlabElementedCase`, teda entity, ktoré ten vzor pomenúvali.

Ten istý vzor platí aj pre **obvodovú izoláciu základovej dosky**:
sedem `FS03.01` je agregovaných do `ZD02.01.0001`. Izolácia pokrýva celú
zvislú hranu dosky (prekryv 500 mm = plná hrúbka) a typ sa volá
`Izolace_ZD_120`. Precedens je v `AUDIT.md` §4: krytina na doske do dosky
patrí.

**Dva rôzne celky sú zámer.** `FS03.01.0008` a `.0009` zostávajú
agregované do stien, ktoré naozaj pokrývajú, zvyšných sedem do dosky.
Rozhodnutie Samuela: *„budú oddelené, proste to nie je skladba, ale len
nalepené na základovú dosku.“* Izolácia nie je jedna súvislá konštrukcia,
ktorú by bolo treba viesť pod jedným celkom — každý kus patrí k tomu, na
čom je nalepený.

### 2.3 Zóny šácht mimo požiarneho rámca

Sedem `IfcZone` nesie `ObjectType` `'ElevatorShaft'` (2) a `'RisingDuct'`
(5). Spec tie hodnoty uvádza vetou *„in case of a zone denoting a (fire)
compartment"*, teda v požiarnom kontexte; tu sa používajú na zvislé
zoskupenie šachtových priestorov naprieč podlažiami. Opora pre význam je
doslovná: *`'ElevatorShaft'`: a collection of spaces within an elevator,
**potentially going through many storeys***.

### 2.4 Prenajímateľnosť 3NP inou cestou než PZ

`PZ01`–`PZ10` sú `IfcSpatialZone` s vlastným telesom. 3NP takú zónu nemá
a vyrobiť ju by znamenalo fabrikovať geometriu. Namiesto toho je
`IfcZone` „Nájomné priestory 3NP" s 11 priestormi, vložená do `IfcZone`
`Pronajmutelné`. `IfcZone` geometriu niesť **nemôže** — *„A zone does not
have its own shape representation"* — takže sa nič nefabrikuje. WR1
`IfcSpace` aj `IfcZone` ako členov výslovne povoľuje.

Dôsledok: najvyššia zóna drží dva druhy členov — `IfcSpatialZone` pre
1NP a 2NP, `IfcZone` pre 3NP. Je to nesúrodé a je to vedomé.

**Väzba zón na priestory.** `PZ01`–`PZ10` dostali `IfcRelReferencedInSpatialStructure`
na **42 priestorov**; zón bez väzby je 0. Schéma to výslovne povoľuje —
pravidlo `AllowedRelatedElements` má výnimku *„an `IfcSpace` can be
referenced by another spatial structure element, in particular by an
`IfcSpatialZone`"*. Priraďovalo sa **podielom plochy z priemetu telesa**,
nie bboxom: `PZ01` má bbox celého pôdorysu budovy, ale plochu 611,54 m²,
takže bboxom by pohltila štyri susedné zóny. Prah je necitlivý — 0,3 aj
0,7 dávajú rovnakých 42 väzieb.

Zónu nedostalo 33 zo 75 priestorov a ani jeden prípad nie je vada: 22 je
celé 3NP (nesie ho `IfcZone` vyššie), 9 sú služobné priestory 2NP mimo
nájomnej zóny, 2 sú šachty mimo telies zón. Jedna vedomá odchýlka: `2.19`
je šachta, ktorá geometricky leží vnútri `PZ10` „Nájomný priestor", a
väzbu preto dostala — vzťah znamená „referenced in", nie „je
prenajímateľná". Jej náprotivok na 3NP väzbu nemá, lebo tá zóna vznikla
z legendy.

### 2.5 `IfcDistributionSystem` bez siete

Zariaďovacie predmety sú v troch `IfcDistributionSystem`:

| systém | `PredefinedType` | členov | opora |
|---|---|--:|---|
| Zdravotechnika | `SEWAGE` | 46 | *„Sewage collection system."* Všetkých **51 `IfcDistributionPort` nesie `SystemType = SEWAGE`** |
| Odvodnenie strechy | `RAINWATER` | 20 | *„Rainwater… which directly falls on a parcel."* Proti `STORMWATER`, ktoré je povrchový odtok |
| Podlahové vpuste | `DRAINAGE` | 5 | *„Drainage collection system."* Vpuste `OV01.01` sú vnútri budovy, nie na streche |

**Čo treba vedieť pri preberaní:** model má 51 portov a **0
`IfcFlowSegment`**, takže sieť v ňom nie je — systémy sú zoskupenia
zariadení, nie prepojené vetvy. Schéma to nezakazuje:
`IfcDistributionSystem` je podtyp `IfcSystem`, teda zoskupenie, a žiadne
pravidlo nevyžaduje, aby obsahoval segmenty. Kto bude systémy používať na
výpočet, musí vedieť, že topológia chýba.

Do odvodnenia strechy patria aj **dva poistné prepady `OV04.03`**, ktoré
predtým stáli mimo akéhokoľvek systému.

### 2.6 Rekonštruované priestory

Pravidlo projektu je **nefabrikovať geometriu**, ktorá v modeli nie je.
Priestory sú jediná výnimka, lebo precedens vznikol už v krokoch 1–13
(`build_1np_spaces.py`). Fáza 5c pridala 6 šachtových priestorov, a to
len tam, kde void existujúceho otvoru dokazuje, že šachta tým podlažím
prechádza. Tvar sa preberá z otvoru a oreže na pásmo podlažia; výťahové
šachty sa nekreslili.

---

## 3. Rozhodnutia o triede a type, ktoré nemá excel

SNIM excel `MOC_BEP_05` neexistuje, takže autoritou je dokumentácia
a rozhodnutie projektanta. Tieto je nutné vedieť pri preberaní:

| prvok | trieda / typ | opora |
|---|---|---|
| `IH01.01` | `IfcCovering / MEMBRANE` | „nepriepustná vrstva… hydroizolačný materiál" |
| `ST01.31` OSB | `IfcCovering / TOPPING` | „vrstva na vyrovnanie povrchu" |
| `KV01` | `IfcCovering / COPING` | „ochranné zakončenie steny či atiky" |
| `SN02.01` atika | `IfcWall / PARAPET` | — |
| `ZD02.03/.04` | `IfcSlab / BASESLAB` | základové dosky nie sú `IfcFooting` |
| `ZD02.05` | `IfcFooting / PAD_FOOTING` | blok, nie doska |
| `SN11.01/.02` | `IfcWall / PARTITIONING` | test „nie je prevažne zvislý → `IfcPlate`" tu neplatí |
| strecha | 2× `IfcRoof / FLAT_ROOF` | `Decomposes` je `SET[0:1]` |
| `OV01.01` | `IfcWasteTerminal / GULLYTRAP` | výkres „krytá pochôdznou mriežkou"; spec `GULLYTRAP` „fitted with a grating… discharges water through a trap" |
| `OV04.01/.02/.04/.05` | `IfcWasteTerminal / ROOFDRAIN` | „set into the roof, collects rainwater" |
| `WC01` | `IfcSanitaryTerminal / URINAL` | §7 |
| `WC02`, `WC04` | `TOILETPAN` | §7 |
| `WC03`, `WC05` | `WASHHANDBASIN` | §7 |
| `WC07` | `SINK` | §7 |
| `DZ02` steny výťahových jám | `IfcWall / SOLIDWALL` | **návrat k originálu** — `data/ASR.ifc` má `IfcWall` s `Pset_WallCommon.LoadBearing = True`; na `IfcSlab` ju prepísala pôvodná pipeline. Spec: *„massive wall… concrete walls… that are load bearing"* |
| `VP02` sklopné madlá WC | `IfcRailing / HANDRAIL` | popis „Bezbariérové WC – madlo sklopné"; spec *„support for loads applied by human occupants (at hand height)"* |
| `ZV01.01` | `IfcRailing / GUARDRAIL` | „Zábradlí 1000 se svislou výplní"; spec *„guard… from falling off a stair, ramp or landing"* |
| `ZV01.02`, `KV02` | `IfcRailing / HANDRAIL` | „Madlo 1000", „Madlo – kovové" — madlo, nie bariéra |
| `OV02` prístrešky vstupov | `IfcShadingDevice / AWNING` | *„A rooflike shelter… extending over a doorway… in order to provide protection“*. Zvažovaný `IfcBuiltElement` — schéma ho pripúšťa (`is_abstract() = False`) — ale konkrétna entita má prednosť pred všeobecnou; rozhodnutie Samuela |
| `OV04.03` poistný prepad | `IfcWasteTerminal / USERDEFINED`, `ObjectType = 'Poistný prepad'` | enum hodnotu pre prepad nemá; `ROOFDRAIN` ústi do systému, prepad ústi voľne von |
| `ZV04.01` rebrík s košom | `IfcStair / LADDER` | spec: *„a series of bars or steps between two upright elements used for climbing"* |
| `SC01` | `IfcStair / HALF_TURN_STAIR` | **zmerané, nie prevzaté z popisu**: smery stúpania oboch ramien zvierajú 180,0° na všetkých troch schodiskách |
| `SD04` | `IfcStairFlight / STRAIGHT` | priame rameno 4500–5100 mm |

**Poznámka k `IfcBuiltElement`.** Fáza 11 ním `OV02` zapísala, fáza 16 to
zmenila na `IfcShadingDevice / AWNING`. Schéma `IfcBuiltElement` pripúšťa
(`is_abstract() = False` pre entitu aj typ) a `PredefinedType` nedefinuje —
význam by niesol `ObjectType`, na type `ElementType`. Docs ten prípad menujú:
*„when the concrete entity instantiated does not have a PredefinedType
attribute… in some exceptional leaf classes“*. V modeli sa nakoniec
nepoužíva; zaznamenané preto, aby to nevyzeralo ako prehliadnutie.

**`IfcCurtainWall` nemá čo nastaviť.** `IfcCurtainWallTypeEnum` obsahuje
iba `USERDEFINED` a `NOTDEFINED`, takže `NOTDEFINED` na všetkých 67
fasádach a poliach je jediná zmysluplná hodnota bez zavedenia vlastného
`ObjectType`.

---

## 4. Vzduch a hrúbky

**Vzduchová dutina** rektifikovanej podlahy `PD03.*` je zapísaná podľa
schémy: vrstva **bez materiálu**, `IsVentilated = UNKNOWN`, meno
„Vzduchová dutina". Spec: *„Air gaps… are represented as an
`IfcMaterialLayer` with the attribute `IsVentilated` having the value TRUE
or UNKNOWN. Such air gaps shall be interpreted as voids (not having a
material)."* `UNKNOWN` a nie `TRUE` preto, že dokumentácia o vetraní
dutiny nehovorí nič.

**Súčet hrúbok vrstiev nikdy nedá hodnotu z výpisu.** Model nesie len
vrstvy s vlastnou geometriou. Pri ETICS to znamená jednu vrstvu zo
šiestich — chýbajú lepidlo, kotvy, stierka so sieťkou a omietka. Izolácia
pritom sedí na milimeter (`FS01.20` 180 mm = S8, `FS01.12` 50 mm = S9).
Doplniť tenké vrstvy do layer setu by rozišlo `TotalThickness` s hrúbkou
prvku, čo `IfcMaterialLayerSetUsage` nedovoľuje.

**Skladby ako `IfcGroup`.** Kódy S1–S9 nesie `IfcGroup` +
`IfcRelAssignsToGroup`, nie `IfcRelAssociatesDocument` ani
`IfcClassification`. Výpis `D.1.1.09` má **osem** skladieb, S7 v ňom nie
je. Založených päť (`S3`, `S4`, `S5`, `S8`, `S9`) — ostatné zdieľajú
kódy s inými skladbami a priradenie podľa kódu by bolo nesprávne.

---

## 4b. Fyzika materiálov

Deväť materiálov nesie λ, ρ, c a μ z výpisu `D.1.1.09`. Zápis je podľa
schémy v `IfcMaterialProperties` na `IfcMaterial`, nie v `IfcPropertySet`
na prvku — psety `Pset_MaterialThermal`, `Pset_MaterialCommon`
a `Pset_MaterialHygroscopic` sú `PSET_MATERIALDRIVEN`.

μ je v `Pset_MaterialHygroscopic` ako dvojica `Lower`/`UpperVaporResistanceFactor`;
`Pset_MaterialThermal` ho nemá. Rozsah `ρ = 23–28` nesie
`IfcPropertyBoundedValue` — šablóna psetu predpisuje jednu hodnotu, tá by
rozsah zahodila. Každá hodnota má v `Specification` riadok výpisu, z ktorého
pochádza.

**Doplnené jednotky.** Model pre λ, ρ ani c jednotku nedeklaroval. Pribudli
do `IfcUnitAssignment` ako `IfcDerivedUnit`: `THERMALCONDUCTANCEUNIT`
(kg·m·s⁻³·K⁻¹), `MASSDENSITYUNIT` (kg·m⁻³), `SPECIFICHEATCAPACITYUNIT`
(m²·s⁻²·K⁻¹). Metre sú z `IfcSIUnit` bez prefixu — projekt je
v milimetroch a bez toho by ρ vyšlo v kg/mm³.

**Fyziku nemá 38 zo 47 materiálov.** Výpis ich neuvádza a tabuľková hodnota
by bola vymyslená. Menovite chýba parotesniaci pás s AL fóliou — vo výpise
je, ale samostatný materiál preň v modeli nie je.

---

## 5. Vady podkladu

Nájdené pri práci; model ich nekopíruje, ale ani neopravuje ticho.

| # | podklad | čo je zle |
|---|---|---|
| AV | `D.1.1.09` | skladba S8 uvádza `SD02` tam, kde má byť `SN05.01` |
| — | `D.1.1.01` | legenda: `PD02.31` vs `.30`; `1.17 WC Muži` má skopírovaný riadok elektrorozvodne |
| AZ | model | 80 z 97 `IfcDoor` nemá `FillsVoids`, teda nie sú zviazané s otvorom |
| Q2 | model | `PZ01`–`PZ10` nereferencujú ani jeden prvok či priestor |

---

## 6. Čo model nemá a mať nebude bez ďalšieho podkladu

* **fyzika materiálov** — λ, ρ, c, μ z výpisu nie sú v `Pset_Material*`;
* **energetické zónovanie** a `IfcRelSpaceBoundary` 2. úrovne — mimo rozsah;
* **okenné hranice** — všetkých 26 `IfcWindow` je agregovaných do
  `IfcCurtainWall` bez `FillsVoids`, takže z miestnosti lúč trafí najprv
  panely fasády;
* **vodorovná plocha pod doskou `IH01`** — doska končí na −0.800 a
  podkladný betón tam začína, na 8.2 mm nie je miesto;
* **9 prvkov s degenerovanou extrúziou** (nulová výška);
* **sieť rozvodov** — v modeli nie je ani jeden kus potrubia.

---

## 7. Čo je overené

| tvrdenie | ako |
|---|---|
| geometria prvkov sa od pôvodného exportu **neposunula** | **0 posunutých bboxov** medzi `data/ASR.ifc` a `ASR_v21.ifc`, na 6 desatinných miest, 2542 spoločných tvarov. Jediný rozdiel v množine tvarov je prekreslenie priestorov 1NP pôvodnou pipeline (42 zaniklo, 22 vzniklo) — viď `AUDIT.md` §34 |
| každý zrušený a nový GUID fáz 1–10 je vysvetlený | 560 + 1118 = 1678, presne veľkosť kumulatívneho allowlistu, 0 mimo neho |
| model je schémovo platný | `validate(express_rules=True)` = 0 hlásení |
| žiadne osirelé entity | invariant 4 = 0 |
| kontajnment je exkluzívny | invariant 7 = 0 |
| plný SNIM kód je jedinečný | invariant 6 = 0 |

Brána po každej fáze proti výstupu predošlej: **zlyhalo 0 zo 7** vo fázach 11, 12, 13 aj 14. `pytest` 8 z 8 (deviaty je pomalý test geometrie, beží na merge).
