"""Fáza 1b — strecha a atika.

Register: #T #V #AO, rozhodnutia 9, 10, 11 z ``AUDIT.md`` §2.

    python src/15_fix_roof_assembly.py           # dry-run
    python src/15_fix_roof_assembly.py --apply   # zapíše out/ASR_v3.ifc

Delenie vrstiev
---------------
Rozhodnutie Samuela po bráne 1a: **delí sa podľa orientácie, nie podľa kódu.**

* do agregácie **atiky** idú zvislé vrstvy, OSB doska a oplechovanie:
  ``ST01.32`` (8, zvislý pás na vnútornom líci) + ``ST01.31`` (8, OSB)
  + ``KV01`` (2, oplechovanie) = 18 dielov v 8 ``IfcRelAggregates``
* do **strešných súvrství** idú vodorovné vrstvy ``ST01``:
  ``ST01.10`` + ``.20`` + ``.21`` + ``.30`` = 76 prvkov

Tým sa ruší číslo „73/19" z rozhodnutia 11 — bolo spočítané nad všetkými
``ST01`` ešte pred vyčlenením atiky a ``Decomposes : SET[0:1]`` nedovolí,
aby bol prvok v dvoch agregáciách naraz. Nové čísla: **4NP 65, 5NP 10**.

Jedna ``ST01.10`` leží v 3NP (z 13250–13454, tesne pod doskou 4NP).
Nechávame ju tak — je to #G a patrí do fázy 6.

Pasce
-----
* agregujúci ``IfcRoof`` **nesmie** mať ``Body`` reprezentáciu → nové obaly
  vznikajú bez ``Representation`` aj bez ``ObjectPlacement``;
* 36 rušených obalov nemá reprezentáciu vôbec a ich ``IfcLocalPlacement``
  drží reťaz dosky (``PlacementRelTo``, 2 inverzy) — placement sa preto
  **nemaže**, inak by sa rozbila geometria dosky;
* obaly sú netypované, takže zrušením neosirie žiadny typ;
* atribúty sa čítajú pred ``model.remove()``, iteruje sa cez ``list(...)``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import ifcopenshell.util.schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v3_a.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v3.ifc")
ALLOW = os.path.join(ROOT, "out", "ASR_v3.allowlist.json")

DRY_RUN = True

#: vodorovné vrstvy → strešné súvrstvie, s cieľovým PredefinedType
ROOF_LAYERS = {
    "ST01.10": "INSULATION",
    "ST01.20": "ROOFING",
    "ST01.21": "ROOFING",
    "ST01.30": "INSULATION",
}
#: zvislé vrstvy + OSB + oplechovanie → atika
ATIKA_LAYERS = {
    "ST01.31": "TOPPING",
    "ST01.32": "INSULATION",
    "KV01": "COPING",
}
ATIKA_WALL = "SN02.01"
ROOF_STOREYS = ("4NP", "5NP")


# --------------------------------------------------------------------------


def bboxes(model, elements):
    """``{GlobalId: (xmin,ymin,zmin,xmax,ymax,zmax)}`` v mm, cez geom.iterator."""
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    threads = max(1, (os.cpu_count() or 2) - 1)
    it = ifcopenshell.geom.iterator(s, model, threads, include=list(elements))
    out = {}
    if not it.initialize():
        return out
    while True:
        sh = it.get()
        v = sh.geometry.verts
        if v:
            xs, ys, zs = v[0::3], v[1::3], v[2::3]
            out[sh.guid] = (min(xs) * 1000, min(ys) * 1000, min(zs) * 1000,
                            max(xs) * 1000, max(ys) * 1000, max(zs) * 1000)
        if not it.next():
            break
    return out


def storey_of(e):
    for r in getattr(e, "ContainedInStructure", ()) or ():
        return r.RelatingStructure
    for r in getattr(e, "Decomposes", ()) or ():
        return storey_of(r.RelatingObject)
    return None


#: Tolerancia pre párovanie vrstvy k stene, v mm.
#: Zvislý pás ``ST01.32`` sa steny **dotýka**, neprekrýva ju — napr. pás
#: ``y 12879…12959`` a stena ``y 12959…13109`` majú prienik presne 0.
#: Bez nafúknutia bboxu by párovanie zlyhalo. 100 mm bezpečne premostí dotyk
#: a zároveň nechá vyhrať tú stenu, s ktorou vrstva zdieľa dlhú hranu.
TOL_XY = 100.0


def xy_overlap(a, b, tol=TOL_XY):
    ox = min(a[3] + tol, b[3] + tol) - max(a[0] - tol, b[0] - tol)
    oy = min(a[4] + tol, b[4] + tol) - max(a[1] - tol, b[1] - tol)
    return ox * oy if ox > 0 and oy > 0 else 0.0


def detach_from_containment(model, element, removed: list) -> None:
    """Odoberie prvok z ``IfcRelContainedInSpatialStructure``.

    Ak rel ostane prázdny, zmaže sa celý — ``RelatedElements`` je
    ``SET[1:?]`` a prázdny by porušil invariant 5.
    """
    eid = element.id()
    for rid in [r.id() for r in (getattr(element, "ContainedInStructure", ()) or ())]:
        rel = model.by_id(rid)
        rest = tuple(x for x in rel.RelatedElements if x.id() != eid)
        if rest:
            rel.RelatedElements = rest
        else:
            removed.append(rel.GlobalId)
            model.remove(rel)


def _drop_rel(model, rel, removed: list, candidates: list, dead: set) -> None:
    """Zmaže vzťah a zapamätá jeho ``Relating*`` definície na zametenie."""
    rid = rel.id()
    if rid in dead:
        return
    for i in range(len(rel)):
        if rel.attribute_name(i).startswith("Relating"):
            v = rel[i]
            # produkty nezametáme — tie sa mažú explicitne
            if isinstance(v, ifcopenshell.entity_instance) and not v.is_a(
                "IfcObjectDefinition"
            ):
                candidates.append(v.id())
    gid = getattr(rel, "GlobalId", None)
    if isinstance(gid, str):
        removed.append(gid)
    dead.add(rid)
    model.remove(rel)


def detach_object_from_rels(model, element, removed: list, candidates: list,
                            dead: set) -> None:
    """Odpojí prvok od **všetkých** vzťahov pred jeho zmazaním.

    Bez tohto zostanú po zmazaní obalu prázdne ``IfcRelDefinesByProperties``
    (36 obalov × 4 = 144) a invariant 5 padne.
    """
    eid = element.id()
    # Handle z get_inverse sa po prvom model.remove() zneplatnia a siahnutie
    # na ne zhodí proces. Preto sa najprv odloží zoznam id a entita sa
    # v každom kole vytiahne nanovo.
    for rid in [r.id() for r in model.get_inverse(element)]:
        if rid in dead:
            continue
        rel = model.by_id(rid)
        if not rel.is_a("IfcRelationship"):
            continue
        # prvok je celok / kontajner → vzťah ide preč celý
        whole = False
        for a in ("RelatingObject", "RelatingStructure"):
            v = getattr(rel, a, None)
            if v is not None and v.id() == eid:
                whole = True
        if whole:
            _drop_rel(model, rel, removed, candidates, dead)
            continue
        for attr in ("RelatedObjects", "RelatedElements", "RelatedDefinitions"):
            cur = getattr(rel, attr, None)
            if cur is None:
                continue
            rest = tuple(x for x in cur if x.id() != eid)
            if len(rest) == len(cur):
                continue
            if rest:
                setattr(rel, attr, rest)
            else:
                _drop_rel(model, rel, removed, candidates, dead)
                break   # entita je preč — ďalší atribút by sa čítal z mŕtveho
                        # handle a zhodil by proces (SIGSEGV)


def sweep_orphans(model, candidate_ids, removed: list, dead: set):
    """Iteratívne zmaže definície, na ktoré už nič neodkazuje.

    Iteratívne zámerne: Revit **zdieľa `IfcProperty` medzi psetmi** — zo 72
    property v rušených psetoch ich 36 patrí aj inam. Zmazanie psetu môže
    property osirotiť, ale len tú nezdieľanú; preto sa po každom kole
    prepočíta ``get_total_inverses`` a zdieľané ostávajú.

    Pracuje sa s ``id()``, nie s handle — handle zmazanej entity je v
    ifcopenshell neplatný a siahnutie naň zhodí proces (SIGSEGV).
    """
    done = collections.Counter()
    queue = [i for i in candidate_ids if i not in dead]
    while queue:
        nxt = []
        for eid in queue:
            if eid in dead:
                continue
            e = model.by_id(eid)
            if model.get_total_inverses(e):
                continue
            children = []
            for attr in ("HasProperties", "Quantities"):
                children.extend(x.id() for x in (getattr(e, attr, None) or ()))
            done[e.is_a()] += 1
            gid = getattr(e, "GlobalId", None)
            if isinstance(gid, str):
                removed.append(gid)
            dead.add(eid)
            model.remove(e)
            nxt.extend(children)
        queue = [i for i in nxt if i not in dead]
    return done


def contain_in(model, storey, element, added: list):
    """Pridá prvok do existujúceho kontajnmentu podlažia."""
    for rel in storey.ContainsElements:
        if element.id() not in {x.id() for x in rel.RelatedElements}:
            rel.RelatedElements = tuple(rel.RelatedElements) + (element,)
        return rel
    rel = model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=storey.OwnerHistory,
        RelatedElements=(element,),
        RelatingStructure=storey,
    )
    added.append(rel.GlobalId)
    return rel


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
    removed_guids: list[str] = []
    added_guids: list[str] = []
    log: list[str] = []

    # ---- 0 · snapshot pred akoukoľvek mutáciou --------------------------
    all_layers = [e for e in list(m.by_type("IfcElement"))
                  if e.Name in set(ROOF_LAYERS) | set(ATIKA_LAYERS)
                  and not e.is_a("IfcFeatureElement")]
    layer_storey = {e.GlobalId: (storey_of(e).Name if storey_of(e) else None)
                    for e in all_layers}
    walls = [e for e in list(m.by_type("IfcWall")) if e.Name == ATIKA_WALL]

    # ---- 1 · #V zrušiť 36 prázdnych obalov ------------------------------
    # #V hovorí „prázdne obaly 1:1 nad IfcSlab": bez reprezentácie a s práve
    # jednou časťou. Podmienka musí vylúčiť nové agregujúce FLAT_ROOF, inak
    # by ich druhý beh zmazal a znova vytvoril — a skript by nebol idempotentný.
    wrappers = []
    for r in list(m.by_type("IfcRoof")):
        parts = [p for rel in r.IsDecomposedBy for p in rel.RelatedObjects]
        if len(parts) == 1 and r.PredefinedType != "FLAT_ROOF":
            wrappers.append(r)
    n_wrap = 0
    sweep_candidates: list = []
    dead: set = set()
    for w in wrappers:
        if w.Representation is not None:
            raise SystemExit("STOP: obal #%d má reprezentáciu, nemazem" % w.id())
        detach_object_from_rels(m, w, removed_guids, sweep_candidates, dead)
        removed_guids.append(w.GlobalId)
        dead.add(w.id())
        m.remove(w)          # placement zostáva — drží reťaz dosky
        n_wrap += 1
    if n_wrap:
        swept = sweep_orphans(m, sweep_candidates, removed_guids, dead)
        log.append("#V   zrušených prázdnych IfcRoof obalov: %d" % n_wrap)
        if swept:
            log.append("#V   zametené osirelé definície: %s" % dict(swept))

    # ---- 2 · #T vrstvy ST01 → IfcCovering --------------------------------
    targets = dict(ROOF_LAYERS)
    targets.update(ATIKA_LAYERS)
    changed = collections.Counter()

    # id/meno/trieda sa vyčítajú dopredu — reassign_class entitu znovu vytvorí,
    # takže staré handle by boli neplatné
    occ = [(e.id(), e.Name, e.is_a()) for e in m.by_type("IfcElement")
           if e.Name in targets and not e.is_a("IfcFeatureElement")]
    for eid, name, old in occ:
        want = targets[name]
        if old != "IfcCovering":
            ifcopenshell.util.schema.reassign_class(m, m.by_id(eid), "IfcCovering")
            changed[(name, old, want)] += 1
        e = m.by_id(eid)
        if e.PredefinedType != want:
            e.PredefinedType = want

    typ = [(t.id(), t.Name, t.is_a()) for t in m.by_type("IfcTypeProduct")
           if t.is_a() in ("IfcRoofType", "IfcSlabType") and t.Name]
    for tid, name, old in typ:
        want = targets.get(name.rstrip("ab"))   # ST01.10a → ST01.10
        if want is None:
            continue
        ifcopenshell.util.schema.reassign_class(m, m.by_id(tid), "IfcCoveringType")
        m.by_id(tid).PredefinedType = want
        changed[(name, old, want)] += 1

    for (name, old, want), n in sorted(changed.items()):
        log.append("#T   %-9s %-13s → %-16s %-11s %3d"
                   % (name, old, "IfcCoveringType" if old.endswith("Type")
                      else "IfcCovering", want, n))

    # ---- 3 · dve nové IfcRoof / FLAT_ROOF --------------------------------
    existing = [r for r in m.by_type("IfcRoof") if r.PredefinedType == "FLAT_ROOF"]
    storeys = {s.Name: s for s in m.by_type("IfcBuildingStorey")}
    roofs = {}
    if existing:
        for r in existing:
            st = storey_of(r)
            roofs[st.Name if st else None] = r
        log.append("#11  IfcRoof/FLAT_ROOF už existujú (%d) — preskočené" % len(existing))
    else:
        for name in ROOF_STOREYS:
            st = storeys[name]
            r = m.create_entity(
                "IfcRoof",
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=st.OwnerHistory,
                Name="ST01",
                Description="Strešné súvrstvie %s" % name,
                ObjectPlacement=None,      # bez vlastnej geometrie
                Representation=None,       # agregujúci obal NESMIE mať Body
                PredefinedType="FLAT_ROOF",
            )
            added_guids.append(r.GlobalId)
            contain_in(m, st, r, added_guids)
            roofs[name] = r
            log.append("#11  nová IfcRoof/FLAT_ROOF 'ST01' v %s" % name)

    # ---- 4 · agregácia vodorovných vrstiev do striech ---------------------
    for name in ROOF_STOREYS:
        parts = [e for e in list(m.by_type("IfcCovering"))
                 if e.Name in ROOF_LAYERS and layer_storey.get(e.GlobalId) == name
                 and not e.Decomposes]
        if not parts:
            continue
        rel = m.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=roofs[name].OwnerHistory,
            RelatingObject=roofs[name],
            RelatedObjects=tuple(parts),
        )
        added_guids.append(rel.GlobalId)
        for p in parts:
            detach_from_containment(m, p, removed_guids)
        log.append("#11  %s: strecha agreguje %d vodorovných vrstiev %s"
                   % (name, len(parts),
                      dict(collections.Counter(p.Name for p in parts))))

    stray = [e for e in m.by_type("IfcCovering")
             if e.Name in ROOF_LAYERS and not e.Decomposes]
    if stray:
        log.append("#G   mimo strechy ostáva %d vrstva: %s (podlažie %s) — fáza 6"
                   % (len(stray), stray[0].Name, layer_storey.get(stray[0].GlobalId)))

    # ---- 5 · #9 atika: 8× IfcRelAggregates -------------------------------
    if walls and not any(w.IsDecomposedBy for w in walls):
        atika_parts = [e for e in list(m.by_type("IfcCovering"))
                       if e.Name in ATIKA_LAYERS and not e.Decomposes]
        box = bboxes(m, walls + atika_parts)
        assign = collections.defaultdict(list)
        for p in atika_parts:
            pb = box.get(p.GlobalId)
            if pb is None:
                raise SystemExit("STOP: vrstva %s nemá tvar" % p.GlobalId)
            best, best_a = None, 0.0
            for w in walls:
                wb = box.get(w.GlobalId)
                if wb is None or abs(pb[2] - wb[5]) > 1500:
                    continue          # iná úroveň atiky
                a = xy_overlap(wb, pb)
                if a > best_a:
                    best, best_a = w, a
            if best is None:
                raise SystemExit("STOP: pre %s %s sa nenašla stena"
                                 % (p.Name, p.GlobalId))
            assign[best.id()].append(p)
        for w in walls:
            parts = assign.get(w.id(), [])
            if not parts:
                raise SystemExit("STOP: stena %s ostala bez vrstiev" % w.GlobalId)
            rel = m.create_entity(
                "IfcRelAggregates",
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=w.OwnerHistory,
                RelatingObject=w,
                RelatedObjects=tuple(parts),
            )
            added_guids.append(rel.GlobalId)
            for p in parts:
                detach_from_containment(m, p, removed_guids)
        log.append("#9   atika: %d× IfcRelAggregates, %d dielov %s"
                   % (len(walls), sum(len(v) for v in assign.values()),
                      dict(collections.Counter(
                          p.Name for v in assign.values() for p in v))))
    elif walls:
        log.append("#9   atika už agregovaná — preskočené")

    # ---- výpis -----------------------------------------------------------
    print("ZMENY")
    for line in log:
        print("  " + line)
    if not log:
        print("  (žiadna zmena — model je už v cieľovom stave)")
    print("\n  GlobalId zrušených: %d, nových: %d" % (len(removed_guids), len(added_guids)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    allow = args.dst + ".allowlist.json"   # viazaný na výstup, nie konštanta
    with open(allow, "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(removed_guids), "added": sorted(added_guids)},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    print("allowlist:", allow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
