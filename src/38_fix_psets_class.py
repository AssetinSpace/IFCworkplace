"""Fáza 19 — #BC, #BD, #BE, #BF: psety a ``Qto`` na správnu triedu.

    python src/38_fix_psets_class.py                     # dry-run
    python src/38_fix_psets_class.py --apply             # zapíše out/ASR_v26.ifc
    python src/38_fix_psets_class.py --surplus drop      # cesta (a) z §39
    python src/38_fix_psets_class.py --drop-tool-trace   # aj #BG

Nález opravuje ``src/probe_psets.py`` (§39). Poradie operácií je
zámerné: **B, C, D, A** — B zjednotí názvoslovie veličín skôr, než ich
A presúva, a C odstráni duplicitu skôr, než by ju A odniesla do
prebytkovej sady.

A · #BC — 251 psetov a Qto na triede, ktorá ich nepripúšťa
-----------------------------------------------------------
Pset sa premenuje na ten, ktorý trieda pripúšťa; čo cieľová šablóna
nepozná, je **prebytok**. Precedens #B (``16_fix_psets.py``) hovorí
prebytok zahodiť — tu sa to nedá, lebo prebytok nie je Revitový zvyšok,
ale plné zloženie skladieb, sklon strechy, ``ProjectedArea`` a
prenajímateľné plochy (§39). Preto ``--surplus keep`` (default): prebytok
ide do sady s **vlastným menom bez vyhradenej predpony**, ako to pre
neštandardné sady predpisuje ``lexical/IfcPropertySet.html``:

    Property sets that are not declared as part of the IFC specification
    shall have a Name value not including the "Pset_" prefix.

``--surplus drop`` je cesta (a) zo §39 — čistejšia schéma, menej údajov.

Jediná výnimka, ktorá sa maže vždy: ``Pset_StairCommon`` na ``ZD02.05``
(#AB). Nesie ``IsExternal = False``, ``NosingLength = 0``,
``NumberOfRiser = 0``, ``NumberOfTreads = 0`` — nuly po ``IfcStair``,
a ``Pset_FootingCommon`` z nich nepozná ani jednu.

B · #BD — 128× ``GrossFootprintArea`` → ``GrossFootPrintArea``
C · #BE — 72 duplicitných veličín von z ``Qto_BodyGeometryValidation``
D · #BF — ``PanelOperation`` na ``IfcPropertyEnumeratedValue``;
          ``PanelPosition`` sa vypúšťa, lebo jeho jediná hodnota
          ``NOTDEFINED`` v ``PEnum_DoorPanelPositionEnum`` nie je
          (``--panel-position unset`` ju namiesto toho prepíše na ``UNSET``)
E · #BG — stopa nástroja; **len s ``--drop-tool-trace``**, lebo je to zmazanie

Čo skript overuje, kým niečo zmení
----------------------------------
* žiadna dotknutá definícia psetu nemá viac než jedného vlastníka
  (odmerané: 251 z 251 má práve jedného) — inak by premenovanie zasiahlo
  aj prvok, ktorého sa netýka;
* cieľové meno na vlastníkovi ešte nie je obsadené;
* pri C sa veličina odstráni, len keď je **tá istá entita** doložene aj
  v inej ``IfcElementQuantity`` — porovnáva sa ``id()``, nie hodnota;
* pri D je vlastnosť práve v jednom psete;
* prázdna sada sa nezapíše — ``HasProperties`` aj ``Quantities`` sú
  ``SET [1:?]``, takže sada bez členov sa maže celá.

Ktorákoľvek z týchto kontrol skript zastaví. Radšej nespraviť nič než
spraviť to potichu zle.

Pasce
-----
``IfcProperty`` je v modeli **zdieľaná medzi psetmi** — jedna sedí
v 1662 sadách. Nič sa preto nemaže priamo; z ``HasProperties`` sa len
vyberie a osirelé pozametá ``ifcutil.sweep_orphans``. To isté pri
``IfcPhysicalQuantity``: 144 ich je v dvoch ``Qto`` naraz.

``IfcProperty`` nemá v IFC4.3 ``Description``, ale ``Specification``.
Prebytkové vlastnosti sa preto presúvajú **ako entity**, nepíšu sa nanovo.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

import ifcopenshell
import ifcopenshell.guid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ifcutil  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v25.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v26.ifc")

LEX = os.environ.get("IFC_DOCS", "/workspace/bs-output/IFC/RELEASE/IFC4_3/lexical")
PSD_ZIP = os.path.join(os.path.dirname(LEX), "annex-a-psd.zip")

# (meno psetu, trieda vlastníka) → meno, ktoré tá trieda pripúšťa.
# None = štandardný cieľ pre túto triedu neexistuje, celý obsah je prebytok.
MAP = {
    ("Pset_RoofCommon", "IfcCovering"): "Pset_CoveringCommon",
    ("Pset_RoofCommon", "IfcCoveringType"): "Pset_CoveringCommon",
    ("Pset_SlabCommon", "IfcCovering"): "Pset_CoveringCommon",
    ("Pset_SlabCommon", "IfcCoveringType"): "Pset_CoveringCommon",
    ("Pset_WallCommon", "IfcCoveringType"): "Pset_CoveringCommon",
    ("Pset_ReinforcementBarPitchOfSlab", "IfcCoveringType"): None,
    ("Pset_ReinforcementBarPitchOfWall", "IfcCoveringType"): None,
    ("Qto_RoofBaseQuantities", "IfcCovering"): "Qto_CoveringBaseQuantities",
    ("Qto_SlabBaseQuantities", "IfcCovering"): "Qto_CoveringBaseQuantities",
    ("Qto_WallBaseQuantities", "IfcCovering"): "Qto_CoveringBaseQuantities",
    ("Qto_WallBaseQuantities", "IfcSlab"): "Qto_SlabBaseQuantities",
    ("Qto_SpaceBaseQuantities", "IfcSpatialZone"): "Qto_SpatialZoneBaseQuantities",
}

# Maže sa vždy, aj pri --surplus keep. Dôvod v §39: samé nuly po IfcStair.
ZMAZAT_BEZ_STRATY = {
    ("Pset_StairCommon", "IfcFooting"),
    ("Pset_StairCommon", "IfcFootingType"),
}

PREFIX = "SNIM_"


def sablony():
    """Mená vlastností každej šablóny z publikovaných docs."""
    out = {}
    with zipfile.ZipFile(PSD_ZIP) as z:
        for info in z.infolist():
            if not info.filename.endswith(".xml"):
                continue
            r = ET.fromstring(z.read(info.filename))
            name = (r.findtext("Name") or "").strip()
            if not name:
                continue
            out[name] = {(d.findtext("Name") or "").strip()
                         for d in list(r.iter("PropertyDef")) + list(r.iter("QtoDef"))}
    return out


def enum_hodnoty(pset, prop):
    """Povolené hodnoty enumerácie pre jednu vlastnosť šablóny."""
    with zipfile.ZipFile(PSD_ZIP) as z:
        r = ET.fromstring(z.read(pset + ".xml"))
    for pd in r.iter("PropertyDef"):
        if (pd.findtext("Name") or "").strip() != prop:
            continue
        el = pd.find(".//EnumList")
        if el is not None:
            return el.get("name"), [e.text for e in el]
    return None, []


def cleny(pdef):
    if pdef.is_a("IfcPropertySet"):
        return list(pdef.HasProperties or []), "HasProperties"
    if pdef.is_a("IfcElementQuantity"):
        return list(pdef.Quantities or []), "Quantities"
    return [], ""


def psety_vlastnika(obj):
    out = []
    for r in getattr(obj, "IsDefinedBy", None) or []:
        if r.is_a("IfcRelDefinesByProperties") and r.RelatingPropertyDefinition:
            out.append(r.RelatingPropertyDefinition)
    out += list(getattr(obj, "HasPropertySets", None) or [])
    return out


def vlastnici(model, pdef):
    """Všetci, čo tú definíciu nesú — oboma cestami."""
    out = []
    for r in model.get_inverse(pdef):
        if r.is_a("IfcRelDefinesByProperties"):
            out += list(r.RelatedObjects or [])
    for t in model.by_type("IfcTypeObject"):
        if pdef in (t.HasPropertySets or []):
            out.append(t)
    return out


def odpoj(model, pdef, owner, removed):
    """Odoberie definíciu od vlastníka. Vráti ju na zametenie."""
    if owner.is_a("IfcTypeObject") and pdef in (owner.HasPropertySets or []):
        zvysok = [p for p in owner.HasPropertySets if p.id() != pdef.id()]
        # HasPropertySets je OPTIONAL SET [1:?] — prázdna množina by bola
        # porušenie schémy, správne je atribút nenastaviť vôbec
        owner.HasPropertySets = tuple(zvysok) if zvysok else None
    for r in list(model.get_inverse(pdef)):
        if not r.is_a("IfcRelDefinesByProperties"):
            continue
        zvysok = [o for o in (r.RelatedObjects or []) if o.id() != owner.id()]
        if zvysok:
            r.RelatedObjects = tuple(zvysok)
        else:
            if getattr(r, "GlobalId", None):
                removed.append(r.GlobalId)
            model.remove(r)


def pripoj(model, pdef, owner, added):
    """Pripojí definíciu vlastníkovi cestou, ktorú schéma pre neho pripúšťa."""
    if owner.is_a("IfcTypeObject"):
        # WR NoRelatedTypeObject zakazuje typ v IfcRelDefinesByProperties
        owner.HasPropertySets = tuple(list(owner.HasPropertySets or []) + [pdef])
        return
    gid = ifcopenshell.guid.new()
    model.create_entity(
        "IfcRelDefinesByProperties", GlobalId=gid,
        OwnerHistory=owner.OwnerHistory, RelatedObjects=[owner],
        RelatingPropertyDefinition=pdef)
    added.append(gid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--surplus", choices=("keep", "drop"), default="keep")
    ap.add_argument("--panel-position", choices=("drop", "unset"), default="drop")
    ap.add_argument("--drop-tool-trace", action="store_true")
    args = ap.parse_args()
    dry = not args.apply

    tpl = sablony()
    model = ifcopenshell.open(args.src)
    print("vstup    :", args.src)
    print("prebytok :", args.surplus, " PanelPosition:", args.panel_position)
    print()

    removed: list = []
    added: list = []
    candidates: list = []
    dead: set = set()
    log = collections.Counter()

    # ---------- B · #BD ----------------------------------------------------
    zle, ok = 0, 0
    for q in model.by_type("IfcElementQuantity"):
        if q.Name != "Qto_WallBaseQuantities":
            continue
        for x in q.Quantities or []:
            if x.Name != "GrossFootprintArea":
                continue
            sady = [i for i in model.get_inverse(x)
                    if i.is_a("IfcElementQuantity")]
            if len(sady) != 1:
                zle += 1
                continue
            if not dry:
                x.Name = "GrossFootPrintArea"
            ok += 1
    if zle:
        sys.exit("B: %d veličín GrossFootprintArea je v inej sade naraz — "
                 "premenovanie by zasiahlo aj ju. Zastavené." % zle)
    log["B · GrossFootprintArea → GrossFootPrintArea"] = ok

    # ---------- C · #BE ----------------------------------------------------
    von, nedolozene = 0, 0
    for q in list(model.by_type("IfcElementQuantity")):
        if q.Name != "Qto_BodyGeometryValidation":
            continue
        drz = []
        for x in q.Quantities or []:
            if x.Name not in ("NetArea", "GrossArea"):
                drz.append(x)
                continue
            inde = [i for i in model.get_inverse(x)
                    if i.is_a("IfcElementQuantity") and i.id() != q.id()]
            if not inde:
                nedolozene += 1
                drz.append(x)
                continue
            von += 1
        if not dry and len(drz) != len(q.Quantities or []):
            q.Quantities = tuple(drz)
    if nedolozene:
        sys.exit("C: %d veličín nie je doložených v inej sade — zmazanie by "
                 "bola strata, nie deduplikácia. Zastavené." % nedolozene)
    log["C · duplicitné NetArea/GrossArea von z Qto_BodyGeometryValidation"] = von

    # ---------- D · #BF ----------------------------------------------------
    enum_meno, enum_ok = enum_hodnoty("Pset_DoorPanelProperties", "PanelOperation")
    poz_meno, poz_ok = enum_hodnoty("Pset_DoorPanelProperties", "PanelPosition")
    print("D · %s = %s" % (enum_meno, ", ".join(enum_ok)))
    print("D · %s = %s   ('NOTDEFINED' v nej nie je)" % (poz_meno, ", ".join(poz_ok)))
    enum_ent = {}
    prevod, vypustene, mimo = 0, 0, collections.Counter()
    for p in list(model.by_type("IfcPropertySet")):
        if p.Name != "Pset_DoorPanelProperties":
            continue
        drz = []
        for x in p.HasProperties or []:
            if not x.is_a("IfcPropertySingleValue") or x.Name not in (
                    "PanelOperation", "PanelPosition"):
                drz.append(x)
                continue
            if len([i for i in model.get_inverse(x)
                    if i.is_a("IfcPropertySet")]) != 1:
                sys.exit("D: %s je vo viacerých psetoch, výmena by zasiahla "
                         "aj ich. Zastavené." % x.Name)
            hod = x.NominalValue.wrappedValue if x.NominalValue else None
            meno, povolene = (enum_meno, enum_ok) if x.Name == "PanelOperation" \
                else (poz_meno, poz_ok)
            if hod not in povolene:
                mimo[(x.Name, hod)] += 1
                if x.Name == "PanelPosition" and args.panel_position == "drop":
                    candidates.append(x.id())
                    vypustene += 1
                    continue
                hod = "UNSET"
            if dry:
                drz.append(x)
                prevod += 1
                continue
            if meno not in enum_ent:
                enum_ent[meno] = model.create_entity(
                    "IfcPropertyEnumeration", Name=meno,
                    EnumerationValues=[model.create_entity("IfcLabel", v)
                                       for v in povolene])
            nova = model.create_entity(
                "IfcPropertyEnumeratedValue", Name=x.Name,
                EnumerationValues=[model.create_entity("IfcLabel", hod)],
                EnumerationReference=enum_ent[meno])
            drz.append(nova)
            candidates.append(x.id())
            prevod += 1
        if not dry:
            p.HasProperties = tuple(drz)
    log["D · PanelOperation/Position → IfcPropertyEnumeratedValue"] = prevod
    log["D · PanelPosition vypustené (hodnota mimo enumerácie)"] = vypustene

    # ---------- A · #BC ----------------------------------------------------
    plan = collections.defaultdict(list)   # vlastník → [(pdef, cieľ)]
    for pdef in model.by_type("IfcPropertySetDefinition"):
        if not pdef.Name:
            continue
        for o in vlastnici(model, pdef):
            key = (pdef.Name, o.is_a())
            if key in ZMAZAT_BEZ_STRATY or key in MAP:
                plan[o.id()].append((pdef, MAP.get(key), key))

    for oid, polozky in plan.items():
        for pdef, _, _ in polozky:
            if len(vlastnici(model, pdef)) != 1:
                sys.exit("A: %s má viac vlastníkov, premenovanie by zasiahlo "
                         "aj cudzí prvok. Zastavené." % pdef.Name)

    # Pred-kontrola: cieľové meno nesmie byť na vlastníkovi už obsadené.
    # Musí prebehnúť skôr, než sa čokoľvek zmení — inak by zastavenie
    # nechalo model rozrobený.
    for oid, polozky in sorted(plan.items()):
        owner = model.by_id(oid)
        zdrojove = {p.id() for p, _, _ in polozky}
        cudzie = {p.Name for p in psety_vlastnika(owner) if p.id() not in zdrojove}
        for _, ciel, _ in polozky:
            if ciel and ciel in cudzie:
                sys.exit("A: %s už nesie %s, premenovanie by ho zdvojilo. "
                         "Zastavené." % (owner.Name, ciel))

    premenovane = zmazane = prebytok_prop = prebytok_sad = 0
    for oid, polozky in sorted(plan.items()):
        owner = model.by_id(oid)
        zlucit = collections.defaultdict(list)   # cieľ → [členovia]
        prebytok = []
        zdroje = []
        for pdef, ciel, key in polozky:
            cl, _ = cleny(pdef)
            if key in ZMAZAT_BEZ_STRATY:
                zdroje.append([pdef, None])
                continue
            povolene = tpl.get(ciel, set()) if ciel else set()
            drzat = [x for x in cl if x.Name in povolene]
            zvysne = [x for x in cl if x.Name not in povolene]
            if drzat:
                zlucit[ciel] += drzat
            prebytok += [(pdef.Name, x) for x in zvysne]
            zdroje.append([pdef, ciel if drzat else None])

        # premenovanie / zlúčenie
        for ciel, cleny_ in zlucit.items():
            rovnake = [z for z in zdroje if z[1] == ciel]
            nositel = rovnake[0][0]
            # Zvyšné zdroje toho istého cieľa sa už premenovať nesmú —
            # ich členovia sú v `unik`. Prepnú sa na zmazanie, inak by
            # v modeli zostali pod pôvodným, nesprávnym menom.
            for z in rovnake[1:]:
                z[1] = None
            videne, unik = set(), []
            for x in cleny_:
                k = (x.Name, str(x[3]) if len(x) > 3 else "")
                if k in videne:
                    continue
                videne.add(k)
                unik.append(x)
            mien = collections.Counter(x.Name for x in unik)
            spor = [n for n, c in mien.items() if c > 1]
            if spor:
                sys.exit("A: %s — dva zdroje nesú %s s rôznou hodnotou. "
                         "Zastavené." % (owner.Name, ", ".join(spor)))
            if not dry:
                nositel.Name = ciel
                if nositel.is_a("IfcPropertySet"):
                    nositel.HasProperties = tuple(unik)
                else:
                    nositel.Quantities = tuple(unik)
            premenovane += 1
            zlucit[ciel] = unik

        # sady, z ktorých nič neprežilo (vrátane zlúčených zdrojov)
        drzane = {x.id() for cl in zlucit.values() for x in cl}
        for pdef, c in zdroje:
            if c is not None:
                continue
            if not dry:
                odpoj(model, pdef, owner, removed)
                if getattr(pdef, "GlobalId", None):
                    removed.append(pdef.GlobalId)
                # členov, ktorí prežili v zlúčenej sade, nezametať
                candidates += [x.id() for x in cleny(pdef)[0]
                               if x.id() not in drzane]
                model.remove(pdef)
            zmazane += 1

        # prebytok
        if prebytok and args.surplus == "keep":
            for trieda, meno in (("IfcPropertySet", PREFIX + "Properties"),
                                 ("IfcElementQuantity", PREFIX + "Quantities")):
                vyber = [(src, x) for src, x in prebytok
                         if (trieda == "IfcPropertySet") == x.is_a("IfcProperty")]
                if not vyber:
                    continue
                popis = "prebytok zo šablóny " + ", ".join(
                    sorted({s for s, _ in vyber}))
                prebytok_prop += len(vyber)
                prebytok_sad += 1
                if dry:
                    continue
                gid = ifcopenshell.guid.new()
                kw = {"GlobalId": gid, "OwnerHistory": owner.OwnerHistory,
                      "Name": meno, "Description": popis}
                if trieda == "IfcPropertySet":
                    kw["HasProperties"] = [x for _, x in vyber]
                else:
                    kw["Quantities"] = [x for _, x in vyber]
                nova = model.create_entity(trieda, **kw)
                added.append(gid)
                pripoj(model, nova, owner, added)
        elif prebytok:
            prebytok_prop += len(prebytok)
            if not dry:
                candidates += [x.id() for _, x in prebytok]

    log["A · premenovaných sád"] = premenovane
    log["A · zmazaných sád (nič neprežilo)"] = zmazane
    log["A · prebytkových vlastností %s" % args.surplus] = prebytok_prop
    log["A · nových prebytkových sád"] = prebytok_sad

    # ---------- E · #BG ----------------------------------------------------
    if args.drop_tool_trace:
        n = 0
        for p in list(model.by_type("IfcPropertySet")):
            if p.Name != "PEnum_AddressType":
                continue
            for o in vlastnici(model, p):
                if not dry:
                    odpoj(model, p, o, removed)
            if not dry:
                removed.append(p.GlobalId)
                candidates += [x.id() for x in (p.HasProperties or [])]
                model.remove(p)
            n += 1
        for a in list(model.by_type("IfcActor")):
            org = getattr(a, "TheActor", None)
            if org is not None and org.is_a("IfcOrganization") \
                    and org.Name == "IfcOpenShell":
                if not dry:
                    ifcutil.detach_object_from_rels(model, a, removed,
                                                    candidates, dead)
                    removed.append(a.GlobalId)
                    model.remove(a)
                n += 1
        log["E · zmazaná stopa nástroja (#BG)"] = n

    # ---------- výsledok ---------------------------------------------------
    for k in sorted(log):
        print("  %-62s %5d" % (k, log[k]))
    if mimo:
        print("\n  hodnoty mimo enumerácie:")
        for (n, v), c in mimo.most_common():
            print("    %4d  %-16s %s" % (c, n, v))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    zamet = ifcutil.sweep_orphans(model, candidates, removed, dead)
    print("\nzametené osirelé:", sum(zamet.values()),
          dict(zamet.most_common()) if zamet else "")
    model.write(args.dst)
    print("zapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": removed, "added": added}, fh, indent=2)
        fh.write("\n")
    print("allowlist: -%d GlobalId, +%d GlobalId" % (len(removed), len(added)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
