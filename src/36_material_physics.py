"""Fáza 17 — #AT: fyzika materiálov z výpisu skladieb do modelu.

Rozhodnutie Samuela z 10. 8.: *„áno, nejakým spôsobom na základe IFC
schémy."*

    python src/36_material_physics.py            # dry-run
    python src/36_material_physics.py --apply    # zapíše out/ASR_v24.ifc

Čo robí
-------
Zapíše λ, ρ, c a μ z `D.1.1.09 Výpis skladieb` na deväť materiálov, ktoré
sa dajú k riadkom výpisu **priradiť dôkazom**, nie odhadom.

Kam to podľa schémy patrí
-------------------------
`Pset_MaterialThermal`, `Pset_MaterialCommon` aj `Pset_MaterialHygroscopic`
sú **`PSET_MATERIALDRIVEN`**: *„The property sets defined by this
IfcPropertySetTemplate are to be encoded in an `IfcMaterialProperties`
entity and assigned to an `IfcMaterialDefinition`."* Nie sú to teda
`IfcPropertySet` na prvku, ale `IfcMaterialProperties` na `IfcMaterial`.

Pozn.: `IfcProperty` má v IFC4.3 namiesto `Description` atribút
**`Specification`** — `Description` na `IfcProperty*` neexistuje a zápis
by spadol. Na `IfcMaterialProperties` `Description` naopak je.

| veličina | pset | vlastnosť | dátový typ |
|---|---|---|---|
| λ | `Pset_MaterialThermal` | `ThermalConductivity` | `IfcThermalConductivityMeasure` |
| c | `Pset_MaterialThermal` | `SpecificHeatCapacity` | `IfcSpecificHeatCapacityMeasure` |
| ρ | `Pset_MaterialCommon` | `MassDensity` | `IfcMassDensityMeasure` |
| μ | `Pset_MaterialHygroscopic` | `Upper`/`LowerVaporResistanceFactor` | `IfcPositiveRatioMeasure` |

**μ nie je v `Pset_MaterialThermal`.** Schéma preň má samostatný pset
s dvojicou `Upper`/`Lower`, čo rieši aj rozsahy typu `μ = 30–70`.

Rozsahy
-------
`μ = 30–70` → `Lower = 30`, `Upper = 70`. Výpis neuvádza, ktorý koniec
platí pri akej vlhkosti, kým schéma áno (*„measured in high/low relative
humidity"*), takže sa hodnoty priraďujú **číselne** a `Description`
vlastnosti to hovorí. Pri jedinej hodnote nesú oba konce to isté číslo.

`ρ = 23–28` → `IfcPropertyBoundedValue` s `LowerBoundValue` a
`UpperBoundValue`. Šablóna psetu predpisuje `IfcPropertySingleValue`,
ale jedna hodnota by rozsah zahodila; `IfcPropertyBoundedValue` je
schémou určený nosič medzí. Odchýlka od šablóny, nie od schémy.

Jednotky
--------
Model deklaruje len `LENGTHUNIT` (mm), `AREAUNIT`, `VOLUMEUNIT`,
`PLANEANGLEUNIT` a jednu `THERMALTRANSMITTANCEUNIT`. Pre λ, ρ a c
jednotky **chýbajú**, takže by ich musel čitateľ hádať. Skript ich preto
doplní do `IfcUnitAssignment` ako `IfcDerivedUnit`:

* `THERMALCONDUCTANCEUNIT` = kg·m·s⁻³·K⁻¹ (W·m⁻¹·K⁻¹)
* `MASSDENSITYUNIT` = kg·m⁻³
* `SPECIFICHEATCAPACITYUNIT` = m²·s⁻²·K⁻¹ (J·kg⁻¹·K⁻¹)

Metre sa berú z **`IfcSIUnit` bez prefixu**, nie z milimetrovej dĺžkovej
jednotky projektu — inak by ρ vyšlo v kg/mm³. Vzor je existujúca
`THERMALTRANSMITTANCEUNIT`, ktorá je postavená rovnako.

Čo NEROBÍ a prečo
-----------------
* **Materiály bez riadku vo výpise sa nedopĺňajú.** Z 47 materiálov
  dostane fyziku 9. Zvyšok výpis neuvádza a generická tabuľková hodnota
  by bola vymyslená — §8.
* Parotesniaci pás s AL fóliou (λ=0,21, c=1470, ρ=1400, μ=370 000) sa
  **nepriraďuje**: v skladbe `ST01.10` je vo výpise, ale samostatný
  materiál preň v modeli nie je.
* `DEKSEPAR` (separačná PE fólia) výpis fyzikou neopisuje, len plošnou
  hmotnosťou.
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v23.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v24.ifc")

DRY_RUN = True

#: materiál → (λ, ρ, c, μ, opora vo výpise)
#: ρ a μ môžu byť dvojica (dolná, horná) = rozsah
FYZIKA = {
    "Izolace EPS spadove kliny": (
        0.035, (23.0, 28.0), None, (30.0, 70.0),
        "ST01.10 v.9: Spádové kliny z EPS 150, λ=0,035, ρ=23-28, μ=30-70"),
    "Izolace EPS": (
        0.035, None, None, None,
        "PD02 v.6: Podlahové dosky z EPS 150, λD=0,035"),
    "Izolace minerální": (
        0.035, None, None, None,
        "FS01.10/.12/.20 v.4: λD=0,035, trieda reakcie na oheň A1"),
    "Izolace XPS": (
        0.036, None, None, None,
        "FS01.11 v.4: λD=0,036, trieda reakcie na oheň E"),
    "Zdivo nosné": (
        0.093, None, None, 20.0,
        "SN05.01 v.7: Keramické murivo dutinové 250, λ=0,093, μ=20"),
    "Beton - Železobeton": (
        1.430, 2300.0, 1020.0, 24.0,
        "SD02 v.14: ŽB doska, betón C25/30, λ=1,430, C=1020, ρ=2300, μ=24"),
    "Hydroizolace - asfaltový pás": (
        None, None, None, 29000.0,
        "ST01.10 v.7/8: SBS modifikovaný asfaltový pás, μ=29000"),
    "Hydrofílna vata": (
        0.037, None, None, None,
        "ST01.20 v.3: Hydrofílne dosky, λD=0,037"),
    "podlahový potěr/mazanina + kari síť KH 20": (
        None, 2100.0, None, 19.0,
        "PD02 v.4: Cementový poter, ρ=2100, μ=19"),
}

#: odvodené jednotky, ktoré model nemá: typ → [(exponent, prefix, meno, typ SI)]
JEDNOTKY = {
    "THERMALCONDUCTANCEUNIT": [
        (1, "KILO", "GRAM", "MASSUNIT"),
        (1, None, "METRE", "LENGTHUNIT"),
        (-3, None, "SECOND", "TIMEUNIT"),
        (-1, None, "KELVIN", "THERMODYNAMICTEMPERATUREUNIT"),
    ],
    "MASSDENSITYUNIT": [
        (1, "KILO", "GRAM", "MASSUNIT"),
        (-3, None, "METRE", "LENGTHUNIT"),
    ],
    "SPECIFICHEATCAPACITYUNIT": [
        (2, None, "METRE", "LENGTHUNIT"),
        (-2, None, "SECOND", "TIMEUNIT"),
        (-1, None, "KELVIN", "THERMODYNAMICTEMPERATUREUNIT"),
    ],
}

POZN_MU = ("Výpis D.1.1.09 uvádza μ bez rozlíšenia vlhkostných podmienok; "
           "hodnoty sú priradené číselne, nie podľa 95/50 a 0/50 % RH.")


def single(model, name, typ, hodnota, popis=None):
    return model.create_entity(
        "IfcPropertySingleValue", Name=name, Specification=popis,
        NominalValue=model.create_entity(typ, float(hodnota)))


def bounded(model, name, typ, dolna, horna, popis=None):
    return model.create_entity(
        "IfcPropertyBoundedValue", Name=name, Specification=popis,
        UpperBoundValue=model.create_entity(typ, float(horna)),
        LowerBoundValue=model.create_entity(typ, float(dolna)))


def doplnit_jednotky(model) -> list[str]:
    """Pridá chýbajúce odvodené jednotky do IfcUnitAssignment."""
    ua = model.by_type("IfcUnitAssignment")[0]
    mame = {u.UnitType for u in ua.Units if u.is_a("IfcDerivedUnit")}
    pridane = []
    nove = list(ua.Units)
    for typ, prvky in JEDNOTKY.items():
        if typ in mame:
            continue
        elems = []
        for exp, prefix, meno, si_typ in prvky:
            si = model.create_entity("IfcSIUnit", UnitType=si_typ,
                                     Prefix=prefix, Name=meno)
            elems.append(model.create_entity("IfcDerivedUnitElement",
                                             Unit=si, Exponent=exp))
        nove.append(model.create_entity("IfcDerivedUnit", Elements=elems,
                                        UnitType=typ))
        pridane.append(typ)
    ua.Units = tuple(nove)
    return pridane


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY", "\n")

    podla_mena = {}
    for mat in model.by_type("IfcMaterial"):
        podla_mena.setdefault(mat.Name, []).append(mat)

    chyba = [n for n in FYZIKA if n not in podla_mena]
    if chyba:
        raise SystemExit("STOP: materiál v modeli nie je: %s" % chyba)
    viac = {n: len(v) for n, v in podla_mena.items()
            if n in FYZIKA and len(v) > 1}
    if viac:
        raise SystemExit("STOP: materiál v modeli viackrát: %s" % viac)

    uz = {p.Material.Name for p in model.by_type("IfcMaterialProperties")
          if p.Material}
    ostava = [n for n in FYZIKA if n not in uz]
    if not ostava:
        print("Idempotencia: všetkých %d materiálov fyziku už má." % len(FYZIKA))
        return 0
    if len(ostava) != len(FYZIKA):
        raise SystemExit("STOP: %d z %d materiálov fyziku už má — "
                         "model je v polovičnom stave"
                         % (len(FYZIKA) - len(ostava), len(FYZIKA)))

    rows, psetov = [], 0
    for meno in sorted(FYZIKA):
        lam, rho, cap, mu, opora = FYZIKA[meno]
        mat = podla_mena[meno][0]

        termal = []
        if lam is not None:
            termal.append(single(model, "ThermalConductivity",
                                 "IfcThermalConductivityMeasure", lam, opora))
        if cap is not None:
            termal.append(single(model, "SpecificHeatCapacity",
                                 "IfcSpecificHeatCapacityMeasure", cap, opora))
        common = []
        if rho is not None:
            if isinstance(rho, tuple):
                common.append(bounded(model, "MassDensity",
                                      "IfcMassDensityMeasure", rho[0], rho[1],
                                      opora))
            else:
                common.append(single(model, "MassDensity",
                                     "IfcMassDensityMeasure", rho, opora))
        hygro = []
        if mu is not None:
            dolna, horna = mu if isinstance(mu, tuple) else (mu, mu)
            popis = opora + " — " + POZN_MU
            hygro.append(single(model, "LowerVaporResistanceFactor",
                                "IfcPositiveRatioMeasure", dolna, popis))
            hygro.append(single(model, "UpperVaporResistanceFactor",
                                "IfcPositiveRatioMeasure", horna, popis))

        for nazov, props in (("Pset_MaterialThermal", termal),
                             ("Pset_MaterialCommon", common),
                             ("Pset_MaterialHygroscopic", hygro)):
            if not props:
                continue
            model.create_entity("IfcMaterialProperties", Name=nazov,
                                Description=opora, Properties=props,
                                Material=mat)
            psetov += 1

        rows.append((meno[:34], lam, rho, cap, mu))

    pridane = doplnit_jednotky(model)

    w = "  %-34s %-7s %-10s %-6s %-9s"
    print(w % ("materiál", "λ", "ρ", "c", "μ"))
    print("  " + "-" * 72)
    for m_, lam, rho, cap, mu in rows:
        f = lambda v: ("%g–%g" % v) if isinstance(v, tuple) else ("—" if v is None else "%g" % v)
        print(w % (m_, f(lam), f(rho), f(cap), f(mu)))
    print("\nmateriálov %d, IfcMaterialProperties %d, doplnené jednotky: %s"
          % (len(rows), psetov, ", ".join(pridane) or "žiadne"))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    model.write(args.dst)
    print("\nzapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
