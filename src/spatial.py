"""Priestorová štruktúra — pásma podlaží, obálky, test „bod v priestore".

Vzniklo pri fáze 19, keď sa ukázalo, že tri rôzne hlásené vady (vpuste na
3NP, stĺpy „náhodne" na dvoch podlažiach, dvere len na podlaží) majú jeden
spoločný koreň: **kontajnment sa určoval z `IfcBuildingStorey.Elevation`,
ale prvky podlažia začínajú pod ňou.**

Pásmo podlažia
--------------
`Elevation` je v tomto modeli **čistá podlaha**. Stĺp, priečka aj skladba
podlahy toho istého podlažia začínajú o hrúbku podlahovej skladby nižšie —
na **vrchu nosnej dosky**. Preto:

    pásmo(N) = ⟨vrch nosnej dosky pod Elevation(N),
               vrch nosnej dosky pod Elevation(N+1))

Vrchy dosiek sa berú z modelu (`IfcSlab` s `PredefinedType` `FLOOR`,
`BASESLAB` alebo `ROOF`), nie z konštanty. V OCB to dáva posun 150 mm na
2NP–4NP a 204 mm na 5NP — ručne zvolená tolerancia by jedno z toho minula.

Čo sa tým rieši
---------------
Naivné pásmo ⟨Elevation(N), Elevation(N+1)) hodí každý stĺp z `4850…8800`
do 1NP, hoci 96 % jeho výšky je v 2NP, a **zároveň** falošne obviní
skladbu podlahy `4850…5000`, ktorá do 2NP patrí správne. Posunuté pásmo
rieši oboje jedným pravidlom.

Pasce
-----
* ``geom.create_shape`` vracia **metre**, súbor je v milimetroch — všetko
  tu sa násobí 1000;
* shape z iterátora sa **drží v premennej**, inak sa číta pamäť zaniknutého
  dočasného objektu (CLAUDE_CODE_START.md);
* bbox nestačí na otázku „je bod v miestnosti" — bbox kuchynky prekrýva
  bbox openspace, takže bboxový test priradí stĺp obom. Preto
  :func:`point_in_mesh` strieľa lúč cez trojuholníky obalu.
"""

from __future__ import annotations

import os

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

#: koľko procesov dostane ``geom.iterator``
THREADS = max(1, (os.cpu_count() or 2) - 1)

#: triedy dosiek, ktorých vrch definuje hranicu pásma podlažia
STRUCTURAL_SLABS = ("FLOOR", "BASESLAB", "ROOF")


# --------------------------------------------------------------------------
# geometria
# --------------------------------------------------------------------------


def shapes(model, elements):
    """``{GlobalId: (vrcholy Nx3 v mm, trojuholníky Mx3)}``."""
    elements = [e for e in elements if e.Representation is not None]
    out: dict[str, tuple] = {}
    if not elements:
        return out
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(settings, model, THREADS, include=elements)
    if not it.initialize():
        return out
    while True:
        shape = it.get()                      # drží sa v premennej — viď docstring
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3) * 1000.0
        faces = np.array(shape.geometry.faces, dtype=int).reshape(-1, 3)
        if len(verts):
            out[shape.guid] = (verts, faces)
        if not it.next():
            break
    return out


def boxes(model, elements):
    """``{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)}`` v mm."""
    return {gid: bbox_of(vf) for gid, vf in shapes(model, elements).items()}


def bbox_of(vf):
    v = vf[0]
    return (float(v[:, 0].min()), float(v[:, 1].min()), float(v[:, 2].min()),
            float(v[:, 0].max()), float(v[:, 1].max()), float(v[:, 2].max()))


def centre(b):
    return ((b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0, (b[2] + b[5]) / 2.0)


def xy_inter(a, b):
    ix = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    iy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ix * iy


def xy_area(b):
    return max(1.0, (b[3] - b[0]) * (b[4] - b[1]))


def z_inter(a, b):
    return max(0.0, min(a[5], b[5]) - max(a[2], b[2]))


def in_box(pt, b, tol=0.0):
    return (b[0] - tol <= pt[0] <= b[3] + tol
            and b[1] - tol <= pt[1] <= b[4] + tol
            and b[2] - tol <= pt[2] <= b[5] + tol)


def point_in_mesh(pt, vf) -> bool:
    """Lúč z bodu smerom +Z; nepárny počet priesečníkov = bod je vnútri.

    Obal ``IfcSpace`` je uzavreté teleso, takže parita platí. Test je
    vektorizovaný cez barycentrické súradnice priemetu do XY.
    """
    verts, faces = vf
    tri = verts[faces]
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    det = ((b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0])
           + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1]))
    ok = np.abs(det) > 1e-9
    if not ok.any():
        return False
    safe = np.where(ok, det, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (pt[0] - c[:, 0])
          + (c[:, 0] - b[:, 0]) * (pt[1] - c[:, 1])) / safe
    l2 = ((c[:, 1] - a[:, 1]) * (pt[0] - c[:, 0])
          + (a[:, 0] - c[:, 0]) * (pt[1] - c[:, 1])) / safe
    l3 = 1.0 - l1 - l2
    hit = ok & (l1 >= 0.0) & (l2 >= 0.0) & (l3 >= 0.0)
    if not hit.any():
        return False
    z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
    return int(np.count_nonzero(hit & (z > pt[2]))) % 2 == 1


