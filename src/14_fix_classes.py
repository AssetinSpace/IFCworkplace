"""Fáza 1a — triedny model.

Register: #AL #AB #AC #AN #AM (časť pre steny), rozhodnutia 8, 12, 13, 14, 15
z ``AUDIT.md`` §2.

    python src/14_fix_classes.py            # dry-run, nič nezapíše
    python src/14_fix_classes.py --apply    # zapíše out/ASR_v3_a.ifc

Čo robí
-------
A  #AL / 8   ``IH01`` hydroizolácia   ``IfcWall/STANDARD`` → ``IfcCovering/MEMBRANE``
B  #AB / 12  základový blok           ``IfcStair`` → ``IfcFooting/PAD_FOOTING``,
                                      premenovaný na ``ZD02.05``
C  #AC / 12  základové dosky          typ ``ZD02.04`` → ``ZD02.01``;
                                      ``ZD02.03`` aj ``ZD02.04`` → ``BASESLAB``
D  #AN / 14  ``KV01`` oplechovanie    ``MOLDING`` → ``COPING``
E  #AM / 13, 15  ``PredefinedType`` stien podľa §5

Čo NEROBÍ a prečo
-----------------
``IfcRoof`` (84×) rieši ``15_fix_roof_assembly.py``.

67 occurrences ostáva ``NOTDEFINED`` zámerne — §5 pre ne pravidlo nemá
a §2 rozhodnutie tiež nie: 8 ``IfcSlab DZ02``, 19 ``IfcCurtainWall``,
22 ``IfcFurniture``, 12 ``IfcRailing``, 3 ``IfcStair SC01``,
2 ``IfcStairFlight SC01``. Nehádame — treba rozhodnutie do §5.

Pozn. k počtu 383 z #AM: v modeli je 314 occurrences s ``NOTDEFINED``
plus 69 ``IfcFlowTerminal``, ktoré v IFC4X3 atribút ``PredefinedType``
**vôbec nemajú**. 314 + 69 = 383. Terminály rieši fáza 10 (`26_sanitary.py`)
prekvalifikovaním na konkrétne podtypy, ktoré ``PredefinedType`` majú.

Pasce
-----
* ``ifcopenshell.api.root.reassign_class`` kaskádovo prepíše zdieľaný typ —
  raz to prepísalo 88 priestorov namiesto 10. Používame **výhradne**
  ``ifcopenshell.util.schema.reassign_class``, ktorý entitu len premenuje
  a zachová ``id()``; navyše prvok od typu pred prepisom odpojíme.
* atribúty sa čítajú **pred** zápisom, iteruje sa cez ``list(...)``.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

import ifcopenshell
import ifcopenshell.util.schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_final_v2.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v3_a.ifc")

DRY_RUN = True

# --- §5 návrh PredefinedType pre IfcWall ----------------------------------
WALL_PREDEFINED = {
    "SN07.01": "PARTITIONING",
    "SN07.02": "PARTITIONING",
    "SN07.03": "PARTITIONING",
    "SN07.04": "PARTITIONING",
    "SN07.05": "PARTITIONING",
    "SN02.01": "PARAPET",
    "SN02.02": "SHEAR",
    "SN02.03": "SHEAR",
    "SN05.01": "SOLIDWALL",
    "SN11.01": "PARTITIONING",
    "SN11.02": "PARTITIONING",
}

# occurrence sa volá SN07.01, typ tiež SN07.01 — mapovanie platí pre oboje


class Report:
    """Zbiera „pred → po" pre výpis a pre kontrolu idempotencie."""

    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def add(self, polozka, kod, co, pred, po, n):
        self.rows.append((polozka, kod, co, str(pred), str(po), n))

    def table(self) -> str:
        if not self.rows:
            return "  (žiadna zmena — model je už v cieľovom stave)"
        w = [max(len(str(r[i])) for r in self.rows) for i in range(5)]
        out = []
        head = ("register", "kód", "čo", "pred", "po")
        w = [max(w[i], len(head[i])) for i in range(5)]
        out.append("  %-*s  %-*s  %-*s  %-*s  %-*s  %5s"
                   % (w[0], head[0], w[1], head[1], w[2], head[2],
                      w[3], head[3], w[4], head[4], "ks"))
        out.append("  " + "-" * (sum(w) + 18))
        for r in self.rows:
            out.append("  %-*s  %-*s  %-*s  %-*s  %-*s  %5d"
                       % (w[0], r[0], w[1], r[1], w[2], r[2],
                          w[3], r[3], w[4], r[4], r[5]))
        return "\n".join(out)

    @property
    def total(self) -> int:
        return sum(r[5] for r in self.rows)


