"""Fáza 4 — názvoslovie a INST.

Register: #M #N #P #S #Y #AP (#AX čaká na čísla), rozhodnutia 2, 4, 6, 19.

    python src/18_snim_inst.py           # dry-run
    python src/18_snim_inst.py --apply   # zapíše out/ASR_v6.ifc

Čo robí
-------
A  #N   ``LOP02`` → ``LP02`` (1292 occurrences + 1 ``IfcMemberType``)
B  #6   3NP: mená dverí ``DD03.04`` ↔ ``DD03.05`` (12 ↔ 3)
C  #AP  2 sklenené dvojkrídlové ``DD01.05.01/.02`` → ``DD01.04.01/.02``
D  #AX  ``DD01.02.01/.02/.03`` — čaká na rozhodnutie, viď ``AX_RENAME``
E  #Y   diakritika v ``LongName`` priestorov
F  #M   ``INST`` na occurrences bez neho, pevná šírka 4

Prečo je swap na 3NP práve takto
--------------------------------
2NP je podľa AUDIT správne a hovorí konvenciu jednoznačne:
``DD02.04`` = „Dvere do sklenených priečok" (3 ks), ``DD02.05`` = „Dvere do
SDK priečok" (16 ks), a mená sedia s typmi. Na 3NP sú **mená prehodené
oproti typom**: 12 kusov s menom ``DD03.04`` je typovaných ``DD03.05``
(SDK) a 3 kusy s menom ``DD03.05`` sú typované ``DD03.04`` (sklenené).
Swap teda mená s typmi zrovná. Kolízia nehrozí — ``.04`` má ``.01``–``.12``
a ``.05`` má ``.01``–``.03``, po výmene ``.05`` má ``.01``–``.12``
a ``.04`` má ``.01``–``.03``.

Poradie INST
------------
``podlažie → Y → X → Z``, ťažisko bboxu zaokrúhlené na 10 mm, počítadlo
po kóde **globálne** cez celú budovu. Poradie sa počíta **z geometrie**
cez ``geom.iterator``, nie z ``ObjectPlacement`` — 149 prvkov má placement
v (0,0,0) vrátane stĺpov ``SL02``, takže placement by dal nezmysel (#P).

25 prvkov nemá vlastný tvar — sú to zostavy (12 ``PL01``, 4 ``LP03.01``,
3 ``OV06.01``, 3 ``SC01``, 2 ``ST01``, 1 ``SH04.03``). Ich bbox sa
dopočíta z agregovaných častí. ``GlobalId`` je posledný člen triediaceho
kľúča, aby bolo poradie deterministické.

Čo sa NEMENÍ
------------
154 occurrences ``DD*``/``PD*``/``OV*``, ktoré už ``INST`` majú — sú
výkresovo autoritatívne (#S). 26 ``LP01`` ``IfcWindow`` sa prečíslováva,
lebo ich ``UOT`` bol zneužitý ako počítadlo (#O, rozhodnutie 19).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.geom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_invariants import parse_snim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v5.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v6.ifc")

DRY_RUN = True

#: #N rozhodnutie 4
CODE_RENAME = {"LOP02": "LP02"}

#: #6 swap na 3NP — (staré UOT, nové UOT)
DOOR_SWAP_3NP = ("DD03.04", "DD03.05")

#: #AP rozhodnutie 6 — sklenené dvojkrídlové z DD01.05 na voľné DD01.04
GLASS_DOUBLE = {"DD01.05.01": "DD01.04.01", "DD01.05.02": "DD01.04.02"}

#: #AX — duplicitné DD01.02.01/.02/.03. PRÁZDNE, kým Samuel nedodá čísla.
#: Formát: {GlobalId: nové_meno}. Bez toho invariant 6 ostane na 3 kódoch.
AX_RENAME: dict[str, str] = {}

#: #Y diakritika v LongName priestorov
DIACRITICS = {
    "Openspace - Zapad": "Openspace - Západ",
    "Openspace - Vychod": "Openspace - Východ",
}

#: výkresovo autoritatívne prefixy — ich INST sa nemení (#S)
AUTHORITATIVE = ("DD", "PD", "OV")

INST_WIDTH = 4
ROUND_MM = 10.0


def bboxes(model, elements):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(
        s, model, max(1, (os.cpu_count() or 2) - 1), include=list(elements))
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


def effective_box(e, box):
    """Vlastný bbox, inak zjednotenie bboxov agregovaných častí."""
    b = box.get(e.GlobalId)
    if b:
        return b
    parts = [p for r in (e.IsDecomposedBy or ()) for p in r.RelatedObjects]
    bs = [box.get(p.GlobalId) for p in parts]
    bs = [x for x in bs if x]
    if not bs:
        return None
    return (min(x[0] for x in bs), min(x[1] for x in bs), min(x[2] for x in bs),
            max(x[3] for x in bs), max(x[4] for x in bs), max(x[5] for x in bs))


def storey_of(e):
    for r in getattr(e, "ContainedInStructure", ()) or ():
        return r.RelatingStructure
    for r in getattr(e, "Decomposes", ()) or ():
        return storey_of(r.RelatingObject)
    return None


def snap(v):
    return round(v / ROUND_MM) * ROUND_MM


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
    log: list[str] = []
    elements = [e for e in m.by_type("IfcElement") if not e.is_a("IfcFeatureElement")]

    # ---- A · #N LOP02 → LP02 -------------------------------------------
    n = collections.Counter()
    for e in list(m.by_type("IfcProduct")) + list(m.by_type("IfcTypeProduct")):
        new = CODE_RENAME.get(e.Name)
        if new:
            e.Name = new
            n["typ" if e.is_a("IfcTypeObject") else "occ"] += 1
    if n:
        log.append("#N   LOP02 → LP02: %d occurrences + %d typ"
                   % (n["occ"], n["typ"]))

    # ---- B · #6 swap dverí na 3NP ---------------------------------------
    a, b = DOOR_SWAP_3NP
    plan = []
    for d in list(m.by_type("IfcDoor")):
        st = storey_of(d)
        if not d.Name or st is None or st.Name != "3NP":
            continue
        if d.Name.startswith(a + "."):
            plan.append((d, b + d.Name[len(a):]))
        elif d.Name.startswith(b + "."):
            plan.append((d, a + d.Name[len(b):]))
    if plan:
        for d, new in plan:            # naraz, až po výpočte všetkých
            d.Name = new
        log.append("#6   3NP swap %s ↔ %s: %d dverí"
                   % (a, b, len(plan)))

    # ---- C · #AP sklenené dvojkrídlové ----------------------------------
    n_ap = 0
    for d in list(m.by_type("IfcDoor")):
        new = GLASS_DOUBLE.get(d.Name or "")
        if new and d.Description and "sklen" in d.Description.lower():
            d.Name = new
            n_ap += 1
    if n_ap:
        log.append("#AP  sklenené dvojkrídlové DD01.05 → DD01.04: %d" % n_ap)

    # ---- D · #AX --------------------------------------------------------
    n_ax = 0
    for gid, new in AX_RENAME.items():
        m.by_guid(gid).Name = new
        n_ax += 1
    if n_ax:
        log.append("#AX  prečíslovaných duplicitných dverí: %d" % n_ax)

    # ---- E · #Y diakritika ----------------------------------------------
    n_y = collections.Counter()
    for s in list(m.by_type("IfcSpatialElement")):
        new = DIACRITICS.get(s.LongName or "")
        if new:
            s.LongName = new
            n_y[new] += 1
    if n_y:
        log.append("#Y   diakritika v LongName: %s" % dict(n_y))

    # ---- F · #M INST ----------------------------------------------------
    box = bboxes(m, elements)
    storeys = sorted({st.id(): st for st in m.by_type("IfcBuildingStorey")}.values(),
                     key=lambda s: (s.Elevation if s.Elevation is not None else 0))
    order = {s.id(): i for i, s in enumerate(storeys)}

    used = collections.defaultdict(set)      # kód → obsadené INST
    todo = collections.defaultdict(list)     # kód → prvky bez INST
    for e in elements:
        code, inst = parse_snim(e.Name)
        if code is None:
            continue
        if inst is not None and (e.Name or "").startswith(AUTHORITATIVE):
            used[code].add(inst.zfill(INST_WIDTH))   # autoritatívne, nemení sa
        else:
            todo[code].append(e)

    def key(e):
        bb = effective_box(e, box)
        st = storey_of(e)
        si = order.get(st.id(), len(order)) if st else len(order)
        if bb is None:
            return (si, float("inf"), float("inf"), float("inf"), e.GlobalId)
        return (si, snap((bb[1] + bb[4]) / 2), snap((bb[0] + bb[3]) / 2),
                snap((bb[2] + bb[5]) / 2), e.GlobalId)

    assigned = 0
    for code, items in todo.items():
        items.sort(key=key)
        nxt = 1
        for e in items:
            while str(nxt).zfill(INST_WIDTH) in used[code]:
                nxt += 1
            new = "%s.%s" % (code, str(nxt).zfill(INST_WIDTH))
            used[code].add(str(nxt).zfill(INST_WIDTH))
            if e.Name != new:
                e.Name = new
                assigned += 1
            nxt += 1
    if assigned:
        log.append("#M   INST pridelený %d occurrences v %d kódoch, šírka %d"
                   % (assigned, len(todo), INST_WIDTH))

    # ---- kontrola brány 4 ------------------------------------------------
    full = collections.defaultdict(list)
    for e in elements:
        code, inst = parse_snim(e.Name)
        if inst is not None:
            full[e.Name].append(e)
    dups = {k: len(v) for k, v in full.items() if len(v) > 1}
    no_inst = [e for e in elements if parse_snim(e.Name)[1] is None]

    print("ZMENY")
    for line in log:
        print("  " + line)
    if not log:
        print("  (žiadna zmena — model je už v cieľovom stave)")
    print("\nKONTROLA BRÁNY 4")
    print("  occurrences s plným SNIM kódom : %d z %d"
          % (sum(len(v) for v in full.values()), len(elements)))
    print("  bez INST                       : %d %s"
          % (len(no_inst), dict(collections.Counter(e.Name for e in no_inst))))
    print("  duplicitných plných kódov      : %d %s   (očakávané 0)"
          % (len(dups), dups))
    if not AX_RENAME:
        print("  POZNÁMKA: #AX nie je vyriešené — chýbajú čísla pre "
              "DD01.02.01/.02/.03")

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
