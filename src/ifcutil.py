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