def type_of(occ):
    return occ.IsTypedBy[0].RelatingType if occ.IsTypedBy else None


def reassign_with_type(model, occurrences, type_entity, new_occ_class, new_type_class):
    """Prepíše triedu occurrences aj ich typu, s odpojením od typu.

    Vráti ``(nové_occurrences, nový_typ)``. ``id()`` sa zachovávajú, takže
    všetky odkazy vrátane ``IfcRelDefinesByType`` držia a **GlobalId sa
    nemenia** — invariant 3 preto nehlási nič.
    """
    occ_ids = [o.id() for o in occurrences]
    type_id = type_entity.id() if type_entity is not None else None

    rel = None
    saved: list[int] = []
    if type_entity is not None and type_entity.Types:
        rel = type_entity.Types[0]
        saved = [o.id() for o in rel.RelatedObjects]
        cudzie = set(saved) - set(occ_ids)
        if cudzie:
            raise SystemExit(
                "STOP: typ #%d %r je zdieľaný aj s occurrences mimo rozsahu: %s"
                % (type_id, type_entity.Name, sorted(cudzie))
            )
        # odpojiť pred zmenou triedy (CLAUDE_CODE_START.md § Pravidlá)
        rel.RelatedObjects = ()

    for oid in occ_ids:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(oid), new_occ_class)
    if type_id is not None:
        ifcopenshell.util.schema.reassign_class(
            model, model.by_id(type_id), new_type_class
        )

    if rel is not None:
        rel = model.by_id(rel.id())
        rel.RelatedObjects = tuple(model.by_id(i) for i in saved)

    return ([model.by_id(i) for i in occ_ids],
            model.by_id(type_id) if type_id is not None else None)


def set_predefined(entity, value) -> bool:
    """Nastaví ``PredefinedType``, vráti či sa reálne zmenil."""
    if entity.PredefinedType == value:
        return False
    entity.PredefinedType = value
    return True


def set_attr(entity, attr, value) -> bool:
    if getattr(entity, attr) == value:
        return False
    setattr(entity, attr, value)
    return True


