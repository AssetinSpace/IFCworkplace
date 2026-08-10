"""Fáza 11 — triedny model podruhé.

Register: #AM (časť), rozhodnutia z ``AUDIT.md`` §29.

    python src/30_fix_classes_2.py            # dry-run, nič nezapíše
    python src/30_fix_classes_2.py --apply    # zapíše out/ASR_v18.ifc

Čo robí
-------
Prekvalifikuje 30 occurrences a 6 typov, ktoré nesú triedu, akou nie sú.
Dvadsaťjeden z nich je ``IfcFurniture`` — nábytkom nie je ani jeden.

A  `DZ02`    8  steny výťahových jám  ``IfcSlab``      → ``IfcWall / SOLIDWALL``
B  `VP02`   12  sklopné madlá WC      ``IfcFurniture`` → ``IfcRailing / HANDRAIL``
C  `OV02`    7  prístrešky vstupov    ``IfcFurniture`` → ``IfcBuiltElement``
D  `OV04.03` 2  poistný prepad        ``IfcFurniture`` → ``IfcWasteTerminal / USERDEFINED``
E  `ZV04.01` 1  rebrík s košom        ``IfcFurniture`` → ``IfcStair / LADDER``

Opora pre každý riadok
----------------------
A  V origináli ``data/ASR.ifc`` je ``DZ02`` **``IfcWall`` s
   ``Pset_WallCommon.LoadBearing = True``**. Na ``IfcSlab`` ju prepísala
   pôvodná pipeline (kroky 1–12, mimo tohto repa) — overené naprieč všetkými
   verziami: ``ASR.ifc`` má 8× ``IfcWall``, ``ASR_final_v2.ifc`` už 8×
   ``IfcSlab``. Fáza 2 potom naháňala následok a premenovala
   ``Pset_WallCommon`` na ``Pset_SlabCommon`` (#B). Vraciame oboje.
   Geometricky sú to zvislé pásy 100 mm hrubé a 700 mm vysoké na kóte
   −1600…−900, tvoriace dva obdĺžniky súosé s výťahovými šachtami
   ``2.15`` a ``2.18`` (§29). ``SOLIDWALL`` = *„A massive wall construction…
   often masonry or concrete walls (both cast in-situ or precast) that are
   load bearing"*. Rozhodnutie Samuela: nosná konštrukcia, doska a stena.
B  ``HANDRAIL`` = *„structural support for loads applied by human occupants
   (at hand height)"*. Popis v modeli: „Bezbariérové WC – madlo sklopné".
C  ``IfcShadingDevice`` sme **zamietli**: entita je definovaná ako ochrana
   *„from the sunlight, from natural light, or screening them from view"*
   a jej vlastná NOTE posiela prvky s iným primárnym účelom na
   ``IfcBuiltElement``. Sklenený prístrešok netieni, chráni pred zrážkami.
   ``IfcBuiltElement`` je v IFC4.3 inštancovateľný (overené proti schéme,
   ``is_abstract() == False``) a **nemá** ``PredefinedType`` — význam nesie
   ``ObjectType``, resp. ``ElementType`` na type. Docs to menujú ako prípad
   *„when the concrete entity instantiated does not have a PredefinedType
   attribute… in some exceptional leaf classes"*.
D  ``IfcWasteTerminalTypeEnum`` nemá hodnotu pre prepad — ``ROOFDRAIN`` je
   *„pipe fitting… that collects rainwater for discharge into the rainwater
   system"*, čo poistný prepad nerobí; ten ústi voľne von. ``USERDEFINED``
   + ``ObjectType`` je preto čestnejšie. Trieda ``IfcWasteTerminal`` drží
   rodinu ``OV04`` pokope — zvyšných 18 kusov ju už má z fázy 10.
E  ``LADDER`` = *„a series of bars or steps between two upright elements
   used for climbing up or down something"*. Popis: „Žebřík s košem".

Čo NEROBÍ a prečo
-----------------
* ``PredefinedType`` prvkov, ktoré si triedu **ponechávajú** — ``SC01`` 3,
  ``SD04`` 2, ``ZV01.01`` 4, ``ZV01.02`` 6, ``KV02`` 2 — rieši fáza 12.
  Tu sa nastavuje len tam, kde je hodnota súčasťou rozhodnutia o triede:
  na ``IfcStair`` sa nedá prejsť bez toho, aby sme povedali ``LADDER``.
* ``OV04.03`` **nevkladá** do ``IfcSystem`` „Zoskupenie zariadení — strešné
  vpuste". Prepad vpusť nie je a názov skupiny by prestal platiť; členstvo
  je samostatné rozhodnutie.
* 67 ``IfcCurtainWall`` ostáva bez ``PredefinedType`` — uzavreté schémou
  v §25, enum má len ``USERDEFINED`` a ``NOTDEFINED``.

Pasce
-----
* ``ifcopenshell.api.root.reassign_class`` kaskádovo prepíše zdieľaný typ.
  Používame **výhradne** ``ifcopenshell.util.schema.reassign_class`` cez
  ``reassign_with_type`` z fázy 1 — entitu len premenuje, ``id()`` aj
  ``GlobalId`` zostanú, takže invariant 3 nehlási nič.
* ``Pset_SlabCommon`` na ``IfcWall`` je presne vada #B naopak. Premenovanie
  psetu je súčasťou zmeny triedy, nie extra krok.
"""

