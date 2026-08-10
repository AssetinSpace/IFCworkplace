"""Fáza 8 — vzduchová dutina a skupiny skladieb (#AS, S1–S9).

    python src/28_layer_sets.py           # dry-run
    python src/28_layer_sets.py --apply   # zapíše out/ASR_v16.ifc

A · #AS — vzduch v dutine
-------------------------
`PD03.*` má druhú vrstvu s materiálom `Výchozí` — to je dutina
rektifikovanej podlahy. Rozhodnutie Samuela: *„ak to je dutina tak tam je
vzduch"*. Schéma na to má presný zápis, `IfcMaterialLayer` §8.10.3.6.1:

    Air gaps within a material layer set are represented as an
    IfcMaterialLayer with the attribute IsVentilated having the value
    TRUE or UNKNOWN. Such air gaps shall be interpreted as voids
    (not having a material).

Vrstva preto stratí materiál, dostane `IsVentilated = UNKNOWN` a meno
„Vzduchová dutina". `UNKNOWN` a nie `TRUE` zámerne: dokumentácia
nehovorí, že dutina je vetraná, len že tam je. Hrúbka sa nemení, takže
súčet vrstiev aj naďalej sedí s hrúbkou prvku a `Usage` ostáva platné.

Tým sa napĺňa aj pravidlo §2 „`IsVentilated` platí len vnútri jedného
prvku" — vrstva je vnútri jedného layer setu, nie samostatný prvok.

B · S1–S9 ako `IfcGroup`
------------------------
Rozhodnutie §2: kódy skladieb nesie `IfcGroup` + `IfcRelAssignsToGroup`,
nie `IfcRelAssociatesDocument` ani `IfcClassification`.

Výpis `D.1.1.09` má **osem** skladieb, nie deväť — S7 v ňom nie je.
Každá strana uvádza svoje SNIM kódy.

**Zakladajú sa len skupiny, ktorých členstvo je jednoznačné.** Kódy
`SD02`, `PH01`, `ST01.10` a `SN02` zdieľa viac skladieb naraz, takže
priradenie „všetky prvky kódu" by dalo tú istú stenu do S4 aj S5, hoci
ETICS na nej je jedno. Pri ETICS sa to rieši presne — substrát sa
neberie z kódu, ale z **agregácie z fázy 6a**, ktorá hovorí, na ktorej
stene daná krytina naozaj je. S1, S2 a S6 takú oporu nemajú a nechávajú
sa otvorené.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v15.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v16.ifc")

DRY_RUN = True

#: materiál, ktorý Revit dal dutine
DUTINA_MATERIAL = "Výchozí"
DUTINA_KODY = ("PD03.",)
DUTINA_NAZOV = "Vzduchová dutina"

#: skladby, ktorých členstvo je jednoznačné: kódy nezdieľa iná skladba
#: (S3) alebo sa substrát dá vziať z agregácie (ETICS)
SKLADBY = {
    "S3": ("Skladba základovej dosky a podlahy v 1NP",
           ("DZ01", "IH01", "PD02", "ZD02.01"), None),
    "S4": ("Skladba ETICS, plocha výlezu", ("FS01.10",), "agregácia"),
    "S5": ("Skladba ETICS, sokol výlezu", ("FS01.11",), "agregácia"),
    "S8": ("Skladba ETICS, odpadové hospodárstvo (FS01.20, SD02)",
           ("FS01.20",), "agregácia"),
    "S9": ("Skladba ETICS, odpadové hospodárstvo (FS01.12, SN05)",
           ("FS01.12",), "agregácia"),
}

#: skladby, ktoré sa nezakladajú, a dôvod
ODLOZENE = {
    "S1": "zdieľa SD02, PH01 a ST01.10 s S2 a S6",
    "S2": "zdieľa SD02, PH01 a ST01.10 s S1 a S6",
    "S6": "zdieľa PH01 a SD02 s S1 a S2",
}

DESC = ("Skladba podľa D.1.1.09. Členstvo: prvky uvedených SNIM kódov; "
        "pri ETICS je substrát prevzatý z agregácie krytiny do steny.")


def occurrences(model):
    return [e for e in model.by_type("IfcProduct")
            if not e.is_a("IfcFeatureElement") and not e.is_a("IfcTypeObject")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = DRY_RUN and not args.apply

    print("vstup :", args.src)
    print("výstup:", args.dst, "(DRY-RUN)" if dry else "")
    print()

    m = ifcopenshell.open(args.src)
    added: list[str] = []
    removed: list[str] = []
    log: list[str] = []

    occ = occurrences(m)

    # ---- A · #AS vzduchová dutina ---------------------------------------
    dotknute = 0
    materialy = set()
    for e in occ:
        if not (e.Name or "").startswith(DUTINA_KODY):
            continue
        for r in (e.HasAssociations or ()):
            if not r.is_a("IfcRelAssociatesMaterial"):
                continue
            mm = r.RelatingMaterial
            if mm.is_a("IfcMaterialLayerSetUsage"):
                mm = mm.ForLayerSet
            if not mm.is_a("IfcMaterialLayerSet"):
                continue
            for lay in (mm.MaterialLayers or ()):
                if lay.Material is not None and lay.Material.Name == DUTINA_MATERIAL:
                    materialy.add(lay.Material.id())
                    lay.Material = None
                    lay.IsVentilated = "UNKNOWN"
                    lay.Name = DUTINA_NAZOV
                    dotknute += 1
    if dotknute:
        log.append("#AS  %d vrstiev %r → void, IsVentilated=UNKNOWN, meno %r"
                   % (dotknute, DUTINA_MATERIAL, DUTINA_NAZOV))
        # materiál môže osirieť — inv 4 je po fáze 9b na nule, nech tak ostane
        for mid in materialy:
            mat = m.by_id(mid)
            if not m.get_total_inverses(mat):
                m.remove(mat)
                log.append("#AS  osirelý IfcMaterial %r zmazaný" % DUTINA_MATERIAL)
    else:
        log.append("#AS  žiadna vrstva %r — preskočené" % DUTINA_MATERIAL)

    # ---- B · skupiny skladieb -------------------------------------------
    existujuce = {g.Name for g in m.by_type("IfcGroup")}
    owner = occ[0].OwnerHistory
    for kod, (nazov, kody, substrat) in sorted(SKLADBY.items()):
        if kod in existujuce:
            log.append("%-4s už existuje — preskočené" % kod)
            continue
        cleny = [e for e in occ if (e.Name or "").startswith(kody)]
        if not cleny:
            raise SystemExit("STOP: %s nemá ani jeden prvok kódov %s" % (kod, kody))
        if substrat == "agregácia":
            rodicia = []
            for e in cleny:
                for r in (e.Decomposes or ()):
                    rodicia.append(r.RelatingObject)
            if not rodicia:
                raise SystemExit(
                    "STOP: %s — krytiny %s nie sú agregované, substrát sa nedá "
                    "prevziať (fáza 6a ich mala zavesiť na stenu)" % (kod, kody))
            cleny = cleny + rodicia
        cleny = list({e.id(): e for e in cleny}.values())

        g = m.create_entity("IfcGroup", GlobalId=ifcopenshell.guid.new(),
                            OwnerHistory=owner, Name=kod,
                            Description="%s — %s" % (nazov, DESC))
        rel = m.create_entity("IfcRelAssignsToGroup",
                              GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                              RelatedObjects=tuple(cleny), RelatingGroup=g)
        added.extend([g.GlobalId, rel.GlobalId])
        rozpad = collections.Counter(e.is_a().replace("Ifc", "") for e in cleny)
        log.append("%-4s %-46s %3d prvkov %s"
                   % (kod, nazov[:46], len(cleny), dict(rozpad)))

    for kod, dovod in sorted(ODLOZENE.items()):
        log.append("%-4s NEZALOŽENÁ — %s" % (kod, dovod))

    print("ZMENY")
    for line in log:
        print("  " + line)

    siroty = [e for e in m if not m.get_total_inverses(e)
              and not any(e.is_a(w) for w in
                          ("IfcShapeAspect", "IfcMaterialDefinitionRepresentation",
                           "IfcPresentationLayerAssignment", "IfcMapConversion",
                           "IfcRelationship", "IfcRepresentationContext"))]
    if siroty:
        raise SystemExit("STOP: krok vyrobil %d osirelých entít: %s"
                         % (len(siroty), collections.Counter(e.is_a() for e in siroty)))
    print("\n  kontrola inv 4: 0 osirelých")
    print("  GlobalId nových: %d" % len(added))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed)), "added": sorted(set(added))},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
