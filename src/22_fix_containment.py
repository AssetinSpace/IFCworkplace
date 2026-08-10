"""Fáza 6a — kontajnment a agregácia skladieb.

Register: #AW #AO #G #H, rozhodnutie 24 z ``AUDIT.md`` §2.

    python src/22_fix_containment.py           # dry-run
    python src/22_fix_containment.py --apply   # zapíše out/ASR_v10.ifc

Čo robí
-------
A  #AW  85 častí fasády je súčasne agregovaných aj kontajnovaných.
        Kontajnment je exkluzívny — do priestorovej štruktúry viaže celok,
        nie časť. Časti sa preto z kontajnmentu odoberajú a najprv sa
        overí, že ich celok kontajnovaný naozaj je.
B  #AO  fasádne zateplenia ``FS01``/``FS03`` idú cez ``IfcRelAggregates``
        do steny, ktorú pokrývajú, a z kontajnmentu von. Tá istá
        deprecation ako pri atike vo fáze 1 (``IfcRelCoversBldgElements``).
C  #G   +  #H  **jedno geometrické pravidlo namiesto dvoch opráv.**
        Kontajnment sa pre triedy z rozhodnutia 24 prepočíta z geometrie:
        prvok patrí do priestoru, ktorý ho obsahuje, inak do podlažia,
        v ktorého pásme leží. Tým sa 16 strešných vpustí dostane von
        z openspace na 3NP (#G) a podhľady, podlahy a zariaďovacie
        predmety do miestností (#H) — bez dvoch rôznych pravidiel.

Prečo sa dvere a steny nepresúvajú
----------------------------------
Rozhodnutie 24: kontajnment je exkluzívny, takže dvere patriace dvom
miestnostiam by sa museli prikloniť k jednej. To je vec
``IfcRelSpaceBoundary`` vo fáze 6b, nie kontajnmentu.

Pasce
-----
* prvok s ``Decomposes`` **nesmie** byť kontajnovaný (invariant 7), preto
  sa agregované prvky do prepočtu vôbec neberú;
* ``IfcRelContainedInSpatialStructure`` je pre prvok jediný — presun je
  odobratie zo starého a pridanie do nového, nie druhý vzťah;
* priestor sa hľadá ako **najmenší**, ktorý ťažisko obsahuje; bez toho by
  chodba pohltila prvky priľahlých miestností.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import detach_from_containment  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v9.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v10.ifc")

DRY_RUN = True

#: triedy, ktoré podľa rozhodnutia 24 smú byť v miestnosti
ROOM_CLASSES = ("IfcCovering", "IfcFlowTerminal", "IfcSanitaryTerminal",
                "IfcFurniture", "IfcRailing")

#: kódy fasádnych zateplení pre #AO
ETICS_PREFIX = ("FS01", "FS03")

#: tolerancia párovania vrstvy k stene, prevzatá z fázy 1
TOL_XY = 100.0

#: o koľko sa priestor „zmenší" pri teste obsahovania ťažiska; bez toho by
#: prvok na hranici dvoch miestností padol do oboch
SHRINK = 1.0

#: zvislá tolerancia priľahlosti krytiny k miestnosti (hrúbka skladby podlahy)
TOL_Z = 300.0

#: koľko z pôdorysu krytiny musí ležať v miestnosti, aby jej patrila
MIN_COVER = 0.5


def bboxes(model, elements):
    """``{GlobalId: (xmin,ymin,zmin,xmax,ymax,zmax)}`` v mm."""
    elements = [e for e in elements if e.Representation is not None]
    out = {}
    if not elements:
        return out
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        s, model, max(1, (os.cpu_count() or 2) - 1), include=elements)
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


def centre(b):
    return ((b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0, (b[2] + b[5]) / 2.0)


def volume(b):
    return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2])


def inside(pt, b, shrink=SHRINK):
    return (b[0] + shrink <= pt[0] <= b[3] - shrink
            and b[1] + shrink <= pt[1] <= b[4] - shrink
            and b[2] + shrink <= pt[2] <= b[5] - shrink)


def xy_inter(a, b):
    ix = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    iy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ix * iy


def xy_area(b):
    return (b[3] - b[0]) * (b[4] - b[1])


def xy_overlap(a, b, tol=TOL_XY):
    ox = min(a[3] + tol, b[3] + tol) - max(a[0] - tol, b[0] - tol)
    oy = min(a[4] + tol, b[4] + tol) - max(a[1] - tol, b[1] - tol)
    return ox * oy if ox > 0 and oy > 0 else 0.0


def z_overlap(a, b):
    o = min(a[5], b[5]) - max(a[2], b[2])
    return o if o > 0 else 0.0


def container_of(e):
    for r in (getattr(e, "ContainedInStructure", None) or ()):
        return r.RelatingStructure
    return None


def contain_in(model, target, element, added: list):
    """Pridá prvok do kontajnmentu cieľa; vytvorí vzťah, ak ešte nie je."""
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
    removed: list[str] = []
    log: list[str] = []

    storeys = sorted(m.by_type("IfcBuildingStorey"),
                     key=lambda s: s.Elevation or 0.0)
    spaces = list(m.by_type("IfcSpace"))

    # ---- A · #AW dvojitá väzba ------------------------------------------
    both = [e for e in m.by_type("IfcObjectDefinition")
            if getattr(e, "Decomposes", None) and getattr(e, "ContainedInStructure", None)]
    if both:
        # najprv overiť, že celok je viazaný — inak by sa časť „stratila"
        for e in both:
            whole = e.Decomposes[0].RelatingObject
            if not (getattr(whole, "ContainedInStructure", None)
                    or getattr(whole, "Decomposes", None)):
                raise SystemExit(
                    "STOP: celok %s %r nie je v priestorovej štruktúre — "
                    "odobratím časti by sa stratila" % (whole.is_a(), whole.Name))
        for e in list(both):
            detach_from_containment(m, e, removed)
        log.append("#AW  %d častí odobraných z kontajnmentu %s"
                   % (len(both), dict(collections.Counter(e.is_a() for e in both))))
    else:
        log.append("#AW  žiadna dvojitá väzba — preskočené")

    # ---- B · #AO fasádne zateplenia do steny ----------------------------
    etics = [e for e in m.by_type("IfcCovering")
             if (e.Name or "").startswith(ETICS_PREFIX) and not e.Decomposes]
    if etics:
        walls = list(m.by_type("IfcWall"))
        box = bboxes(m, walls + etics)
        assign = collections.defaultdict(list)
        siroty = []
        for p in etics:
            pb = box.get(p.GlobalId)
            if pb is None:
                raise SystemExit("STOP: zateplenie %s nemá tvar" % p.GlobalId)
            best, best_a = None, 0.0
            for w in walls:
                wb = box.get(w.GlobalId)
                if wb is None or z_overlap(pb, wb) < 100.0:
                    continue
                a = xy_overlap(wb, pb)
                if a > best_a:
                    best, best_a = w, a
            if best is None:
                siroty.append(p)
                continue
            assign[best.id()].append(p)
        for wid, parts in assign.items():
            w = m.by_id(wid)
            rel = None
            for r in (w.IsDecomposedBy or ()):
                rel = r
                break
            if rel is None:
                rel = m.create_entity(
                    "IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                    OwnerHistory=w.OwnerHistory, RelatingObject=w,
                    RelatedObjects=tuple(parts))
                added.append(rel.GlobalId)
            else:
                rel.RelatedObjects = tuple(rel.RelatedObjects) + tuple(parts)
            for p in parts:
                detach_from_containment(m, p, removed)
        log.append("#AO  %d zateplení do %d stien cez IfcRelAggregates"
                   % (sum(len(v) for v in assign.values()), len(assign)))
        if siroty:
            log.append("#AO  BEZ STENY: %d — %s"
                       % (len(siroty), [p.Name for p in siroty][:8]))
    else:
        log.append("#AO  zateplenia už agregované — preskočené")

    # ---- C+D · #G #H kontajnment z geometrie ----------------------------
    cand = []
    for cls in ROOM_CLASSES:
        for e in m.by_type(cls):
            if getattr(e, "Decomposes", None):
                continue                       # agregované — invariant 7
            if container_of(e) is None:
                continue                       # nikde neviazané, nehýbeme
            if (e.Name or "").startswith(ETICS_PREFIX):
                continue                       # rieši #AO, nie kontajnment
            cand.append(e)

    box = bboxes(m, cand + spaces)
    sbb = [(s, box[s.GlobalId]) for s in spaces if s.GlobalId in box]
    bands = []
    for i, st in enumerate(storeys):
        zl = st.Elevation or 0.0
        zh = (storeys[i + 1].Elevation if i + 1 < len(storeys) else zl + 5000.0)
        bands.append((st, zl, zh))

    moves = collections.Counter()
    detail = collections.Counter()
    nogeom = 0
    for e in cand:
        b = box.get(e.GlobalId)
        if b is None:
            nogeom += 1
            continue
        c = centre(b)
        if e.is_a("IfcCovering"):
            # Krytina leží **mimo** objemu miestnosti — podlaha pod ňou,
            # podhľad nad ňou — takže test ťažiskom by ju vždy vyhodil do
            # podlažia. Rozhoduje zvislá priľahlosť a až potom prekryv;
            # opačné poradie nefunguje, lebo bbox openspace prekrýva v XY
            # takmer všetko a párovanie by trafilo cudzie podlažie.
            best, best_o = None, 0.0
            for s, sb in sbb:
                podlaha = abs(sb[2] - b[5]) <= TOL_Z
                podhlad = abs(b[2] - sb[5]) <= TOL_Z
                vnutri = sb[2] - TOL_Z <= b[2] and b[5] <= sb[5] + TOL_Z
                if not (podlaha or podhlad or vnutri):
                    continue
                o = xy_inter(b, sb) / max(1.0, xy_area(b))
                if o > best_o:
                    best, best_o = s, o
            hit = [(best, None)] if (best is not None and best_o >= MIN_COVER) else []
        else:
            hit = [(s, sb) for s, sb in sbb if inside(c, sb)]
        if hit and hit[0][1] is None:
            target = hit[0][0]
        elif hit:
            target = min(hit, key=lambda x: volume(x[1]))[0]
        else:
            target = None
            for st, zl, zh in bands:
                if zl <= c[2] < zh:
                    target = st
                    break
            if target is None:
                target = bands[-1][0] if c[2] >= bands[-1][1] else bands[0][0]
        cur = container_of(e)
        if cur is not None and cur.id() == target.id():
            continue
        detach_from_containment(m, e, removed)
        contain_in(m, target, e, added)
        moves["%s → %s" % (cur.is_a().replace("Ifc", "") if cur else "?",
                           target.is_a().replace("Ifc", ""))] += 1
        detail[(e.is_a(), (e.Name or "?")[:4])] += 1

    if moves:
        log.append("#G#H presunutých %d prvkov: %s"
                   % (sum(moves.values()), dict(moves)))
    else:
        log.append("#G#H kontajnment už sedí s geometriou — preskočené")
    if nogeom:
        log.append("#G#H %d kandidátov bez tvaru — nedotknuté" % nogeom)

    # ---- E · #G zvyšok: vrstva ST01 mimo strešnej agregácie -------------
    # Fáza 1 ju minula, lebo bola kontajnovaná v 3NP, kým zvyšok súvrstvia
    # visí na 4NP. Patrí do tej strechy, ktorej stoh na ňu **nadväzuje**:
    # vrch vrstvy = spodok agregátu, pri zhodnom pôdoryse.
    strays = [e for e in m.by_type("IfcCovering")
              if (e.Name or "").startswith("ST01") and not e.Decomposes
              and container_of(e) is not None]
    if strays:
        roofs = {r: [o for rel in (r.IsDecomposedBy or ()) for o in rel.RelatedObjects]
                 for r in m.by_type("IfcRoof")}
        rb = bboxes(m, strays + [p for v in roofs.values() for p in v])
        for e in strays:
            eb = rb.get(e.GlobalId)
            if eb is None:
                continue
            best = None
            for r, parts in roofs.items():
                pb = [rb[p.GlobalId] for p in parts if p.GlobalId in rb]
                if not pb:
                    continue
                zmin = min(x[2] for x in pb)
                ext = (min(x[0] for x in pb), min(x[1] for x in pb), 0.0,
                       max(x[3] for x in pb), max(x[4] for x in pb), 0.0)
                if abs(zmin - eb[5]) > TOL_Z:
                    continue
                if xy_inter(eb, ext) / max(1.0, xy_area(eb)) < 0.9:
                    continue
                best = r
                break
            if best is None:
                log.append("#G   %s nenadväzuje na žiadnu strechu — nedotknuté"
                           % e.Name)
                continue
            rel = (best.IsDecomposedBy or (None,))[0]
            rel.RelatedObjects = tuple(rel.RelatedObjects) + (e,)
            detach_from_containment(m, e, removed)
            log.append("#G   %s → agregácia %s (%d dielov)"
                       % (e.Name, best.Name, len(rel.RelatedObjects)))

    # ---- kontrola: invariant 7 na vlastnom výsledku ----------------------
    bad = [e for e in m.by_type("IfcObjectDefinition")
           if getattr(e, "Decomposes", None) and getattr(e, "ContainedInStructure", None)]
    if bad:
        raise SystemExit("STOP: invariant 7 porušený na %d prvkoch — %s"
                         % (len(bad), [e.Name for e in bad][:6]))
    log.append("     kontrola inv 7: 0 prvkov s dvojitou väzbou")

    orphan = [e for cls in ROOM_CLASSES for e in m.by_type(cls)
              if container_of(e) is None and not getattr(e, "Decomposes", None)
              and e.Representation is not None]
    log.append("     bez kontajnera po behu: %d" % len(orphan))

    print("ZMENY")
    for line in log:
        print("  " + line)
    if detail:
        print("\n  rozpad presunov")
        for (cls, code), n in detail.most_common(18):
            print("     %-20s %-6s %4d" % (cls, code, n))
    print("\n  GlobalId nových: %d, zrušených: %d" % (len(added), len(removed)))

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
