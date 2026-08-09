"""Fáza 6b — hranice priestorov (#L).

Register: #L, rozhodnutie 23 z ``AUDIT.md`` §2.

    python src/23_space_boundaries.py           # dry-run
    python src/23_space_boundaries.py --apply   # zapíše out/ASR_v11.ifc

Čo robí
-------
Zakladá ``IfcRelSpaceBoundary1stLevel`` — 1. úroveň, **bez**
``ConnectionGeometry``, s ``ParentBoundary`` pre dvere a okná. Spec
(IFC4.3 §5.4.3.60) k tomu atribútu hovorí: *„ParentBoundary with inverse
InnerBoundaries is provided to link the space boundaries of doors,
windows, and openings to the parent boundary, such as of a wall or slab."*

2. úroveň sa nerobí — energetické zónovanie je mimo rozsah (§2).

Ako sa hranica nájde
--------------------
Hranica je odpoveď na otázku „čo stojí tesne za touto stenou miestnosti".
Berie sa teda **obal priestoru** a z každého jeho trojuholníka sa vystrelí
lúč von po normále. Prvý prvok, ktorý lúč trafí, je hranicou.

Prečo lúč a nie „bod vnútri bboxu": bbox veľkej dosky obsahuje aj body,
ktoré v doske nie sú, takže test bodom priradí jednej stene miestnosti
tri rôzne prvky naraz. Lúč berie **najbližší** zásah, čo je presne to, čo
slovo hranica znamená. Zásah sa počíta na bboxe (slab method) — presnosť
na úrovni bboxu tu stačí, lebo hranica 1. úrovne nenesie geometriu.

Čo hranicou nie je
------------------
Krytiny, nábytok a zariaďovacie predmety sa vynechávajú. Ich vzťah
k miestnosti už nesie **kontajnment** z fázy 6a (rozhodnutie 24) a druhý
raz ho vyjadrovať ako hranicu by bola duplicita. Hranica hovorí, čo
miestnosť uzatvára, nie čo v nej stojí.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v10.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v11.ifc")

DRY_RUN = True

#: triedy, ktoré priestor uzatvárajú
ENCLOSING = ("IfcWall", "IfcSlab", "IfcRoof", "IfcColumn", "IfcCurtainWall",
             "IfcDoor", "IfcWindow", "IfcStair", "IfcFooting", "IfcPlate",
             "IfcMember")

#: dokiaľ lúč hľadá; za touto vzdialenosťou už nejde o hranicu (mm)
REACH = 400.0

#: o koľko sa okolo priestoru zbierajú kandidáti (mm)
INFLATE = 800.0

#: Minimálna plocha zásahu, aby šlo o hranicu a nie o dotyk rohom (mm²).
#: Počítať trojuholníky sa nedá: kvádrový priestor má na stenu presne dva,
#: takže akýkoľvek počtový prah nad 2 zmaže hranice všetkých jednoduchých
#: miestností. Plocha je na tvare nezávislá.
MIN_AREA = 50_000.0

#: Dvere a okná sedia v otvore steny, ale **bbox steny ten otvor zahŕňa**,
#: takže lúč vojde do steny v tej istej vzdialenosti ako do výplne. Keď sú
#: zásahy takto tesne pri sebe, vyhráva výplň — to je ten konkrétnejší prvok.
TIE = 50.0


def bboxes(model, products):
    out = {}
    products = [p for p in products if p.Representation is not None]
    if not products:
        return out
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        s, model, max(1, (os.cpu_count() or 2) - 1), include=products)
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


def meshes(model, products):
    """``{GlobalId: (verts_mm, faces)}``."""
    out = {}
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        s, model, max(1, (os.cpu_count() or 2) - 1), include=products)
    if not it.initialize():
        return out
    while True:
        sh = it.get()
        v = sh.geometry.verts
        if v:
            out[sh.guid] = ([x * 1000.0 for x in v], list(sh.geometry.faces))
        if not it.next():
            break
    return out


def vol(b):
    return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2])


def ray_bbox(o, d, b):
    """Vzdialenosť po lúči k vstupu do bboxu, alebo ``None``.

    Klasická slab method: pre každú os interval parametrov, v ktorých je
    lúč vnútri pásu bboxu; prienik intervalov dá vstup a výstup.
    """
    tmin, tmax = 0.0, float("inf")
    for i in range(3):
        lo, hi = b[i], b[i + 3]
        if abs(d[i]) < 1e-12:
            if o[i] < lo or o[i] > hi:
                return None
            continue
        t1 = (lo - o[i]) / d[i]
        t2 = (hi - o[i]) / d[i]
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return None
    return tmin


def whole_of(e):
    """Najvyšší celok, ktorého je prvok časťou.

    Lúč trafí konkrétny panel či stĺpik fasády, ale hranicou miestnosti je
    **celok** — rovnako ako pri kontajnmente, ktorý po fáze 6a drží tiež
    celok, nie časť. Bez tohto kroku by openspace mal 79 hraníc na tú istú
    fasádu.
    """
    seen = set()
    while True:
        dec = getattr(e, "Decomposes", None)
        if not dec or e.id() in seen:
            return e
        seen.add(e.id())
        e = dec[0].RelatingObject


def host_wall(e):
    """Stena či doska, do ktorej otvoru dvere alebo okno sedia."""
    for r in (getattr(e, "FillsVoids", None) or ()):
        op = r.RelatingOpeningElement
        for v in (getattr(op, "VoidsElements", None) or ()):
            return v.RelatingBuildingElement
    return None


def is_external(e):
    for r in (getattr(e, "IsDefinedBy", None) or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcPropertySet"):
                for p in (d.HasProperties or ()):
                    if p.Name == "IsExternal" and p.is_a("IfcPropertySingleValue"):
                        return bool(p.NominalValue.wrappedValue)
    t = getattr(e, "IsTypedBy", None)
    if t:
        for p in (t[0].RelatingType.HasPropertySets or ()):
            if p.is_a("IfcPropertySet"):
                for q in (p.HasProperties or ()):
                    if q.Name == "IsExternal" and q.is_a("IfcPropertySingleValue"):
                        return bool(q.NominalValue.wrappedValue)
    return None


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

    existing = m.by_type("IfcRelSpaceBoundary")
    if existing:
        print("hranice už existujú (%d) — skript je idempotentný, končí"
              % len(existing))
        return 0

    spaces = [s for s in m.by_type("IfcSpace") if s.Representation is not None]
    els = [e for cls in ENCLOSING for e in m.by_type(cls)
           if e.Representation is not None and not e.is_a("IfcFeatureElement")]
    els = list({e.id(): e for e in els}.values())
    print("priestorov %d, uzatvárajúcich prvkov %d" % (len(spaces), len(els)))

    ebox = bboxes(m, els)
    smesh = meshes(m, spaces)
    print("bboxov prvkov %d, obalov priestorov %d\n" % (len(ebox), len(smesh)))

    by_gid = {e.GlobalId: e for e in els}
    owner = spaces[0].OwnerHistory

    pairs: dict[int, collections.Counter] = {}
    # by_gid je potrebné už pri sondovaní — výplň má prednosť pred stenou
    for sp in spaces:
        mesh = smesh.get(sp.GlobalId)
        if mesh is None:
            continue
        v, f = mesh
        sb = (min(v[0::3]), min(v[1::3]), min(v[2::3]),
              max(v[0::3]), max(v[1::3]), max(v[2::3]))
        near = [(g, b) for g, b in ebox.items()
                if b[3] > sb[0] - INFLATE and b[0] < sb[3] + INFLATE
                and b[4] > sb[1] - INFLATE and b[1] < sb[4] + INFLATE
                and b[5] > sb[2] - INFLATE and b[2] < sb[5] + INFLATE]
        hits = collections.Counter()
        for i in range(0, len(f), 3):
            p = [v[f[i + k] * 3: f[i + k] * 3 + 3] for k in range(3)]
            ux, uy, uz = (p[1][j] - p[0][j] for j in range(3))
            wx, wy, wz = (p[2][j] - p[0][j] for j in range(3))
            n = (uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx)
            L = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
            if L < 1e-9:
                continue
            n = (n[0] / L, n[1] / L, n[2] / L)
            o = [(p[0][j] + p[1][j] + p[2][j]) / 3.0 + n[j] * 1.0 for j in range(3)]
            zasahy = []
            for g, b in near:
                t = ray_bbox(o, n, b)
                if t is not None and t < REACH:
                    zasahy.append((t, g, b))
            if not zasahy:
                continue
            tmin = min(z[0] for z in zasahy)
            blizke = [z for z in zasahy if z[0] <= tmin + TIE]
            vypln = [z for z in blizke
                     if by_gid[z[1]].is_a() in ("IfcDoor", "IfcWindow")]
            pick = (min(vypln, key=lambda z: z[0]) if vypln
                    else min(blizke, key=lambda z: (z[0], vol(z[2]))))
            e_hit = by_gid[pick[1]]
            # výplň zostáva sama sebou — celok bude jej ParentBoundary
            key = (e_hit if e_hit.is_a() in ("IfcDoor", "IfcWindow")
                   else whole_of(e_hit)).GlobalId
            hits[key] += L / 2.0            # plocha trojuholníka
        pairs[sp.id()] = hits

    # ---- zápis vzťahov, dvere a okná až po rodičoch ----------------------
    made: dict[tuple, object] = {}
    plan = []
    for sp in spaces:
        for gid, n in (pairs.get(sp.id()) or {}).items():
            if n < MIN_AREA:
                continue
            plan.append((sp, m.by_guid(gid)))

    # najprv rodičia (steny, dosky…), potom výplne
    plan.sort(key=lambda x: x[1].is_a() in ("IfcDoor", "IfcWindow"))
    for sp, e in plan:
        ext = is_external(e)
        rel = m.create_entity(
            "IfcRelSpaceBoundary1stLevel",
            GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            Name="%s / %s" % (sp.Name, e.Name),
            RelatingSpace=sp, RelatedBuildingElement=e,
            ConnectionGeometry=None,
            PhysicalOrVirtualBoundary="PHYSICAL",
            InternalOrExternalBoundary=("EXTERNAL" if ext else
                                        "INTERNAL" if ext is False else "NOTDEFINED"))
        made[(sp.id(), e.id())] = rel
        added.append(rel.GlobalId)

    # ---- ParentBoundary pre dvere a okná --------------------------------
    linked = sirota = 0
    bez_rodica = collections.Counter()
    odvodene = 0
    for (sid, eid), rel in made.items():
        e = m.by_id(eid)
        if not e.is_a("IfcDoor") and not e.is_a("IfcWindow"):
            continue
        # rodičom je stena, do ktorej otvoru výplň sedí; ak výplň nesedí
        # v otvore (fasádne okno), je ním celok, ktorého je súčasťou
        parent = None
        # 80 z 97 dverí v modeli nemá FillsVoids (nový nález, viď §17), takže
        # hostiteľ sa musí odvodiť z polohy: stena, ktorá je hranicou tej istej
        # miestnosti a ktorej bbox dvere obsahuje. Odvodenie je overiteľné —
        # keď taká stena nie je, ParentBoundary sa nechá prázdny.
        geom_host = None
        db = ebox.get(e.GlobalId)
        if db is not None:
            dc = [(db[0] + db[3]) / 2, (db[1] + db[4]) / 2, (db[2] + db[5]) / 2]
            best = None
            for (s2, e2), _ in made.items():
                if s2 != sid:
                    continue
                cand = m.by_id(e2)
                if not cand.is_a("IfcWall"):
                    continue
                cb = ebox.get(cand.GlobalId)
                if cb is None:
                    continue
                if all(cb[i] - 150 <= dc[i] <= cb[i + 3] + 150 for i in range(3)):
                    if best is None or vol(cb) < vol(ebox[best.GlobalId]):
                        best = cand
            geom_host = best
        for kand in (host_wall(e), geom_host, whole_of(e)):
            if kand is not None and kand.id() != e.id():
                parent = made.get((sid, kand.id()))
                if parent is not None:
                    break
        if parent is None:
            sirota += 1
            bez_rodica[e.is_a()] += 1
            continue
        rel.ParentBoundary = parent
        linked += 1
        if host_wall(e) is None and geom_host is not None:
            odvodene += 1

    per = collections.Counter(e.is_a() for (_, eid), _ in made.items()
                              for e in [m.by_id(eid)])
    perspace = collections.Counter()
    for (sid, _), _ in made.items():
        perspace[m.by_id(sid).Name] += 1

    print("ZMENY")
    print("  #L   %d hraníc na %d priestoroch" % (len(made), len(perspace)))
    for k, n in per.most_common():
        print("        %-18s %4d" % (k, n))
    print("  #L   ParentBoundary: %d napojených, %d bez rodiča %s"
          % (linked, sirota, dict(bez_rodica) if bez_rodica else ""))
    print("       z toho hostiteľ odvodený z polohy (chýba FillsVoids): %d" % odvodene)
    bez = [s.Name for s in spaces if perspace.get(s.Name, 0) == 0]
    if bez:
        print("  #L   BEZ HRANÍC: %d priestorov — %s" % (len(bez), bez[:10]))
    print("       hraníc na priestor: medián %d, min %d, max %d"
          % (sorted(perspace.values())[len(perspace) // 2],
             min(perspace.values()), max(perspace.values())))

    print("\n  GlobalId nových: %d" % len(added))

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
