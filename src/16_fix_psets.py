"""Fáza 2 — psety a stratené dáta.

Register: #A #B #E #AH #AI, rozhodnutie 27 z ``AUDIT.md`` §2.

    python src/16_fix_psets.py           # dry-run
    python src/16_fix_psets.py --apply   # zapíše out/ASR_v4.ifc

Čo robí
-------
A   #A   ``Status = NEW`` späť na 28 ``IfcCovering`` do ``Pset_CoveringCommon``
         (``FS03.01`` 9, ``ST01.32`` 8, ``FS01.10`` 4, ``FS01.11`` 4, ``FS01.12`` 3)
B   #B   17 ``IfcSlab``: ``Pset_WallCommon`` → ``Pset_SlabCommon``
B'  —    4 ``IfcCovering`` ``IH01.01``: ``Pset_WallCommon`` → ``Pset_CoveringCommon``
C   #E   10 ``IfcSpatialZone``: ``Pset_SpaceCommon`` → ``Pset_SpatialZoneCommon``
D   #27  zmazať 117 occurrence ``IfcMaterialConstituentSet`` (91 ``IfcDoor``,
         26 ``IfcWindow``); terminály (41) a zábradlia (4) ostávajú

Prečo #B presúva a nemaže
-------------------------
Tých 17 dosiek je **jediný nositeľ ``Status`` medzi doskami**. Keby sa
``Pset_WallCommon`` len zmazal, ``Status`` by zmizol a brána „209 prvkov"
by nevyšla (181 − 17 + 28 = 192). Zároveň by to bolo v priamom rozpore
s #A, ktoré stratený ``Status`` obnovuje. Preto sa pset **premenuje** na
správny a zahodia sa z neho len tie property, ktoré cieľová šablóna nepozná.

Šablóny sa čítajú z ``ifcopenshell.util.pset`` pre IFC4X3, nie z pamäti:

===================  ==========================================  ==================
zdroj                prejde                                      zahodí sa
===================  ==========================================  ==================
Pset_SlabCommon      ``IsExternal``, ``LoadBearing``, ``Status``  ``ExtendToStructure``
Pset_CoveringCommon  ``IsExternal``, ``Status``                   ``ExtendToStructure``, ``LoadBearing``
Pset_SpatialZoneCommon  ``IsExternal``                            —
===================  ==========================================  ==================

Zahadzujú sa len hodnoty ``False`` (Revit default). ``LoadBearing = True``
na doskách sa zachováva, lebo ``Pset_SlabCommon`` ho pozná.

B' nie je v registri — tú vadu zaviedla **fáza 1a**, keď ``IH01.01`` zmenila
z ``IfcWall`` na ``IfcCovering`` aj s jeho ``Pset_WallCommon``. Rovnaký
vzor ako #B, opravuje sa tu.

Pasca
-----
Revit **zdieľa ``IfcProperty`` medzi psetmi** — odstránenie jednej môže
vyprázdniť aj iný pset. Preto iteratívny sweep cez ``ifcutil.sweep_orphans``,
ktorý po každom kole prepočíta ``get_total_inverses``. ``HasProperties`` je
``SET[1:?]``, takže prázdny pset sa musí zmazať celý.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.util.pset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import drop_rel, psets_of, sweep_orphans  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v3.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v4.ifc")

DRY_RUN = True

#: #A — kódy, ktorým sa vracia Status, s očakávaným počtom
STATUS_TARGETS = {"FS03.01": 9, "ST01.32": 8, "FS01.10": 4, "FS01.11": 4,
                  "FS01.12": 3}
STATUS_VALUE = "NEW"

#: (trieda occurrences, starý pset, nový pset) — #B, B', #E
PSET_MOVES = [
    ("IfcSlab", "Pset_WallCommon", "Pset_SlabCommon", "#B"),
    ("IfcCovering", "Pset_WallCommon", "Pset_CoveringCommon", "#B'"),
    ("IfcSpatialZone", "Pset_SpaceCommon", "Pset_SpatialZoneCommon", "#E"),
]

#: #27 — triedy, ktorým sa occurrence konštituentný set maže
CONSTITUENT_DROP = ("IfcDoor", "IfcWindow")


def template_props(name):
    """Množina property mien, ktoré daná šablóna pozná (IFC4X3)."""
    tpl = ifcopenshell.util.pset.get_template("IFC4X3").get_by_name(name)
    if tpl is None:
        raise SystemExit("STOP: šablóna %s neexistuje" % name)
    return {p.Name for p in tpl.HasPropertyTemplates}


def make_status(model, value=STATUS_VALUE):
    """Nová ``IfcPropertyEnumeratedValue('Status', …, (IfcLabel(value)))``.

    Kopíruje tvar, ktorý už v modeli je — bez ``EnumerationReference``.
    """
    return model.create_entity(
        "IfcPropertyEnumeratedValue",
        Name="Status",
        EnumerationValues=(model.create_entity("IfcLabel", value),),
    )


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
    removed: list[str] = []
    added: list[str] = []
    dead: set = set()
    cand: list = []
    log: list[str] = []

    # ---- A · #A Status späť na 28 IfcCovering ---------------------------
    found = collections.Counter()
    for e in list(m.by_type("IfcCovering")):
        if e.Name not in STATUS_TARGETS:
            continue
        sets = [(r, d) for r, d in psets_of(e) if d.Name == "Pset_CoveringCommon"]
        if not sets:
            raise SystemExit("STOP: %s %s nemá Pset_CoveringCommon"
                             % (e.Name, e.GlobalId))
        rel, d = sets[0]
        if any(p.Name == "Status" for p in d.HasProperties):
            continue                                   # idempotencia
        if m.get_total_inverses(d) != 1 or len(rel.RelatedObjects) != 1:
            raise SystemExit("STOP: Pset_CoveringCommon #%d je zdieľaný — "
                             "doplnenie Status by zasiahlo aj iné prvky" % d.id())
        d.HasProperties = tuple(d.HasProperties) + (make_status(m),)
        found[e.Name] += 1
    if found:
        log.append("#A   Status=%s doplnený: %s = %d prvkov"
                   % (STATUS_VALUE, dict(found), sum(found.values())))
        if dict(found) != STATUS_TARGETS:
            raise SystemExit("STOP: očakávané %s, nájdené %s"
                             % (STATUS_TARGETS, dict(found)))

    # ---- B, B', C · presun psetov ---------------------------------------
    for cls, old, new, tag in PSET_MOVES:
        keep = template_props(new)
        moved = collections.Counter()
        dropped = collections.Counter()
        for e in list(m.by_type(cls)):
            for rel, d in psets_of(e):
                if d.Name != old:
                    continue
                if m.get_total_inverses(d) != 1 or len(rel.RelatedObjects) != 1:
                    raise SystemExit(
                        "STOP: %s #%d je zdieľaný, premenovanie by zasiahlo "
                        "aj iné prvky" % (old, d.id()))
                loses = [p for p in d.HasProperties if p.Name not in keep]
                d.Name = new
                if loses:
                    d.HasProperties = tuple(p for p in d.HasProperties
                                            if p.Name in keep)
                    cand.extend(p.id() for p in loses)
                    for p in loses:
                        dropped[p.Name] += 1
                moved[e.Name or cls] += 1
        if moved:
            log.append("%-4s %s → %s: %d prvkov %s"
                       % (tag, old, new, sum(moved.values()), dict(moved)))
            if dropped:
                log.append("     zahodené property mimo šablóny: %s" % dict(dropped))

    # ---- D · #27 occurrence konštituentné sety --------------------------
    n_occ = collections.Counter()
    for cls in CONSTITUENT_DROP:
        for e in list(m.by_type(cls)):
            for rid in [r.id() for r in (e.HasAssociations or ())]:
                if rid in dead:
                    continue
                rel = m.by_id(rid)
                if not rel.is_a("IfcRelAssociatesMaterial"):
                    continue
                if not rel.RelatingMaterial.is_a("IfcMaterialConstituentSet"):
                    continue
                t = e.IsTypedBy[0].RelatingType if e.IsTypedBy else None
                ok = any(r.is_a("IfcRelAssociatesMaterial")
                         and r.RelatingMaterial.is_a("IfcMaterialConstituentSet")
                         for r in (t.HasAssociations or ())) if t else False
                if not ok:
                    raise SystemExit(
                        "STOP: %s %s nemá funkčný typový konštituentný set — "
                        "zmazaním occurrence setu by prišiel o materiál"
                        % (cls, e.GlobalId))
                rest = tuple(x for x in rel.RelatedObjects if x.id() != e.id())
                if rest:
                    rel.RelatedObjects = rest
                else:
                    drop_rel(m, rel, removed, cand, dead)
                n_occ[cls] += 1
    if n_occ:
        log.append("#27  zmazaných occurrence IfcMaterialConstituentSet: %d %s"
                   % (sum(n_occ.values()), dict(n_occ)))

    # ---- sweep ----------------------------------------------------------
    swept = sweep_orphans(m, cand, removed, dead)
    if swept:
        log.append("     zametené osirelé entity: %s" % dict(swept))

    # ---- kontrola brány 2 ------------------------------------------------
    n_status = sum(
        1 for e in m.by_type("IfcObject")
        for _, d in psets_of(e)
        if d.is_a("IfcPropertySet")
        and any(p.Name == "Status" for p in d.HasProperties)
    )
    aspects = {a.Name for a in m.by_type("IfcShapeAspect") if a.Name}
    orphan_const = 0
    for r in m.by_type("IfcRelAssociatesMaterial"):
        if not r.RelatingMaterial.is_a("IfcMaterialConstituentSet"):
            continue
        if all(o.is_a("IfcTypeObject") for o in r.RelatedObjects):
            continue                                   # typová úroveň je OK
        for c in r.RelatingMaterial.MaterialConstituents:
            if c.Name not in aspects:
                orphan_const += 1

    print("ZMENY")
    for line in log:
        print("  " + line)
    if not log:
        print("  (žiadna zmena — model je už v cieľovom stave)")
    print("\nKONTROLA BRÁNY 2")
    print("  prvkov so Status : %d   (očakávané 209)" % n_status)
    print("  IfcMaterialConstituent bez IfcShapeAspect na occurrence: %d   "
          "(očakávané 0)" % orphan_const)
    print("  GlobalId zrušených: %d, nových: %d" % (len(removed), len(added)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(removed), "added": sorted(added)},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
