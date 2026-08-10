# BEP — príloha k modelu OCB

Zoznam rozšírení SNIM a odchýlok od dokumentovaného IFC vzoru, ktoré
model `ASR_v16.ifc` obsahuje. Každá položka uvádza, čo sa spravilo, prečo,
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

### 2.5 `IfcSystem` namiesto `IfcDistributionSystem`

Zariaďovacie predmety sú v troch `IfcSystem`, nie v `IfcDistributionSystem`.
Model má 51 portov a **0 `IfcFlowSegment`** — sieť neexistuje, takže
entita, ktorá ju sľubuje, by klamala. Názvy to hovoria priamo:
„Zoskupenie zariadení — zdravotechnika / strešné vpuste / podlahové
vpuste".

### 2.6 Rekonštruované priestory

Pravidlo projektu je **nefabrikovať geometriu**, ktorá v modeli nie je.
Priestory sú jediná výnimka, lebo precedens vznikol už v krokoch 1–13
(`build_1np_spaces.py`). Fáza 5c pridala 6 šachtových priestorov, a to
len tam, kde void existujúceho otvoru dokazuje, že šachta tým podlažím
prechádza. Tvar sa preberá z otvoru a oreže na pásmo podlažia; výťahové
šachty sa nekreslili.

### 2.7 Schodisko ako zoskupenie, nie ako jeden agregát

Hlavné schodisko je v modeli **tri** `IfcStair` — po jednom na každý beh
medzi podlažiami (1NP→2NP, 2NP→3NP, 3NP→4NP), presne ako hovorí spec:
*„from one floor level to another floor level"*. „Jedno schodisko" nesie
`IfcBuiltSystem` s `Name = SC01`, ktoré tie tri celky zoskupuje.

Zámena za jeden `IfcStair` cez tri podlažia sa **odmietla**: časti
agregátu sa do priestorovej štruktúry neviažu samostatne, takže by sa
stratilo, ktoré rameno patrí do ktorého podlažia. Dnes je to tri údaje,
po zlúčení jeden.

`PredefinedType` toho zoskupenia je `USERDEFINED` s `ObjectType =
"Vertikálna komunikácia — schodisko"`. Hodnota `TRANSPORT` sa nepoužila,
lebo spec ju píše o *transport elements* — výťahoch a eskalátoroch —
a model ani jeden nemá.

Strešné schodisko `SH04.03` je samostatná konštrukcia a v zoskupení nie je.

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
| `OV04.*` | `IfcWasteTerminal / ROOFDRAIN` | „set into the roof, collects rainwater" |
| `WC01` | `IfcSanitaryTerminal / URINAL` | §7 |
| `WC02`, `WC04` | `TOILETPAN` | §7 |
| `WC03`, `WC05` | `WASHHANDBASIN` | §7 |
| `WC07` | `SINK` | §7 |
| `SC01` | `IfcStair / HALF_TURN_STAIR` | dve ramená vedľa seba, podesta na oboch — odmerané, nie odhadnuté |
| `SD03` | `IfcSlab / LANDING` | z exportu, spec vzor pre podesty |
| `SD04`, `SH04.02` | `IfcStairFlight / STRAIGHT` | priama výstupná čiara |
| `SH04.01` | `IfcMember / STRINGER` | schodnica oceľového schodiska |
| `ZV01.01` | `IfcRailing / GUARDRAIL` | 290 mm v zrkadle; „guard… from falling off a stair, ramp or landing" |
| `ZV01.02`, `KV02` | `IfcRailing / HANDRAIL` | 40 mm pri stene, stúpa s ramenom; „support… at hand height… wall mounted" |
| `VP02` | `IfcRailing / HANDRAIL` | sklopné madlo na invalidnom WC, 590–810 mm; nie nábytok |
| `OV04.03` | `IfcWasteTerminal / ROOFDRAIN` | zástupná kocka poistného prepadu; zhodne s `OV04.02` |

**Poistný prepad číselník nemá.** `IfcWasteTerminalTypeEnum` pozná
`FLOORTRAP`, `FLOORWASTE`, `GULLYSUMP`, `GULLYTRAP`, `ROOFDRAIN`,
`WASTEDISPOSALUNIT` a `WASTETRAP` — pre poistný prepad atikou nie je nič.
Použil sa `ROOFDRAIN` zhodne s ostatnými `OV04`; je to obmedzenie
číselníka, nie tvrdenie o budove.

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

## 5. Vady podkladu

Nájdené pri práci; model ich nekopíruje, ale ani neopravuje ticho.

| # | podklad | čo je zle |
|---|---|---|
| AV | `D.1.1.09` | skladba S8 uvádza `SD02` tam, kde má byť `SN05.01` |
| BA | `D.1.1.08` | južný pohľad má v treťom poli 1NP kód `C1-S`; systematicky patrí `C1-J`, ktorý sa vo výkrese nevyskytuje. **Model používa `C1-J`** |
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
| geometria prvkov sa od pôvodného exportu neposunula | 2495 tvarov `IfcBuiltElement`, 0 zmenených, bboxy na 6 desatinných miest, `ASR.ifc` → `ASR_v16.ifc` |
| každý zrušený a nový GUID fáz 1–10 je vysvetlený | 560 + 1118 = 1678, presne veľkosť kumulatívneho allowlistu, 0 mimo neho |
| model je schémovo platný | `validate(express_rules=True)` = 0 hlásení |
| žiadne osirelé entity | invariant 4 = 0 |
| kontajnment je exkluzívny | invariant 7 = 0 |
| plný SNIM kód je jedinečný | invariant 6 = 0 |

Brána na `ASR_v16.ifc`: **zlyhalo 0 zo 7**. `pytest` 9 z 9.