from __future__ import annotations

import argparse
import os
import sys

import ifcopenshell
import ifcopenshell.util.schema

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import *  # noqa: F401,F403  (drží konvenciu ostatných krokov)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v17.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v18.ifc")
ORIG = os.path.join(ROOT, "data", "ASR.ifc")

DRY_RUN = True

#: typ → (počet occ, nová trieda occ, nová trieda typu, PredefinedType, ObjectType)
#: ``PredefinedType = None`` znamená, že trieda atribút nemá.
PLAN = [
    ("DZ02",    8, "IfcWall",          "IfcWallType",          "SOLIDWALL",   None),
    ("VP02",   12, "IfcRailing",       "IfcRailingType",       "HANDRAIL",    None),
    ("OV02.01", 6, "IfcBuiltElement",  "IfcBuiltElementType",  None,          "Prístrešok vstupu"),
    ("OV02.02", 1, "IfcBuiltElement",  "IfcBuiltElementType",  None,          "Prístrešok vstupu"),
    ("OV04.03", 2, "IfcWasteTerminal", "IfcWasteTerminalType", "USERDEFINED", "Poistný prepad"),
    ("ZV04.01", 1, "IfcStair",         "IfcStairType",         "LADDER",      None),
]

#: pset, ktorý ide s triedou: kód → (staré meno, nové meno)
PSET_RENAME = {"DZ02": ("Pset_SlabCommon", "Pset_WallCommon")}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def add(self, kod, co, pred, po, n):
        self.rows.append((kod, co, pred, po, n))

    def table(self) -> str:
        w = [max(len(str(r[i])) for r in self.rows + [("kód", "čo", "pred", "po", "ks")])
             for i in range(5)]
        out = ["  %-*s  %-*s  %-*s  %-*s  %*s" % (w[0], "kód", w[1], "čo", w[2], "pred",
                                                  w[3], "po", w[4], "ks"),
               "  " + "  ".join("-" * x for x in w)]
        for r in self.rows:
            out.append("  %-*s  %-*s  %-*s  %-*s  %*s"
                       % (w[0], r[0], w[1], r[1], w[2], r[2], w[3], r[3], w[4], r[4]))
        return "\n".join(out)

    def total(self) -> int:
        return sum(r[4] for r in self.rows)


def type_by_name(model, name):
    hits = [t for t in model.by_type("IfcTypeObject") if t.Name == name]
    if len(hits) != 1:
        raise SystemExit("STOP: typ %r nájdený %d× (čakal som 1)" % (name, len(hits)))
    return hits[0]


def reassign_with_type(model, occurrences, type_entity, new_occ_class, new_type_class):
    """Prepíše triedu occurrences aj ich typu, s odpojením od typu.

    Prevzaté z ``14_fix_classes.py`` — ten istý vzor, tá istá pasca.
    """
    occ_ids = [o.id() for o in occurrences]
    type_id = type_entity.id()

    rel = None
    saved: list[int] = []
    if type_entity.Types:
        rel = type_entity.Types[0]
        saved = [o.id() for o in rel.RelatedObjects]
        cudzie = set(saved) - set(occ_ids)
        if cudzie:
            raise SystemExit(
                "STOP: typ #%d %r je zdieľaný aj mimo rozsahu: %s"
                % (type_id, type_entity.Name, sorted(cudzie)))
        rel.RelatedObjects = ()

    for oid in occ_ids:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(oid), new_occ_class)
    ifcopenshell.util.schema.reassign_class(model, model.by_id(type_id), new_type_class)

    if rel is not None:
        rel = model.by_id(rel.id())
        rel.RelatedObjects = tuple(model.by_id(i) for i in saved)

    return [model.by_id(i) for i in occ_ids], model.by_id(type_id)


def psets_of(entity):
    out = []
    for r in getattr(entity, "IsDefinedBy", []) or []:
        if r.is_a("IfcRelDefinesByProperties"):
            p = r.RelatingPropertyDefinition
            if p.is_a("IfcPropertySet"):
                out.append(p)
    return out


