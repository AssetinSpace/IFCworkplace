"""Fáza 21 — #BI a #BJ: fyzika materiálov proti vykreslenému výpisu.

    python src/40_fix_material_physics.py            # dry-run
    python src/40_fix_material_physics.py --apply    # zapíše out/ASR_v28.ifc

Nález je v §43, meranie bolo **očami na vykreslených stranách** výpisu
`D.1.1.09`, nie cez ``pdftotext`` — teda nezávisle od nástroja, ktorým sa
hodnoty čítali pôvodne.

#BI · `Zdivo nosné` nesie μ = 20, ktoré mu výpis nedáva
--------------------------------------------------------
Riadok muriva uvádza **len λ = 0,093**. μ = 20 patrí vrstve **o riadok
vyššie** — „Suchá omietková zmes pre jadrové omietky… faktor difúzneho
odporu μ = 20" — a to je iný materiál. Platí to na dvoch stranách naraz,
S8 v.7 aj S9 v.7.

Ako sa to stalo, sa dá zopakovať. Bez ``-layout`` vypíše ``pdftotext``::

    odporu μ= 20
    Keramické murivo, dutinové, brúsené,
    hr. 250 mm, λ=0,093 [W/(m.K)]

Okno okolo riadku muriva teda μ pohltí, hoci patrí predchádzajúcej vrstve.
``Pset_MaterialHygroscopic`` na tom materiáli nesie **iba** tú dvojicu,
takže sa maže celý — ``Properties`` je ``SET [1:?]`` a prázdna sada by
bola porušenie schémy.

#BJ · `Izolace EPS` nemá ρ ani μ, hoci ich výpis dáva
------------------------------------------------------
Fáza 17 ten materiál čítala z ``PD02`` v.6, kde je len λ = 0,035. Tie isté
dosky sú však aj v ``ST01.10`` v.10 a v.11:

    Dosky z expandovaného penového polystyrénu, EPS 150, λ=0,035,
    ρ=23-28 kg/m³, μ=30-70

a materiál nesú — dve occurrences ``ST01.10b`` majú ``Izolace EPS``
(overené v modeli, nie predpokladané). Hodnoty sú teda **doložené**, nie
odvodené, a zhodujú sa s tými, ktoré už nesie ``Izolace EPS spadove
kliny``. To sedí s rozhodnutím #BB — rovnaký výrobok má rovnaké vlastnosti.

Zápis kopíruje fázu 17 doslova: ``IfcMaterialProperties`` na
``IfcMaterial`` (psety sú ``PSET_MATERIALDRIVEN``), rozsah ρ ako
``IfcPropertyBoundedValue``, μ ako dvojica ``Lower``/``Upper``, a každá
hodnota nesie v ``Specification`` riadok výpisu, z ktorého pochádza.

Pozn.: ``IfcProperty`` má v IFC4.3 ``Specification``, nie ``Description``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v27.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v28.ifc")

MURIVO = "Zdivo nosné"
EPS = "Izolace EPS"

#: Riadok pôvodu na λ muriva citoval aj μ=20, teda tvrdil o výpise niečo,
#: čo v ňom nie je. Opravuje sa spolu s hodnotou — inak by dokument ostal
#: svedkom vlastnej chyby.
MURIVO_STARA = "SN05.01 v.7: Keramické murivo dutinové 250, λ=0,093, μ=20"
MURIVO_NOVA = ("SN05.01 v.7 (výpis ho značí SD02, viď #AV): Keramické murivo "
               "dutinové, brúsené, hr. 250 mm, λ=0,093 [W/(m.K)] — μ výpis "
               "pre murivo neuvádza")

OPORA = ("ST01.10 v.10/11: Dosky z expandovaného penového polystyrénu, "
         "EPS 150, λ=0,035, ρ=23-28 kg/m³, μ=30-70")
POZN_MU = ("Výpis D.1.1.09 uvádza μ bez rozlíšenia vlhkostných podmienok; "
           "rozsah je priradený číselne")


def single(model, name, typ, hodnota, popis):
    return model.create_entity(
        "IfcPropertySingleValue", Name=name, Specification=popis,
        NominalValue=model.create_entity(typ, float(hodnota)))


def bounded(model, name, typ, dolna, horna, popis):
    return model.create_entity(
        "IfcPropertyBoundedValue", Name=name, Specification=popis,
        UpperBoundValue=model.create_entity(typ, float(horna)),
        LowerBoundValue=model.create_entity(typ, float(dolna)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dry = not args.apply

    m = ifcopenshell.open(args.src)
    print("vstup:", args.src)

    mats = {x.Name: x for x in m.by_type("IfcMaterial")}
    for meno in (MURIVO, EPS):
        if meno not in mats:
            sys.exit("materiál %r v modeli nie je. Zastavené." % meno)

    # ---- #BI · zmazať μ z muriva ----------------------------------------
    na_zmazanie = []
    for mp in m.by_type("IfcMaterialProperties"):
        if mp.Material.id() != mats[MURIVO].id():
            continue
        if mp.Name != "Pset_MaterialHygroscopic":
            continue
        na_zmazanie.append(mp)
    # Druhý beh nesmie spadnúť, ale ohlásiť, že netreba nič — §8.
    mp = na_zmazanie[0] if na_zmazanie else None
    if len(na_zmazanie) > 1:
        sys.exit("na %r som čakal najviac jeden Pset_MaterialHygroscopic, "
                 "našiel som %d. Zastavené." % (MURIVO, len(na_zmazanie)))
    if mp is not None:
        mena = sorted(p.Name for p in mp.Properties)
        if mena != ["LowerVaporResistanceFactor", "UpperVaporResistanceFactor"]:
            sys.exit("Pset_MaterialHygroscopic na %r nesie aj niečo iné než μ "
                     "(%s) — mazanie celej sady by vzalo viac, než má. Zastavené."
                     % (MURIVO, ", ".join(mena)))
        print("#BI  %s: mažem %s s %s" % (MURIVO, mp.Name, ", ".join(mena)))
    else:
        print("#BI  %s: μ tam už nie je — hotové" % MURIVO)

    # riadok pôvodu na λ toho istého materiálu tvrdí „μ=20" — treba prepísať
    lambda_props = [p for mp2 in m.by_type("IfcMaterialProperties")
                    if mp2.Material.id() == mats[MURIVO].id()
                    and mp2.Name == "Pset_MaterialThermal"
                    for p in mp2.Properties if p.Name == "ThermalConductivity"]
    if len(lambda_props) != 1:
        sys.exit("na %r som čakal práve jednu ThermalConductivity, našiel "
                 "som %d. Zastavené." % (MURIVO, len(lambda_props)))
    spec = lambda_props[0].Specification or ""
    prepisat = spec == MURIVO_STARA
    if not prepisat and spec != MURIVO_NOVA:
        sys.exit("riadok pôvodu na λ %r nevyzerá ako čakám (%r) — neprepisujem "
                 "naslepo. Zastavené." % (MURIVO, spec))
    print("     riadok pôvodu: %s" % ("prepisujem, μ=20 cituje aj on"
                                      if prepisat else "už opravený"))

    # ---- #BJ · doplniť ρ a μ na EPS -------------------------------------
    uz = {mp2.Name for mp2 in m.by_type("IfcMaterialProperties")
          if mp2.Material.id() == mats[EPS].id()}
    print("#BJ  %s: má %s" % (EPS, ", ".join(sorted(uz)) or "nič"))
    pridat = []
    if "Pset_MaterialCommon" not in uz:
        pridat.append(("Pset_MaterialCommon", "MassDensity"))
    if "Pset_MaterialHygroscopic" not in uz:
        pridat.append(("Pset_MaterialHygroscopic", "μ Lower/Upper"))
    for a, b in pridat:
        print("     pridám %-28s %s" % (a, b))
    if not pridat:
        print("     nič na pridanie")

    # ---- kontrola: nesú tie dosky naozaj tento materiál? ----------------
    nositelia = 0
    for e in m.by_type("IfcCovering"):
        for r in (getattr(e, "HasAssociations", None) or ()):
            if not r.is_a("IfcRelAssociatesMaterial"):
                continue
            d = r.RelatingMaterial
            layers = []
            if d.is_a("IfcMaterialLayerSetUsage"):
                layers = d.ForLayerSet.MaterialLayers
            elif d.is_a("IfcMaterialLayerSet"):
                layers = d.MaterialLayers
            if any(l.Material is not None and l.Material.id() == mats[EPS].id()
                   for l in layers):
                nositelia += 1
    print("     occurrences s materiálom %r: %d" % (EPS, nositelia))
    if not nositelia:
        sys.exit("materiál %r nenesie ani jedna occurrence — opora z "
                 "ST01.10 v.10/11 by neplatila. Zastavené." % EPS)

    if not pridat and mp is None and not prepisat:
        print("\nNETREBA NIČ — model je už opravený.")
        return 0

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    removed = []
    # Hodnoty mier (IfcPositiveRatioMeasure a spol.) sú v STEP **inline**,
    # nie samostatné entity — `id()` im vracia 0 a `by_id(0)` spadne.
    # Zaniknú spolu s vlastnosťou, takže sa zametajú len samotné property.
    deti = [p.id() for p in mp.Properties if p.id()] if mp is not None else []
    if prepisat:
        lambda_props[0].Specification = MURIVO_NOVA
    if mp is not None:
        if getattr(mp, "GlobalId", None):
            removed.append(mp.GlobalId)
        m.remove(mp)
        for pid in deti:
            e = m.by_id(pid)
            if not m.get_total_inverses(e):
                m.remove(e)

    if ("Pset_MaterialCommon", "MassDensity") in pridat:
        m.create_entity(
            "IfcMaterialProperties", Name="Pset_MaterialCommon",
            Description=OPORA, Material=mats[EPS],
            Properties=[bounded(m, "MassDensity", "IfcMassDensityMeasure",
                                23, 28, OPORA)])
    if ("Pset_MaterialHygroscopic", "μ Lower/Upper") in pridat:
        popis = OPORA + " — " + POZN_MU
        m.create_entity(
            "IfcMaterialProperties", Name="Pset_MaterialHygroscopic",
            Description=OPORA, Material=mats[EPS],
            Properties=[
                single(m, "LowerVaporResistanceFactor",
                       "IfcPositiveRatioMeasure", 30, popis),
                single(m, "UpperVaporResistanceFactor",
                       "IfcPositiveRatioMeasure", 70, popis)])

    m.write(args.dst)
    print("\nzapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": removed, "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
