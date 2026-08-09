"""Spoločné pomôcky pipeline.

Mazanie entít v ifcopenshell má tri pasce, na ktoré sme narazili vo fáze 1
a stáli tri segfaulty. Sú tu vyriešené raz a natrvalo:

1. handle z ``get_inverse`` sa po prvom ``model.remove()`` **zneplatnia** —
   preto sa iteruje cez ``id()`` a entita sa vyťahuje nanovo;
2. čítanie ľubovoľného atribútu zo zmazanej entity **zhodí proces**
   (SIGSEGV), nie je to výnimka — po zmazaní treba okamžite prestať;
3. Revit **zdieľa `IfcProperty` medzi psetmi**, takže mazanie musí byť
   iteratívne a po každom kole prepočítať ``get_total_inverses``.
"""

from __future__ import annotations

import collections

import ifcopenshell
import ifcopenshell.guid


def drop_rel(model, rel, removed: list, candidates: list, dead: set) -> None:
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
                            dead: set, only=None) -> None:
    """Odpojí prvok od vzťahov; prázdny vzťah zmaže.

    ``only`` je voliteľná n-tica názvov tried vzťahov — vtedy sa ostatné
    nechajú tak (napr. #27 sa dotýka len ``IfcRelAssociatesMaterial``).
    """
    eid = element.id()
    for rid in [r.id() for r in model.get_inverse(element)]:
        if rid in dead:
            continue
        rel = model.by_id(rid)
        if not rel.is_a("IfcRelationship"):
            continue
        if only is not None and not any(rel.is_a(o) for o in only):
            continue
        whole = False
        for a in ("RelatingObject", "RelatingStructure"):
            v = getattr(rel, a, None)
            if v is not None and v.id() == eid:
                whole = True
        if whole:
            drop_rel(model, rel, removed, candidates, dead)
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
                drop_rel(model, rel, removed, candidates, dead)
                break   # ďalší atribút by sa čítal z mŕtveho handle


#: atribúty, cez ktoré sa zametanie prepadáva na deti
CHILD_ATTRS = ("HasProperties", "Quantities", "MaterialConstituents",
               "MaterialLayers", "ForLayerSet")


def sweep_orphans(model, candidate_ids, removed: list, dead: set):
    """Iteratívne zmaže definície, na ktoré už nič neodkazuje.

    Zdieľané entity prežijú — po každom kole sa ``get_total_inverses``
    počíta nanovo, takže property zdieľaná iným psetom sa nezmaže.
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
            for attr in CHILD_ATTRS:
                v = getattr(e, attr, None)
                if v is None:
                    continue
                if isinstance(v, ifcopenshell.entity_instance):
                    children.append(v.id())
                else:
                    children.extend(x.id() for x in v)
            done[e.is_a()] += 1
            gid = getattr(e, "GlobalId", None)
            if isinstance(gid, str):
                removed.append(gid)
            dead.add(eid)
            model.remove(e)
            nxt.extend(children)
        queue = [i for i in nxt if i not in dead]
    return done


def detach_from_containment(model, element, removed: list) -> None:
    """Odoberie prvok z ``IfcRelContainedInSpatialStructure``."""
    eid = element.id()
    for rid in [r.id() for r in (getattr(element, "ContainedInStructure", ()) or ())]:
        rel = model.by_id(rid)
        rest = tuple(x for x in rel.RelatedElements if x.id() != eid)
        if rest:
            rel.RelatedElements = rest
        else:
            removed.append(rel.GlobalId)
            model.remove(rel)


def psets_of(element, cls="IfcPropertySet"):
    """``[(rel, definícia)]`` pre daný prvok."""
    out = []
    for r in getattr(element, "IsDefinedBy", ()) or ():
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if cls is None or d.is_a(cls):
                out.append((r, d))
    return out


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
    # LIST[1:?] — prázdny zoznam je porušenie schémy, musí to byť None.
    # V 17 to nevyskočilo, lebo OK01 aj LP01 mapy mali; ST01 typy nemajú.
    survivor.RepresentationMaps = tuple(maps) or None

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