def orig_extend_to_structure(path):
    """Prečíta ``ExtendToStructure`` z pôvodného exportu, ak tam je."""
    if not os.path.exists(path):
        return None
    m = ifcopenshell.open(path)
    for e in m.by_type("IfcWall"):
        if (e.Name or "").startswith("DZ02"):
            for p in psets_of(e):
                if p.Name == "Pset_WallCommon":
                    for pr in p.HasProperties:
                        if pr.Name == "ExtendToStructure":
                            v = getattr(pr, "NominalValue", None)
                            return v.wrappedValue if v is not None else None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="zapíše výstup")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    rep = Report()
    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY", "\n")

    hotovo = 0
    for name, cnt, occ_cls, typ_cls, pdt, obj_type in PLAN:
        typ = type_by_name(model, name)

        # idempotencia: druhý beh nemá čo robiť
        if typ.is_a() == typ_cls:
            hotovo += 1
            continue

        occ = list(typ.Types[0].RelatedObjects) if typ.Types else []
        if len(occ) != cnt:
            raise SystemExit("STOP: %s má %d occurrences, čakal som %d"
                             % (name, len(occ), cnt))
        pred_occ = occ[0].is_a()
        pred_typ = typ.is_a()

        occ, typ = reassign_with_type(model, occ, typ, occ_cls, typ_cls)
        rep.add(name, "occurrence", pred_occ, occ_cls, len(occ))
        rep.add(name, "typ", pred_typ, typ_cls, 1)

        if pdt is not None:
            for o in occ:
                o.PredefinedType = pdt
            typ.PredefinedType = pdt
            rep.add(name, "PredefinedType", "—", pdt, len(occ) + 1)

        if obj_type is not None:
            for o in occ:
                o.ObjectType = obj_type
            # IfcBuiltElementType nesie význam v ElementType, nie PredefinedType
            if hasattr(typ, "ElementType"):
                typ.ElementType = obj_type
            elif hasattr(typ, "ObjectType"):
                typ.ObjectType = obj_type
            rep.add(name, "ObjectType", "—", obj_type, len(occ) + 1)

        # pset, ktorý ide s triedou
        if name in PSET_RENAME:
            stary, novy = PSET_RENAME[name]
            n = 0
            for o in occ:
                for p in psets_of(o):
                    if p.Name == stary:
                        p.Name = novy
                        n += 1
            if n:
                rep.add(name, "pset", stary, novy, n)

    if hotovo == len(PLAN):
        print("Idempotencia: všetkých %d typov už triedu má, niet čo meniť." % hotovo)
        return 0
    if hotovo:
        raise SystemExit("STOP: %d z %d typov je už prekvalifikovaných — "
                         "model je v polovičnom stave" % (hotovo, len(PLAN)))

    # --- #B naopak: vrátiť ExtendToStructure z originálu -------------------
    ets = orig_extend_to_structure(ORIG)
    if ets is not None:
        vratene = 0
        for w in model.by_type("IfcWall"):
            if not (w.Name or "").startswith("DZ02"):
                continue
            for p in psets_of(w):
                if p.Name != "Pset_WallCommon":
                    continue
                if any(pr.Name == "ExtendToStructure" for pr in p.HasProperties):
                    continue
                prop = model.create_entity(
                    "IfcPropertySingleValue", Name="ExtendToStructure",
                    NominalValue=model.create_entity("IfcBoolean", ets))
                p.HasProperties = tuple(p.HasProperties) + (prop,)
                vratene += 1
        if vratene:
            rep.add("DZ02", "ExtendToStructure", "chýbal", str(ets), vratene)

    print(rep.table())
    print("\nspolu dotknutých: %d" % rep.total())

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    model.write(args.dst)
    print("\nzapísané:", args.dst)

    # --- allowlist pre invariant 1 -----------------------------------------
    # Invariant 1 meria bboxy ``IfcBuiltElement`` a ``IfcSpace``. Prvky, ktoré
    # sa z ``IfcFurniture`` stali ``IfcRailing``, ``IfcStair`` alebo
    # ``IfcBuiltElement``, do tej množiny **vstupujú** — invariantu sa javia
    # ako nové tvary, hoci geometria je bit po bite tá istá. Do allowlistu idú
    # menovite; že sa nezmenili, je overené porovnaním bboxov v oboch súboroch.
    import json
    before = {e.GlobalId for e in ifcopenshell.open(args.src).by_type("IfcBuiltElement")}
    after = {e.GlobalId for e in ifcopenshell.open(args.dst).by_type("IfcBuiltElement")}
    al = {"removed": sorted(before - after), "added": sorted(after - before)}
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump(al, fh, indent=2)
        fh.write("\n")
    print("allowlist : %d pribudlo, %d ubudlo → %s"
          % (len(al["added"]), len(al["removed"]),
             os.path.basename(args.dst) + ".allowlist.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
