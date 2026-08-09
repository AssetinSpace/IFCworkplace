"""Fáza 3 — typy a identita.

Register: #AE #O #AK #AA #AF, rozhodnutia 17, 19, 20 z ``AUDIT.md`` §2.

    python src/17_dedup_types.py           # dry-run
    python src/17_dedup_types.py --apply   # zapíše out/ASR_v5.ifc

Čo robí
-------
A  #AE  ``OK01``: 25 ``IfcPlateType`` → jeden; prežívajúci preberá všetkých
        50 ``RepresentationMaps``, occurrences si nechávajú svoj ``IfcMappedItem``
B  #O   125 ``IfcPlate`` typovaných ``OK01`` sa premenúva z ``LP01.*`` na ``OK01``
   #AK  26 ``IfcWindow`` ostáva ``LP01``; typy ``LP01.44`` + ``LP01.69`` → jeden ``LP01``
C  #AA  tretie ``SC01`` (3NP): 2 ``IfcSlab`` → ``SD03``, 2 ``IfcStairFlight``
        → ``SD04``, ``IfcStair`` → typ ``SC01``, 3 ``IfcRailing`` dotypované

Pasce
-----
* ``IfcTypeObject.Types`` je ``SET[0:1]`` — po zlúčení typov sa **musí**
  zlúčiť aj ``IfcRelDefinesByType``, inak by prežívajúci typ mal viac
  vzťahov a invariant 6 padne;
* ``HasPropertySets`` je **priamy atribút**, ``get_inverse`` ho nepokrýva —
  prenáša sa ručne (tu je všade prázdny, kontrola to potvrdí);
* ``RepresentationMaps`` je ``LIST[1:?]``, takže sa nesmie nastaviť na
  prázdny zoznam — pri rušených typoch ide na ``None``;
* occurrences ukazujú cez ``IfcMappedItem.MappingSource`` na konkrétnu mapu.
  Mapy sa **presúvajú** na prežívajúci typ, takže odkazy ostávajú platné
  a brána „0 ``IfcMappedItem`` mimo máp vlastného typu" vychádza.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.guid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import detach_object_from_rels, drop_rel, sweep_orphans  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v4.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v5.ifc")

DRY_RUN = True

#: #AA — prekódovanie a dotypovanie tretieho SC01
SC01_RETYPE = [
    ("IfcSlab", "SC01", "SD03", "SD03"),          # trieda, staré meno, nové meno, typ
    ("IfcStairFlight", "SC01", "SD04", "SD04"),
    ("IfcStair", "SC01", "SC01", "SC01"),
    ("IfcRailing", "ZV01.01", "ZV01.01", "ZV01.01"),
    ("IfcRailing", "ZV01.02", "ZV01.02", "ZV01.02"),
]


def merge_types(model, types, new_name, removed, cand, dead, log, tag):
    """Zlúči rovnomenné typy do jedného. Vráti prežívajúci typ."""
    types = sorted(types, key=lambda t: t.id())
    survivor, others = types[0], types[1:]
    if not others:
        return survivor

    # kontrola, že sa nezlučuje nič, čo sa líši v podstatnom
    differing = {a: {getattr(t, a) for t in types}
                 for a in ("Description", "PredefinedType", "ApplicableOccurrence",
                           "ElementType")}
    for a, vals in differing.items():
        if len(vals) > 1:
            raise SystemExit("STOP: typy %r sa líšia v %s: %s"
                             % (new_name, a, vals))

    # 1 · RepresentationMaps → prežívajúci (occurrences si nechajú IfcMappedItem)
    maps = []
    for t in types:
        maps.extend(t.RepresentationMaps or ())
    survivor.RepresentationMaps = tuple(maps)

    # 2 · HasPropertySets — priamy atribút, get_inverse ho nepokrýva
    psets, seen = list(survivor.HasPropertySets or ()), set()
    seen = {p.id() for p in psets}
    for t in others:
        for p in (t.HasPropertySets or ()):
            if p.id() not in seen:
                psets.append(p)
                seen.add(p.id())
    survivor.HasPropertySets = tuple(psets) or None

    # 3 · occurrences do JEDNÉHO IfcRelDefinesByType (Types : SET[0:1])
    occs, seen_occ = [], set()
    for t in types:
        for r in t.Types:
            for o in r.RelatedObjects:
                if o.id() not in seen_occ:
                    occs.append(o)
                    seen_occ.add(o.id())
    if survivor.Types:
        survivor.Types[0].RelatedObjects = tuple(occs)
    elif occs:
        rel = model.create_entity(
            "IfcRelDefinesByType",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=survivor.OwnerHistory,
            RelatedObjects=tuple(occs),
            RelatingType=survivor,
        )
        del rel

    # 4 · rušené typy: najprv im vyprázdniť mapy (LIST[1:?] → None), potom
    #     odpojiť od všetkých vzťahov a zmazať
    n_maps = len(maps)
    for t in others:
        t.RepresentationMaps = None
        t.HasPropertySets = None
        for r in list(t.Types):
            drop_rel(model, r, removed, cand, dead)
        detach_object_from_rels(model, t, removed, cand, dead)
        removed.append(t.GlobalId)
        dead.add(t.id())
        model.remove(t)

    survivor.Name = new_name
    log.append("%-4s %-8s %d typov → 1, %d RepresentationMaps, %d occurrences"
               % (tag, new_name, len(types), n_maps, len(occs)))
    return survivor


def type_by_name(model, name, cls=None):
    ts = [t for t in model.by_type("IfcTypeProduct")
          if t.Name == name and (cls is None or t.is_a(cls))]
    return ts


def attach_to_type(model, occurrence, typ, added):
    """Priradí occurrence k typu cez jeho ``IfcRelDefinesByType``."""
    if typ.Types:
        rel = typ.Types[0]
        if occurrence.id() not in {o.id() for o in rel.RelatedObjects}:
            rel.RelatedObjects = tuple(rel.RelatedObjects) + (occurrence,)
        return
    rel = model.create_entity(
        "IfcRelDefinesByType",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=typ.OwnerHistory,
        RelatedObjects=(occurrence,),
        RelatingType=typ,
    )
    added.append(rel.GlobalId)


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
    n_types_before = len(m.by_type("IfcTypeObject"))
    removed: list[str] = []
    added: list[str] = []
    cand: list = []
    dead: set = set()
    log: list[str] = []

    # ---- A · #AE OK01 ----------------------------------------------------
    ok = type_by_name(m, "OK01", "IfcPlateType")
    if len(ok) > 1:
        merge_types(m, ok, "OK01", removed, cand, dead, log, "#AE")
    elif ok:
        log.append("#AE  OK01 už zlúčený (%d typ) — preskočené" % len(ok))

    # ---- B · #O 125 IfcPlate LP01.* → OK01 -------------------------------
    ok = type_by_name(m, "OK01", "IfcPlateType")
    renamed = 0
    if ok:
        for o in (ok[0].Types[0].RelatedObjects if ok[0].Types else ()):
            if o.is_a("IfcPlate") and o.Name and o.Name.startswith("LP01"):
                o.Name = "OK01"
                renamed += 1
    if renamed:
        log.append("#O   %d IfcPlate premenovaných z LP01.* na OK01" % renamed)

    # ---- B · #AK typy LP01.44 + LP01.69 → LP01 ---------------------------
    lp = [t for t in m.by_type("IfcWindowType")
          if t.Name in ("LP01.44", "LP01.69", "LP01")]
    if len(lp) > 1:
        merge_types(m, lp, "LP01", removed, cand, dead, log, "#AK")
    elif lp:
        log.append("#AK  LP01 už zlúčený (%d typ) — preskočené" % len(lp))

    # ---- C · #AA tretie SC01 ---------------------------------------------
    done = collections.Counter()
    for cls, old_name, new_name, type_name in SC01_RETYPE:
        ts = type_by_name(m, type_name)
        if not ts:
            raise SystemExit("STOP: typ %s neexistuje" % type_name)
        typ = ts[0]
        for e in list(m.by_type(cls)):
            if e.Name != old_name or e.IsTypedBy:
                continue
            if e.is_a() != cls:
                continue
            if new_name != old_name:
                e.Name = new_name
            attach_to_type(m, e, typ, added)
            done[(cls, old_name, new_name, type_name)] += 1
    for k, n in sorted(done.items(), key=lambda kv: str(kv[0])):
        log.append("#AA  %-16s %-8s → %-8s typ %-8s %d" % (k[0], k[1], k[2], k[3], n))

    swept = sweep_orphans(m, cand, removed, dead)
    if swept:
        log.append("     zametené osirelé entity: %s" % dict(swept))

    # ---- kontrola brány 3 ------------------------------------------------
    n_types = len(m.by_type("IfcTypeObject"))
    multi = [t.Name for t in m.by_type("IfcTypeObject") if len(t.Types) > 1]
    untyped = [e for e in m.by_type("IfcElement")
               if not e.IsTypedBy and not e.is_a("IfcFeatureElement")]
    bad_maps = 0
    for e in m.by_type("IfcProduct"):
        if not e.Representation:
            continue
        t = e.IsTypedBy[0].RelatingType if e.IsTypedBy else None
        own = {rm.id() for rm in (t.RepresentationMaps or ())} if t else set()
        for rep in e.Representation.Representations:
            for it in rep.Items:
                if it.is_a("IfcMappedItem") and it.MappingSource.id() not in own:
                    bad_maps += 1

    print("ZMENY")
    for line in log:
        print("  " + line)
    if not log:
        print("  (žiadna zmena — model je už v cieľovom stave)")
    print("\nKONTROLA BRÁNY 3")
    print("  IfcTypeObject          : %d → %d   (očakávané ~124)"
          % (n_types_before, n_types))
    print("  typov s >1 IfcRelDefinesByType: %d   (Types:SET[0:1], očakávané 0)"
          % len(multi))
    print("  IfcMappedItem mimo máp vlastného typu: %d   (očakávané 0)" % bad_maps)
    print("  netypovaných occurrences: %d %s"
          % (len(untyped), dict(collections.Counter((e.is_a(), e.Name) for e in untyped))))
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
