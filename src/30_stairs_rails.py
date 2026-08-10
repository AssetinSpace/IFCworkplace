"""Fáza 11 — schodiská, zábradlia, madlá a poistný prepad.

    python src/30_stairs_rails.py           # dry-run
    python src/30_stairs_rails.py --apply   # zapíše out/ASR_v18.ifc

Čo je schodisko a čo sú jeho časti
----------------------------------
Spec (`IfcStair`, 6.1.3.37.1): *„A stair is a vertical passageway allowing
occupants to walk (step) **from one floor level to another floor level**
at a different elevation. It may include a landing as an intermediate
floor slab."* a ďalej: *„The IfcStair shall either be represented as
a stair assembly entity that aggregates all parts (stair flight, landing,
etc.…), or as a single stair entity without decomposition… the aggregation
is handled by the IfcRelAggregates relationship, relating an IfcStair with
the related IfcStairFlight and landings, IfcSlab with PredefinedType=LANDING.
IfcRailing's belonging to the stair may also be included."*

Model tento vzor **už spĺňa** — nič sa neprestavuje:

* `SC01.0001` 1NP, `SC01.0002` 2NP, `SC01.0003` 3NP, každé je `IfcStair`
  bez vlastného tvaru, agregujúce 2 ramená + 2 podesty + 3 zábradlia,
* každé prekonáva práve jedno podlažie: 0→5000, 5000→9200, 9200→13400 mm,
  čo sedí s `Pset_StairCommon`: 30×166,667 = 5000 a 26×161,538 = 4200.

Preto sa **nerobí jeden `IfcStair` cez tri podlažia**. Nielenže by odporoval
definícii „from one floor level to another floor level", ale hlavne: časti
agregátu sa do priestorovej štruktúry neviažu samostatne (invariant 7),
takže by sa stratilo, že rameno patrí do 1NP, 2NP a 3NP — z troch údajov
by ostal jeden. To je vecná strata, nie formalita.

„Jedno schodisko" sa preto vyjadrí zoskupením, nie prestavbou hierarchie:
`IfcBuiltSystem` = *„a group by which built elements are grouped according
to a common function within the facility"*. `PredefinedType` je
`USERDEFINED` s `ObjectType`, lebo jediná blízka hodnota `TRANSPORT` je
v spec písaná o *transport elements* (výťahy, eskalátory) a model ani jeden
nemá — tvrdiť to by bolo nad rámec merania.

Strešné schodisko `SH04.03.0001` do zoskupenia nepatrí (Samuel: *„druhé
maličké schodisko je na streche ale to je iné"*) a `PredefinedType` už má.

HALF_TURN_STAIR sa nedosadzuje od oka
-------------------------------------
Rozdiel medzi `HALF_TURN_STAIR` (180° cez medzipodestu) a
`TWO_STRAIGHT_RUN_STAIR` (dve ramená za sebou, bez otočky) je merateľný:
pri otočke sú ramená **vedľa seba** — pôdorysné rozsahy sa v jednej osi
neprekrývajú a v druhej prekrývajú — a podesta leží na oboch. Pri priamom
behu sú ramená za sebou, teda naopak. Skript to overí a keď to nevyjde,
zastaví sa a nič nezapíše.

Zábradlie verzus madlo
----------------------
Rozlíšenie je v geometrii, nie v názve:

* `ZV01.01` — 290 mm široké, v zrkadle schodiska cez celú výšku ramien
  → `GUARDRAIL`: *„designed to guard human occupants from falling off
  a stair, ramp or landing where there is a vertical drop at the edge of
  such floors/landings"*.
* `ZV01.02` — 40 mm tenké, pri stene, stúpa rovnobežne s ramenom
  → `HANDRAIL`: *„structural support for loads applied by human occupants
  (at hand height)… floor or wall mounted"*.
* `KV02` — 40 mm, po oboch stranách oceľového strešného schodiska,
  stúpa presne s ramenom (791 mm na 791 mm) → `HANDRAIL`.
* `VP02` — 850×155 mm vo výške 590…810 mm nad podlahou, 12 ks po dvoch
  v šiestich hygienických miestnostiach; Revit typ *„Invalida Madlo
  Sklop"*, Samuel potvrdil: madlá na invalidnom WC → `IfcRailing/HANDRAIL`.
  `IfcFurniture` bolo z exportu, madlo nie je nábytok.

`ZV01.01.0004` je zábradlie pri otvore zrkadla v miestnosti 4.06, nie na
ramene. Zdieľa typ `ZV01.01`, a keďže typ nesie jednu hodnotu, dostáva
`GUARDRAIL` tiež — spec ju na *„floors/landings"* výslovne rozširuje.
Do zoskupenia schodiska nepatrí, patrí k podlahe 4.06.

Poistný prepad
--------------
`OV04.03` sú dve kocky 100×100×100 mm na atike 5NP. Samuel: *„je to proste
len špeciálna diera trubka v atike"*, zástupný prvok, na nič sa nenapája.
Model má štyri skutočné poistné prepady `OV04.02` (Revit *„Poistny
prepad"*) a tie sú z fázy 10 `IfcWasteTerminal/ROOFDRAIN`. `OV04.03`
dostáva to isté zaradenie — nie preto, že by 100 mm kocka bola vpusť, ale
preto, že je to ten istý druh prvku ako `OV04.02` a rozdiel je len v tom,
že tento je nakreslený zástupne. Že ide o zástupný tvar, hovorí
`Description`; `IfcWasteTerminalTypeEnum` hodnotu pre prepad nemá a to je
zapísané v BEP ako obmedzenie číselníka, nie ako vlastnosť budovy.

Čo skript **nerobí**
--------------------
Typ `SC01` nesie `Pset_StairCommon` s `NumberOfRiser = 0`,
`NumberOfTreads = 0` — nula z Revit šablóny, kým occurrences majú 30/26/26.
Je to nepravdivý údaj z exportu, ale mazať exportované vlastnosti je iný
druh zásahu než dopĺňať `PredefinedType`; ostáva v registri ako #BB.
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
IN = os.path.join(ROOT, "out", "ASR_v17.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v18.ifc")

DRY_RUN = True

#: prefix mena → (trieda occurrence, nový PredefinedType, čakaný počet)
#: Occurrence aj jej typ dostanú tú istú hodnotu.
PREDEF = {
    "SC01":    ("IfcStair", "HALF_TURN_STAIR", 3),
    "SD04":    ("IfcStairFlight", "STRAIGHT", 6),
    "ZV01.01": ("IfcRailing", "GUARDRAIL", 4),
    "ZV01.02": ("IfcRailing", "HANDRAIL", 6),
    "KV02":    ("IfcRailing", "HANDRAIL", 2),
}

#: prefix → (stará trieda, nová occurrence, nový typ, PredefinedType, počet)
RECLASS = {
    "VP02":    ("IfcFurniture", "IfcRailing", "IfcRailingType",
                "HANDRAIL", 12),
    "OV04.03": ("IfcFurniture", "IfcWasteTerminal", "IfcWasteTerminalType",
                "ROOFDRAIN", 2),
}

RECLASS_DESC = {
    "VP02": "Sklopné madlo na WC pre osoby s obmedzenou schopnosťou pohybu. "
            "Export ho niesol ako IfcFurniture; madlo nie je nábytok, je to "
            "opora vo výške ruky (590–810 mm nad podlahou), teda IfcRailing "
            "s PredefinedType HANDRAIL.",
    "OV04.03": "Poistný prepad v atike, v modeli zástupná kocka 100×100×100 mm "
               "bez napojenia. Zaradený zhodne s OV04.02 (Revit „Poistny "
               "prepad\"); IfcWasteTerminalTypeEnum hodnotu pre prepad nemá.",
}

SYS_NAME = "SC01"
SYS_OBJECTTYPE = "Vertikálna komunikácia — schodisko"
SYS_DESC = (
    "Hlavné schodisko 1NP–4NP ako jeden celok. Zoskupuje tri IfcStair, "
    "z ktorých každé podľa spec prekonáva jedno podlažie (0→5000, 5000→9200, "
    "9200→13400 mm). Zoskupenie, nie agregácia: časti agregátu sa do "
    "priestorovej štruktúry neviažu samostatne, takže by sa stratilo "
    "priradenie ramien k 1NP, 2NP a 3NP. Strešné schodisko SH04.03 sem "
    "nepatrí, je to samostatná konštrukcia.")

STAIRS = ("SC01.0001", "SC01.0002", "SC01.0003")


# --------------------------------------------------------------------------


def bboxes(model, products):
    """Svetové obálky v mm; ``create_shape`` vracia metre, súbor je v mm."""
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


#: zaokrúhlenie, na ktoré porovnáva invariant 1 (``BBOX_DECIMALS``)
DEC = 6


def in_inv1(elem) -> bool:
    """Meria invariant 1 tento prvok? Meria ``IfcBuiltElement`` a ``IfcSpace``."""
    return elem.is_a("IfcBuiltElement") or elem.is_a("IfcSpace")


def _prekryv(a, b, i):
    """Dĺžka prieniku obálok v osi ``i`` (0 = X, 1 = Y)."""
    return min(a[i + 3], b[i + 3]) - max(a[i], b[i])


def dokaz_pololomu(stair, box) -> str:
    """Vráti dôvod, prečo to **nie je** polootočka; prázdny reťazec = je.

    Rozlišovač: pri 180° otočke cez medzipodestu sú ramená vedľa seba —
    v jednej osi sa pôdorysne neprekrývajú, v kolmej áno — a podesta
    zasahuje do oboch. Pri ``TWO_STRAIGHT_RUN_STAIR`` je to naopak.
    """
    parts = []
    for r in (stair.IsDecomposedBy or ()):
        parts.extend(r.RelatedObjects)
    flights = [p for p in parts if p.is_a("IfcStairFlight")]
    landings = [p for p in parts if p.is_a("IfcSlab")
                and p.PredefinedType == "LANDING"]
    if len(flights) != 2:
        return "ramien %d, nie 2" % len(flights)
    if not landings:
        return "žiadna podesta IfcSlab/LANDING"
    a, b = (box.get(f.GlobalId) for f in flights)
    if a is None or b is None:
        return "rameno bez tvaru"

    # ramená vedľa seba: v jednej osi rozsahy oddelené, v druhej prekryté
    osi = [_prekryv(a, b, 0), _prekryv(a, b, 1)]
    vedla = sorted(osi)
    if not (vedla[0] <= 0.0 < vedla[1]):
        return ("ramená nie sú vedľa seba (prieniky X=%.0f Y=%.0f mm)"
                % (osi[0], osi[1]))

    # podesta musí siahať do oboch ramien v tej osi, v ktorej sú oddelené
    delici = 0 if osi[0] <= 0.0 else 1
    spolu = max(box[l.GlobalId] for l in landings if l.GlobalId in box)
    for l in landings:
        lb = box.get(l.GlobalId)
        if lb and _prekryv(lb, a, delici) > 0 and _prekryv(lb, b, delici) > 0:
            break
    else:
        return "žiadna podesta nesiaha do oboch ramien (naposledy %s)" % (spolu,)

    # a musí byť medzi nimi vo výške
    zl = max(box[l.GlobalId][5] for l in landings if l.GlobalId in box)
    if not (min(a[2], b[2]) < zl < max(a[5], b[5])):
        return "podesta nie je medzi ramenami vo výške"
    return ""


def reassign_with_type(model, occurrences, type_entity, new_occ, new_type):
    """Prepíše triedu occurrences aj typu; vzor z ``25_sanitary.py``.

    ``util.schema.reassign_class`` zachová ``id()`` aj ``GlobalId``; prvky
    sa od typu pred prepisom odpoja, inak sa vzťah rozpadne. Handle po
    prepise neplatí — pracuje sa cez ``id()``.
    """
    occ_ids = [o.id() for o in occurrences]
    type_id = type_entity.id() if type_entity is not None else None

    rel, saved = None, []
    if type_entity is not None and type_entity.Types:
        rel = type_entity.Types[0]
        saved = [o.id() for o in rel.RelatedObjects]
        cudzie = set(saved) - set(occ_ids)
        if cudzie:
            raise SystemExit("STOP: typ %r je zdieľaný aj mimo rozsahu: %s"
                             % (type_entity.Name, sorted(cudzie)))
        rel.RelatedObjects = ()

    for oid in occ_ids:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(oid), new_occ)
    if type_id is not None:
        ifcopenshell.util.schema.reassign_class(model, model.by_id(type_id), new_type)
    if rel is not None:
        model.by_id(rel.id()).RelatedObjects = tuple(model.by_id(i) for i in saved)

    return ([model.by_id(i) for i in occ_ids],
            model.by_id(type_id) if type_id is not None else None)


def occ_by_prefix(model, prefix):
    return sorted((e for e in model.by_type("IfcProduct")
                   if (e.Name or "").startswith(prefix)),
                  key=lambda e: e.Name)


def typ_of(elem):
    for r in (elem.IsTypedBy or ()):
        return r.RelatingType
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

    if any(g.Name == SYS_NAME for g in m.by_type("IfcBuiltSystem")):
        print("IfcBuiltSystem %r už existuje — skript je idempotentný, končí"
              % SYS_NAME)
        return 0

    # ---- 1. dôkaz polootočky pred akoukoľvek zmenou ---------------------
    print("SCHODISKO — tvar behu")
    stairs = [e for e in m.by_type("IfcStair") if e.Name in STAIRS]
    if len(stairs) != len(STAIRS):
        raise SystemExit("STOP: čakané %s, nájdené %s"
                         % (list(STAIRS), sorted(e.Name for e in stairs)))
    casti = []
    for s in stairs:
        for r in (s.IsDecomposedBy or ()):
            casti.extend(r.RelatedObjects)
    box = bboxes(m, casti)
    for s in stairs:
        chyba = dokaz_pololomu(s, box)
        if chyba:
            raise SystemExit("STOP: %s nevyzerá na polootočku — %s" % (s.Name, chyba))
        print("  %-10s 2 ramená vedľa seba, podesta na oboch → HALF_TURN_STAIR"
              % s.Name)

    # ---- 2. PredefinedType na existujúcich triedach ----------------------
    print("\nPREDEFINEDTYPE")
    for pref, (cls, pt, cnt) in sorted(PREDEF.items()):
        elems = [e for e in occ_by_prefix(m, pref) if e.is_a(cls)]
        if len(elems) != cnt:
            raise SystemExit("STOP: %s — čakaných %d %s, nájdených %d"
                             % (pref, cnt, cls, len(elems)))
        pred = collections.Counter(e.PredefinedType for e in elems)
        typy = {typ_of(e) for e in elems} - {None}
        for e in elems:
            e.PredefinedType = pt
        for t in typy:
            t.PredefinedType = pt
        print("  %-8s %2d× %-14s %-22s → %s  (typ: %s)"
              % (pref, len(elems), cls.replace("Ifc", ""),
                 dict(pred), pt, ", ".join(sorted(t.Name for t in typy)) or "—"))

    # ---- 3. zmena triedy ------------------------------------------------
    print("\nZMENA TRIEDY")
    rozsah: list[str] = []
    for pref, (stara, nova, novy_typ, pt, cnt) in sorted(RECLASS.items()):
        elems = [e for e in occ_by_prefix(m, pref) if e.is_a(stara)]
        if len(elems) != cnt:
            raise SystemExit("STOP: %s — čakaných %d %s, nájdených %d"
                             % (pref, cnt, stara, len(elems)))
        t = typ_of(elems[0])
        ine = {typ_of(e).Name if typ_of(e) else None for e in elems}
        if len(ine) != 1:
            raise SystemExit("STOP: %s má viac typov: %s" % (pref, sorted(ine)))
        pred_box = bboxes(m, elems)
        v_inv1 = {e.GlobalId for e in elems if in_inv1(e)}
        elems, t = reassign_with_type(m, elems, t, nova, novy_typ)
        for e in elems:
            e.PredefinedType = pt
            e.Description = RECLASS_DESC[pref]
        if t is not None:
            t.PredefinedType = pt
            t.Description = RECLASS_DESC[pref]

        # Zmena triedy môže prvok vpustiť do meraného súboru invariantu 1
        # alebo ho z neho vytiahnuť — inv 1 meria IfcBuiltElement a IfcSpace.
        # Nie je to zmena tvaru a nesmie sa ako zmena tvaru tváriť: tvar sa
        # premeria pred aj po a musí sedieť na tú istú desatinu ako inv 1.
        po_box = bboxes(m, elems)
        posun = [g for g, b in pred_box.items()
                 if tuple(round(x, DEC) for x in po_box.get(g, ())) !=
                 tuple(round(x, DEC) for x in b)]
        if posun:
            raise SystemExit("STOP: %s — zmena triedy pohla tvarom: %s"
                             % (pref, posun[:5]))
        prestup = sorted({e.GlobalId for e in elems if in_inv1(e)} ^ v_inv1)
        rozsah.extend(prestup)
        print("  %-8s %2d× %s → %s/%s   tvar zhodný, do rozsahu inv 1 %+d"
              % (pref, len(elems), stara.replace("Ifc", ""),
                 nova.replace("Ifc", ""), pt,
                 len(prestup) if in_inv1(elems[0]) else -len(prestup)))

    # ---- 4. zoskupenie „jedno schodisko" --------------------------------
    print("\nZOSKUPENIE")
    stairs = [e for e in m.by_type("IfcStair") if e.Name in STAIRS]
    owner = stairs[0].OwnerHistory
    budova = m.by_type("IfcBuilding")[0]
    sys = m.create_entity("IfcBuiltSystem", GlobalId=ifcopenshell.guid.new(),
                          OwnerHistory=owner, Name=SYS_NAME, Description=SYS_DESC,
                          ObjectType=SYS_OBJECTTYPE, PredefinedType="USERDEFINED")
    rel = m.create_entity("IfcRelAssignsToGroup",
                          GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                          RelatedObjects=tuple(stairs), RelatingGroup=sys)
    srv = m.create_entity("IfcRelServicesBuildings",
                          GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
                          RelatingSystem=sys, RelatedBuildings=(budova,))
    added.extend([sys.GlobalId, rel.GlobalId, srv.GlobalId])
    print("  IfcBuiltSystem %-6s USERDEFINED/%s" % (SYS_NAME, SYS_OBJECTTYPE))
    print("       členovia: %s" % ", ".join(e.Name for e in stairs))

    # ---- 5. kontrola výsledku, nie zámeru -------------------------------
    print("\nKONTROLA")
    zle = []
    for pref, (cls, pt, cnt) in sorted(PREDEF.items()):
        e = [x for x in occ_by_prefix(m, pref) if x.is_a(cls)]
        if len(e) != cnt or any(x.PredefinedType != pt for x in e):
            zle.append("%s: %d/%d s %s" % (pref, sum(1 for x in e
                                                     if x.PredefinedType == pt), cnt, pt))
    for pref, (stara, nova, novy_typ, pt, cnt) in sorted(RECLASS.items()):
        e = [x for x in occ_by_prefix(m, pref) if x.is_a(nova)]
        if len(e) != cnt or any(x.PredefinedType != pt for x in e):
            zle.append("%s: %d/%d ako %s/%s" % (pref, len(e), cnt, nova, pt))
        if [x for x in occ_by_prefix(m, pref) if x.is_a(stara)]:
            zle.append("%s: ostal aspoň jeden %s" % (pref, stara))
    if zle:
        raise SystemExit("STOP: kontrola zlyhala — %s" % "; ".join(zle))
    print("  všetky PredefinedType a triedy sedia")

    nab = m.by_type("IfcFurniture")
    print("  IfcFurniture v modeli: %d (%s)"
          % (len(nab), ", ".join(sorted({(x.Name or "?")[:4] for x in nab})) or "—"))

    siroty = [e for e in m if not m.get_total_inverses(e)
              and not any(e.is_a(w) for w in
                          ("IfcShapeAspect", "IfcMaterialDefinitionRepresentation",
                           "IfcPresentationLayerAssignment", "IfcMapConversion",
                           "IfcRelationship", "IfcRepresentationContext"))]
    if siroty:
        raise SystemExit("STOP: krok vyrobil %d osirelých entít" % len(siroty))
    print("  inv 4: 0 osirelých")
    print("  GlobalId nových: %d, odstránených: 0" % len(added))
    print("  prestup do rozsahu inv 1: %d (tvar overený zhodný)" % len(rozsah))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(added),
                   "scope": sorted(rozsah),
                   "scope_reason":
                       "Prvky, ktorým zmena triedy zmenila príslušnosť do "
                       "meraného súboru invariantu 1 (IfcBuiltElement + "
                       "IfcSpace). Tvar sa premeral pred aj po zmene a je "
                       "zhodný na 6 desatín mm — geometria sa nemenila, "
                       "zmenil sa rozsah merania."}, fh,
                  ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
