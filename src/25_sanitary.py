"""Fáza 10 — zariaďovacie predmety a ich zoskupenia.

Register: pôvodný krok 13, rozsah podľa ``AUDIT.md`` §7.

    python src/25_sanitary.py           # dry-run
    python src/25_sanitary.py --apply   # zapíše out/ASR_v13.ifc

Čo robí
-------
Prekvalifikuje 69 ``IfcFlowTerminal`` na konkrétne podtypy, ktoré
``PredefinedType`` v IFC4X3 majú, a zoskupí ich do ``IfcSystem``.

Prečo systém a nie sieť
-----------------------
§7: *„v modeli nie je ani jeden kus potrubia… systémy budú zoskupením
zariadení, nie sieťou, a treba to tak pomenovať."* Model má 51 portov
a **0 ``IfcFlowSegment``**, takže ``IfcDistributionSystem`` by sľuboval
sieť, ktorá neexistuje. Použije sa preto ``IfcSystem`` a názov to hovorí
priamo.

Opora pre ``PredefinedType``
----------------------------
Mapovanie WC a ``OV04`` je z §7. Typ pre ``OV01.01`` tam určený nebol,
rozhodla ho definícia zo spec proti legende výkresu:

* výkres: *„Vpusť podlahová, DN110, **krytá pochôdznou mriežkou**"*
* IFC4.3 ``GULLYTRAP``: *„Pipe fitting or assembly of fittings that
  receives surface water or waste water; **fitted with a grating** or
  sealed cover that discharges water through a trap."*

``FLOORTRAP`` je definovaný cez zápachovú uzáveru a ``FLOORWASTE`` cez
odvedenie do samostatnej uzávery — ani jeden nespomína mriežku, ktorú
výkres uvádza ako určujúcu.

Pasca
-----
``ifcopenshell.api.root.reassign_class`` kaskádovo prepíše zdieľaný typ.
Používa sa **výhradne** ``util.schema.reassign_class`` a prvok sa od typu
pred prepisom odpojí — ten istý postup ako vo fáze 1. ``id()`` sa
zachováva, takže ``GlobalId`` sa nemenia a invariant 3 nehlási nič.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v12.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v13.ifc")

DRY_RUN = True

#: názov typu → (trieda occurrence, trieda typu, PredefinedType, čakaný počet)
MAP = {
    "WC01":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "URINAL", 5),
    "WC02":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "TOILETPAN", 6),
    "WC04":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "TOILETPAN", 14),
    "WC03":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "WASHHANDBASIN", 6),
    "WC05":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "WASHHANDBASIN", 12),
    "WC07":    ("IfcSanitaryTerminal", "IfcSanitaryTerminalType", "SINK", 3),
    "OV01.01": ("IfcWasteTerminal", "IfcWasteTerminalType", "GULLYTRAP", 5),
    "OV04.01": ("IfcWasteTerminal", "IfcWasteTerminalType", "ROOFDRAIN", 5),
    "OV04.02": ("IfcWasteTerminal", "IfcWasteTerminalType", "ROOFDRAIN", 4),
    "OV04.04": ("IfcWasteTerminal", "IfcWasteTerminalType", "ROOFDRAIN", 5),
    "OV04.05": ("IfcWasteTerminal", "IfcWasteTerminalType", "ROOFDRAIN", 4),
}

#: súčty, ktoré §7 uvádza — brána proti tichému posunu
EXPECTED = {"URINAL": 5, "TOILETPAN": 20, "WASHHANDBASIN": 18, "SINK": 3,
            "GULLYTRAP": 5, "ROOFDRAIN": 18}

#: zoskupenia; názov hovorí, že ide o zoskupenie zariadení, nie o sieť
SYSTEMS = [
    ("Zoskupenie zariadení — zdravotechnika",
     lambda n: n.startswith("WC")),
    ("Zoskupenie zariadení — strešné vpuste",
     lambda n: n.startswith("OV04")),
    ("Zoskupenie zariadení — podlahové vpuste",
     lambda n: n.startswith("OV01")),
]

SYS_DESC = ("Zoskupenie zariaďovacích predmetov, nie distribučná sieť — "
            "model neobsahuje ani jeden IfcFlowSegment.")


def reassign_with_type(model, occurrences, type_entity, new_occ, new_type):
    """Prepíše triedu occurrences aj typu; vzor z ``14_fix_classes.py``."""
    occ_ids = [o.id() for o in occurrences]
    type_id = type_entity.id() if type_entity is not None else None

    rel, saved = None, []
    if type_entity is not None and type_entity.Types:
        rel = type_entity.Types[0]
        saved = [o.id() for o in rel.RelatedObjects]
        cudzie = set(saved) - set(occ_ids)
        if cudzie:
            raise SystemExit("STOP: typ %r je zdieľaný aj mimo rozsahu: %s"
                             % (type_entity.Name, sorted(cudzie)))
        rel.RelatedObjects = ()          # odpojiť pred zmenou triedy

    for oid in occ_ids:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(oid), new_occ)
    if type_id is not None:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(type_id), new_type)
    if rel is not None:
        model.by_id(rel.id()).RelatedObjects = tuple(model.by_id(i) for i in saved)

    return ([model.by_id(i) for i in occ_ids],
            model.by_id(type_id) if type_id is not None else None)


# ==========================================================================


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
    log: list[str] = []

    terminals = list(m.by_type("IfcFlowTerminal"))
    if not terminals:
        print("žiadny IfcFlowTerminal — skript je idempotentný, končí")
        return 0

    segmenty = len(m.by_type("IfcFlowSegment"))
    if segmenty:
        raise SystemExit("STOP: model má %d IfcFlowSegment — predpoklad §7 "
                         "o neexistujúcej sieti už neplatí" % segmenty)

    # ---- kontrola rozsahu pred zásahom ----------------------------------
    # Držia sa **id()**, nie handle: po prvom ``reassign_class`` sa staré
    # handle zneplatnia a čítanie z nich zhodí proces (viď ``ifcutil``).
    podla_typu = collections.defaultdict(list)
    for e in terminals:
        t = e.IsTypedBy[0].RelatingType if e.IsTypedBy else None
        podla_typu[t.Name if t is not None else None].append(e.id())
    neznamy = sorted(set(podla_typu) - set(MAP))
    if neznamy:
        raise SystemExit("STOP: terminály s typom mimo mapovania §7: %s" % neznamy)
    for nazov, (_, _, _, ks) in MAP.items():
        mam = len(podla_typu.get(nazov, []))
        if mam != ks:
            raise SystemExit("STOP: %s má %d occurrences, §7 čaká %d"
                             % (nazov, mam, ks))

    # OwnerHistory sa musí prečítať **pred** prepisom — potom je handle
    # neplatný a čítanie z neho zhodí proces, nie vyhodí výnimku.
    owner = terminals[0].OwnerHistory

    # ---- prekvalifikovanie ----------------------------------------------
    hotove = collections.Counter()
    for nazov, (occ_cls, typ_cls, pdt, _) in MAP.items():
        occs = [m.by_id(i) for i in podla_typu[nazov]]
        t = occs[0].IsTypedBy[0].RelatingType
        novy_occ, novy_typ = reassign_with_type(m, occs, t, occ_cls, typ_cls)
        for o in novy_occ:
            o.PredefinedType = pdt
        if novy_typ is not None:
            novy_typ.PredefinedType = pdt
        hotove[pdt] += len(novy_occ)
        log.append("     %-8s → %-20s %-14s %2d ks"
                   % (nazov, occ_cls, pdt, len(novy_occ)))

    if dict(hotove) != EXPECTED:
        raise SystemExit("STOP: súčty %s nesedia s §7 %s" % (dict(hotove), EXPECTED))
    log.append("     súčty sedia s §7: %s" % dict(hotove))

    # ---- zoskupenia -------------------------------------------------------
    budovy = m.by_type("IfcBuilding")
    for nazov, patri in SYSTEMS:
        cleny = [e for e in (m.by_type("IfcSanitaryTerminal")
                             + m.by_type("IfcWasteTerminal"))
                 if patri(e.Name or "")]
        if not cleny:
            continue
        sys = m.create_entity("IfcSystem", GlobalId=ifcopenshell.guid.new(),
                              OwnerHistory=owner, Name=nazov, Description=SYS_DESC)
        rel = m.create_entity("IfcRelAssignsToGroup",
                              GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                              RelatedObjects=tuple(cleny), RelatingGroup=sys)
        added.extend([sys.GlobalId, rel.GlobalId])
        if budovy:
            srv = m.create_entity("IfcRelServicesBuildings",
                                  GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                                  RelatingSystem=sys, RelatedBuildings=tuple(budovy))
            added.append(srv.GlobalId)
        log.append("     IfcSystem %-42r %2d zariadení" % (nazov, len(cleny)))

    print("ZMENY")
    for line in log:
        print("  " + line)

    # by_type zahŕňa podtypy, takže sa musí porovnať presná trieda —
    # inak by kontrola počítala vlastný výsledok
    zvysok = sum(1 for e in m.by_type("IfcFlowTerminal")
                 if e.is_a() == "IfcFlowTerminal")
    if zvysok:
        raise SystemExit("STOP: %d IfcFlowTerminal zostalo neprekvalifikovaných"
                         % zvysok)
    print("\n  IfcFlowTerminal po behu: 0")
    print("  IfcSanitaryTerminal %d, IfcWasteTerminal %d"
          % (len(m.by_type("IfcSanitaryTerminal")), len(m.by_type("IfcWasteTerminal"))))
    print("  GlobalId nových: %d (prekvalifikovanie GUID nemení)" % len(added))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(added)}, fh,
                  ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