# --------------------------------------------------------------------------
# pásma podlaží
# --------------------------------------------------------------------------


def storey_zones(model, box_map=None):
    """``{IfcBuildingStorey: (zmin, zmax)}`` — pásma odvodené z dosiek.

    Dolná hranica pásma je vrch najvyššej nosnej dosky, ktorá ešte leží pod
    `Elevation` podlažia (s toleranciou 1 mm). Najvyššie pásmo je zhora
    otvorené, najnižšie siaha pod základy.
    """
    storeys = sorted(model.by_type("IfcBuildingStorey"),
                     key=lambda s: s.Elevation or 0.0)
    slabs = [s for s in model.by_type("IfcSlab")
             if getattr(s, "PredefinedType", None) in STRUCTURAL_SLABS]
    if box_map is None:
        box_map = boxes(model, slabs)
    tops = sorted({round(box_map[s.GlobalId][5], 3)
                   for s in slabs if s.GlobalId in box_map})

    def top_below(elev):
        below = [t for t in tops if t <= elev + 1.0]
        return max(below) if below else elev

    zones = {}
    for i, st in enumerate(storeys):
        lo = top_below(st.Elevation or 0.0)
        hi = (top_below(storeys[i + 1].Elevation or 0.0)
              if i + 1 < len(storeys) else float("inf"))
        zones[st] = (lo if i else -float("inf"), hi)
    return zones


def zone_share(b, zone):
    """Podiel výšky prvku, ktorý padne do pásma."""
    lo, hi = zone
    h = max(1.0, b[5] - b[2])
    return max(0.0, min(b[5], hi) - max(b[2], lo)) / h


def zone_storey(b, zones):
    """``(podlažie, podiel)`` s najväčším prienikom výšky prvku."""
    best, share = None, -1.0
    for st, zone in zones.items():
        f = zone_share(b, zone)
        if f > share:
            best, share = st, f
    return best, share


# --------------------------------------------------------------------------
# väzby
# --------------------------------------------------------------------------


def container_of(element):
    for rel in (getattr(element, "ContainedInStructure", None) or ()):
        return rel.RelatingStructure
    return None


def references_of(element):
    return [rel.RelatingStructure
            for rel in (getattr(element, "ReferencedInStructures", None) or ())]


def storey_of(spatial):
    """Podlažie, pod ktoré priestorový prvok patrí (`IfcSpace` → jeho podlažie)."""
    while spatial is not None and not spatial.is_a("IfcBuildingStorey"):
        spatial = (spatial.Decomposes[0].RelatingObject
                   if getattr(spatial, "Decomposes", None) else None)
    return spatial


def contain_in(model, target, element, added: list):
    """Zaradí prvok do kontajnmentu cieľa. Vzťah je pre prvok jediný."""
    for rel in (target.ContainsElements or ()):
        if element.id() not in {x.id() for x in rel.RelatedElements}:
            rel.RelatedElements = tuple(rel.RelatedElements) + (element,)
        return rel
    rel = model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=target.OwnerHistory,
        RelatedElements=(element,),
        RelatingStructure=target)
    added.append(rel.GlobalId)
    return rel


def reference_in(model, target, element, added: list):
    """Pridá **nehierarchickú** väzbu ``IfcRelReferencedInSpatialStructure``.

    Na rozdiel od kontajnmentu ich prvok smie mať ľubovoľne veľa — presne
    to je schémou určený spôsob, ako povedať „patrí aj sem".
    """
    for rel in (target.ReferencesElements or ()):
        if element.id() not in {x.id() for x in rel.RelatedElements}:
            rel.RelatedElements = tuple(rel.RelatedElements) + (element,)
        return rel
    rel = model.create_entity(
        "IfcRelReferencedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=target.OwnerHistory,
        RelatedElements=(element,),
        RelatingStructure=target)
    added.append(rel.GlobalId)
    return rel


def drop_reference(model, target, element, removed: list) -> bool:
    """Odoberie prvok z referencie na cieľ; prázdny vzťah zmaže."""
    eid = element.id()
    for rel in [r for r in (getattr(element, "ReferencedInStructures", None) or ())
                if r.RelatingStructure.id() == target.id()]:
        rest = tuple(x for x in rel.RelatedElements if x.id() != eid)
        if rest:
            rel.RelatedElements = rest
        else:
            removed.append(rel.GlobalId)
            model.remove(rel)
        return True
    return False
