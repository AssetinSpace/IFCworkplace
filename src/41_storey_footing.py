"""Fáza 22 — #BL a `ZD02.05` podľa rozhodnutí z §44.

    python src/41_storey_footing.py            # dry-run
    python src/41_storey_footing.py --apply    # zapíše out/ASR_v29.ifc

Nález je v §44. Rozhodnutia Samuela k nemu:

* **#BK** — *„šak dobre že majú zapísaný predefined type, všetko ok, nič
  nerieš."* Tých 2416 zostáva; zapisuje sa ako vedomá odchýlka do
  `BEP_ANNEX.md` §2.9. Tento skript sa ich **nedotkne**.
* **#BL** — *„presunúť do psetu."*
* **`ZD02.05`** — *„kľudne aj bez predefined type."*
* **`ST01.31`** — *„nechať TOPPING, doplniť dôvod."* Zápis, nie zmena modelu.

A · #BL — `Elevation` do `Pset_BuildingStoreyCommon`
----------------------------------------------------
`lexical/IfcBuildingStorey.html`: *„IFC4.3.0.0-DEPRECATION This attribute
is deprecated and shall no longer be used. Within Pset_BuildingStoreyCommon
use ElevationOfSSLRelative or ElevationOfFFLRelative instead."*

Ktorá z tých dvoch, docs nepovedia — a **sú to dve rôzne veci**: úroveň
nosnej dosky proti úrovni nášľapnej vrstvy. Rozhodlo meranie, nie odhad.
Horná hrana vrstiev podlahy (`PD02.*`, `PD03.*`) sedí na `Elevation`
**presne**, kým horná hrana nosných dosiek (`SD02`, `ZD02`) je stabilne
150 mm pod ňou:

    podlažie   Elevation   najbližšia SSL   Δ      najbližšia FFL   Δ
    1NP                0                0    0                  0    0
    2NP             5000             4850 −150               5000    0
    3NP             9200             9050 −150               9200    0
    4NP            13400            13250 −150              13400    0

Je to teda **`ElevationOfFFLRelative`**. Skript si tú zhodu **meria sám**
a vlastnosť zapíše len tam, kde ju našiel — inak by tvrdil o podlaží niečo,
čo neoveril.

Slovo „Relative" v mene zvádza k tomu, že ide o odstup od `Elevation`
podlažia. Nejde: docs k obom vlastnostiam hovoria *„given in elevation
above the local zero height"*, teda absolútne. Zapisuje sa preto tá istá
hodnota, akú niesol atribút.

**5NP vlastnosť nedostane.** Nesie 5 prvkov — 4 vpuste `OV04` a jednu
vrstvu strechy `ST01` — a **žiadnu podlahu**. Zapísať tam nášľapnú vrstvu
by bolo tvrdenie o niečom, čo v modeli nie je. Docs to výslovne pripúšťajú:
*„If the level varies and there is no significantly more prominent
elevation, then this property may be omitted."* Hodnota sa tým nestráca —
`placement z` je 16954 rovnako ako atribút, overené na všetkých piatich.

Atribút sa maže **na všetkých piatich**, lebo výška je v `ObjectPlacement`
a ten je overene nedotknutý (§34). Docs to potvrdzujú dvakrát: *„The local
placement of the IfcBuildingStorey is determined by the ObjectPlacement.
The value of Elevation is for informational purposes only."*

B · `ZD02.05` — `PredefinedType` preč
--------------------------------------
`PAD_FOOTING` je *„an element that transfers the load of a single column
(possibly two) to the ground"* a nad tým blokom žiadny stĺp nie je — nesie
schodisko. `STRIP_FOOTING` ani `FOOTING_BEAM` nesedia tiež.

Nesúmernosť, ktorá je v schéme a treba ju vedieť: **na occurrence je
atribút `OPTIONAL`, na type nie.**

    ENTITY IfcFooting  … PredefinedType : OPTIONAL IfcFootingTypeEnum;
    ENTITY IfcFootingType … PredefinedType : IfcFootingTypeEnum;

Occurrence teda hodnotu stratí úplne, typ dostane `NOTDEFINED` — *„The type
of footing is not defined."* Zmazať ju z typu sa nedá, prázdny atribút by
bol porušenie schémy. Význam prvku zostáva v `Name` a `Description`
(„Základový blok pod schodiskom", „Schodiskový blok základového systému“),
ktoré sa nemenia.

Precedens je #BF: *chýbajúca vlastnosť je pravdivá, neplatná hodnota nie.*

Účtovníctvo GUID
----------------
`Pset_BuildingStoreyCommon` na podlažiach **už je** (nesie `AboveGround`),
takže sa nezakladá nový `IfcPropertySet` ani `IfcRelDefinesByProperties`.
`IfcPropertySingleValue` nie je `IfcRoot`, `GlobalId` nemá. Allowlist je
preto prázdny z oboch strán.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell
import ifcopenshell.geom as geom
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v28.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v29.ifc")

PSET = "Pset_BuildingStoreyCommon"
PROP = "ElevationOfFFLRelative"
FOOTING = "ZD02.05"

# Predpony vrstiev podlahy. Ich horná hrana je nášľapná vrstva.
PODLAHA = ("PD02", "PD03")

# Dotyk nikdy nevyjde ako presná nula: bbox sa počíta v metroch a násobí
# tisícom. Prah je preto 1 mm a skutočná odchýlka sa vypisuje (§42).
PRAH_MM = 1.0


def placement_z(p):
    """Absolútne z umiestnenia — reťaz `PlacementRelTo` až po koreň."""
    z = 0.0
    while p is not None:
        z += p.RelativePlacement.Location.Coordinates[2]
        p = p.PlacementRelTo
    return z


def horne_hrany_podlah(model):
    """Horné hrany vrstiev podlahy v mm. Meria sa, nepredpokladá."""
    ciel = [e for e in model.by_type("IfcProduct")
            if (e.Name or "").startswith(PODLAHA)]
    s = geom.settings()
    s.set("use-world-coords", True)
    it = geom.iterator(s, model, include=ciel)
    hrany = []
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3) * 1000.0
            hrany.append(float(v[:, 2].max()))
            if not it.next():
                break
    return hrany


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    m = ifcopenshell.open(args.src)
    print("vstup :", args.src)
    print("výstup:", args.dst, "" if args.apply else "(dry-run)")
    print()

    # ---------------- A · #BL --------------------------------------------
    print("A · #BL — Elevation do Pset_BuildingStoreyCommon")
    hrany = horne_hrany_podlah(m)
    print("    vrstiev podlahy zmeraných :", len(hrany))

    podlazia = sorted(m.by_type("IfcBuildingStorey"),
                      key=lambda s: s.Elevation if s.Elevation is not None else 0)
    plan_a, max_odch = [], 0.0
    for st in podlazia:
        ev = st.Elevation
        pset = None
        for r in st.IsDefinedBy or []:
            if r.is_a("IfcRelDefinesByProperties"):
                d = r.RelatingPropertyDefinition
                if d.is_a("IfcPropertySet") and d.Name == PSET:
                    pset = d
        ma_prop = pset is not None and any(
            p.Name == PROP for p in (pset.HasProperties or []))

        if ev is None:
            print("    %-5s Elevation už nie je — nič" % st.Name)
            continue

        # poistka: atribút nesmie niesť inú výšku než umiestnenie, inak
        # by sa jeho zmazaním stratil údaj, ktorý inde nie je
        zp = placement_z(st.ObjectPlacement)
        if abs(zp - ev) > PRAH_MM:
            print("    ZASTAVENÉ: %s má Elevation %.1f, ale placement z %.1f"
                  % (st.Name, ev, zp))
            return 1
        max_odch = max(max_odch, abs(zp - ev))

        blizko = [h for h in hrany if abs(h - ev) <= PRAH_MM]
        plan_a.append((st, pset, ev, len(blizko), ma_prop))
        print("    %-5s Elevation %8.0f | placement z sedí | vrstiev podlahy "
              "na tej úrovni: %3d %s"
              % (st.Name, ev, len(blizko),
                 "→ %s" % PROP if blizko else "→ bez vlastnosti (podlaha tam nie je)"))
    print("    najväčšia odchýlka placement × Elevation: %.3g mm" % max_odch)

    chyba_pset = [st.Name for st, ps, _, _, _ in plan_a if ps is None]
    if chyba_pset:
        print("    ZASTAVENÉ: %s nemá %s, ktorý sa má doplniť" % (chyba_pset, PSET))
        return 1

    # ---------------- B · ZD02.05 ----------------------------------------
    print()
    print("B · ZD02.05 — PredefinedType preč")
    occ = [o for o in m.by_type("IfcFooting") if (o.Name or "").startswith(FOOTING)]
    typ = [t for t in m.by_type("IfcFootingType") if (t.Name or "") == FOOTING]
    print("    occurrences:", [o.Name for o in occ])
    print("    typ        :", [t.Name for t in typ])
    if len(occ) != 1 or len(typ) != 1:
        print("    ZASTAVENÉ: čakal sa práve jeden prvok a jeden typ")
        return 1

    # poistka: žiadny pset na nich nesmie byť viazaný na PAD_FOOTING —
    # taký by zmenou hodnoty prestal na prvok patriť
    for e in occ + typ:
        mena = set()
        for r in getattr(e, "IsDefinedBy", None) or []:
            if r.is_a("IfcRelDefinesByProperties"):
                mena.add(r.RelatingPropertyDefinition.Name)
        mena |= {p.Name for p in (getattr(e, "HasPropertySets", None) or [])}
        print("    %-16s psety: %s" % (e.is_a(), sorted(mena) or "žiadne"))

    plan_b = []
    if occ[0].PredefinedType is not None:
        plan_b.append(("occurrence", occ[0], None))
    if typ[0].PredefinedType != "NOTDEFINED":
        plan_b.append(("typ", typ[0], "NOTDEFINED"))
    for kde, e, na in plan_b:
        print("    %-10s %s: %s → %s" % (kde, e.Name, e.PredefinedType, na or "$"))

    # ---------------- súhrn ----------------------------------------------
    prida = [x for x in plan_a if x[3] and not x[4]]
    zmaze = [x for x in plan_a if x[2] is not None]
    print()
    print("=" * 70)
    print("A · vlastností %s pridaných : %d" % (PROP, len(prida)))
    print("A · atribútov Elevation zmazaných : %d" % len(zmaze))
    print("B · PredefinedType zmenených      : %d" % len(plan_b))

    if not (prida or zmaze or plan_b):
        print("\nNETREBA NIČ — model je už opravený.")
        return 0
    if not args.apply:
        print("\ndry-run, nič sa nezapísalo. Spusti s --apply.")
        return 0

    for st, pset, ev, blizko, ma_prop in plan_a:
        if blizko and not ma_prop:
            prop = m.create_entity(
                "IfcPropertySingleValue", Name=PROP,
                Specification="Presunuté zo zrušeného atribútu "
                              "IfcBuildingStorey.Elevation (IFC4.3). Horná hrana "
                              "vrstiev podlahy na tejto úrovni: %d prvkov."
                              % blizko,
                NominalValue=m.create_entity("IfcLengthMeasure", float(ev)))
            pset.HasProperties = list(pset.HasProperties or []) + [prop]
        st.Elevation = None

    for _, e, na in plan_b:
        e.PredefinedType = na

    m.write(args.dst)
    print("\nzapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