# ==========================================================================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="zapíše výstup")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = DRY_RUN and not args.apply

    print("vstup :", args.src)
    print("výstup:", args.dst, "(DRY-RUN, nezapisuje sa)" if dry else "")
    print()

    m = ifcopenshell.open(args.src)
    rep = Report()

    # ---- A · #AL / rozhodnutie 8 — IH01 → IfcCovering / MEMBRANE ---------
    ih_occ = [e for e in list(m.by_type("IfcWall")) if e.Name == "IH01.01"]
    ih_typ = [t for t in list(m.by_type("IfcWallType")) if t.Name == "IH01"]
    if ih_occ or ih_typ:
        t = ih_typ[0] if ih_typ else type_of(ih_occ[0])
        pred_t = "%s/%s" % (t.is_a(), t.PredefinedType) if t else "—"
        occ, t = reassign_with_type(m, ih_occ, t, "IfcCovering", "IfcCoveringType")
        n = sum(set_predefined(o, "MEMBRANE") for o in occ)
        if t is not None:
            set_predefined(t, "MEMBRANE")
            rep.add("#AL", "IH01", "typ", pred_t, "IfcCoveringType/MEMBRANE", 1)
        rep.add("#AL", "IH01.01", "occurrence", "IfcWall/NOTDEFINED",
                "IfcCovering/MEMBRANE", len(occ))
        del n

    # ---- B · #AB / rozhodnutie 12 — základový blok -----------------------
    blok = [e for e in list(m.by_type("IfcStair")) if e.Name == "ZD02.01"]
    if blok:
        t = type_of(blok[0])
        pred_t = "%s %r" % (t.is_a(), t.Name) if t else "—"
        occ, t = reassign_with_type(m, blok, t, "IfcFooting", "IfcFootingType")
        for o in occ:
            set_predefined(o, "PAD_FOOTING")
            set_attr(o, "Name", "ZD02.05")
            set_attr(o, "Description", "Základový blok pod schodiskom")
        if t is not None:
            set_predefined(t, "PAD_FOOTING")
            set_attr(t, "Name", "ZD02.05")
            rep.add("#AB", "ZD02.01", "typ", pred_t, "IfcFootingType 'ZD02.05'", 1)
        rep.add("#AB", "ZD02.01", "occurrence", "IfcStair/NOTDEFINED",
                "IfcFooting 'ZD02.05'/PAD_FOOTING", len(occ))

    # ---- C · #AC / rozhodnutie 12 — základové dosky ----------------------
    t404 = [t for t in list(m.by_type("IfcSlabType")) if t.Name == "ZD02.04"]
    if t404:
        t = t404[0]
        pred = "%s/%s" % (t.Name, t.PredefinedType)
        set_attr(t, "Name", "ZD02.01")
        set_predefined(t, "BASESLAB")
        rep.add("#AC", "ZD02.04", "typ (premenovaný)", pred, "ZD02.01/BASESLAB", 1)

    t403 = [t for t in list(m.by_type("IfcSlabType")) if t.Name == "ZD02.03"]
    for t in t403:
        pred = t.PredefinedType
        if set_predefined(t, "BASESLAB"):
            rep.add("#AC", "ZD02.03", "typ", pred, "BASESLAB", 1)

    # occurrences oboch typov: doska ZD02.01 (1×) a ZD02.02 z typu ZD02.03 (2×)
    for tname, label in (("ZD02.01", "ZD02.01"), ("ZD02.03", "ZD02.03")):
        typ = [t for t in list(m.by_type("IfcSlabType")) if t.Name == tname]
        for t in typ:
            occs = [o for r in t.Types for o in r.RelatedObjects]
            changed = collections.Counter()
            for o in occs:
                pred = o.PredefinedType
                if set_predefined(o, "BASESLAB"):
                    changed[pred] += 1
            for pred, n in changed.items():
                rep.add("#AC", label, "occurrence (typ %s)" % tname, pred, "BASESLAB", n)

    # ---- D · #AN / rozhodnutie 14 — KV01 → COPING ------------------------
    for cls, label in (("IfcCoveringType", "typ"), ("IfcCovering", "occurrence")):
        ents = [e for e in list(m.by_type(cls)) if e.Name == "KV01"]
        changed = collections.Counter()
        for e in ents:
            pred = e.PredefinedType
            if set_predefined(e, "COPING"):
                changed[pred] += 1
        for pred, n in changed.items():
            rep.add("#AN", "KV01", label, pred, "COPING", n)

    # ---- E · #AM / rozhodnutia 13, 15 — PredefinedType stien podľa §5 ----
    for cls, label in (("IfcWallType", "typ"), ("IfcWall", "occurrence")):
        changed = collections.defaultdict(collections.Counter)
        for e in list(m.by_type(cls)):
            target = WALL_PREDEFINED.get(e.Name)
            if target is None:
                continue
            pred = e.PredefinedType
            if set_predefined(e, target):
                changed[(e.Name, target)][pred] += 1
        for (name, target), preds in sorted(changed.items()):
            for pred, n in preds.items():
                rep.add("#AM", name, label, pred, target, n)

    # ---- výpis -----------------------------------------------------------
    print("PRED → PO")
    print(rep.table())
    print("\n  spolu dotknutých entít: %d" % rep.total)

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
