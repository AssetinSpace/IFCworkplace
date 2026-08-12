"""Sonda: nesie prvok len tie psety a ``Qto``, ktoré jeho trieda pripúšťa?
(**nič nemení**)

    python src/probe_psets.py                     # out/ASR_v25.ifc
    python src/probe_psets.py --in out/ASR_v24.ifc --show 40

Prečo
-----
``AUDIT.md`` §38 bod 1. Vada tejto povahy v modeli **preukázateľne bola**
(#A, #B, #E), ale opravila sa len tam, kde sa hľadala menovite. Fáza 11 to
ukázala načisto: ``DZ02`` niesla ``Qto_WallBaseQuantities`` tri fázy po sebe
ako odtlačok svojej pôvodnej triedy ``IfcWall`` a nikto si toho nevšimol.
Systematická kontrola „nesie prvok len to, čo jeho trieda pripúšťa" nikdy
nebežala. Toto je ona.

Zdroj pravdy
------------
Publikované docs buildingSMART, ``IFC/RELEASE/IFC4_3``:

* strojovo čitateľné ``annex-a-psd.zip`` — 760 definícií, každá nesie
  ``templatetype`` a ``ApplicableClasses``;
* ľudsky čitateľné ``lexical/<meno>.html`` — tá istá vec vetou.

Sonda **oba zdroje porovná** pre každý pset, ktorý v modeli naozaj je,
a nezhodu ohlási ako vlastný nález. Bez toho by tvrdila niečo o schéme
na základe jedného neovereného čítania — presne to, čo §8 zakazuje.

Čo meria
--------
1  meno    ``Pset_``/``Qto_`` je vyhradená predpona; meno mimo štandardu
           je buď preklep, alebo si žiada vlastnú predponu
2  trieda  vlastník musí byť podtypom niektorej ``ApplicableClasses``
3  nosič   ``Qto_*`` patrí do ``IfcElementQuantity``, ``Pset_*`` do
           ``IfcPropertySet``; ``PSET_MATERIALDRIVEN`` na prvok nepatrí vôbec
4  šablóna ``*_TYPEDRIVENONLY`` len na type, ``*_OCCURRENCEDRIVEN`` len na
           occurrence
5  vlastnosti  mená property/quantity musia byť v šablóne
6  dátové typy  ``IfcPropertySingleValue.NominalValue`` a druh ``IfcQuantity*``
           proti šablóne
7  PredefinedType  pri šablónach viazaných na konkrétnu hodnotu
           (``IfcActuator/ELECTRICACTUATOR``)

Kontroly 5–7 sú prísnejšie než „trieda pripúšťa pset" a v hlásení sú
oddelené, aby sa nález nedal zameniť s bodom 2.

Pasce, na ktoré sonda naráža
----------------------------
* ``IfcRelDefinesByProperties.RelatedObjects`` je síce
  ``SET [1:?] OF IfcObjectDefinition``, ale pravidlo ``NoRelatedTypeObject``
  z ``IFC4X3_DEV_60a6175.exp`` v ňom ``IfcTypeObject`` **zakazuje**::

      NoRelatedTypeObject : SIZEOF(QUERY(Types <* SELF\\IfcRelDefinesByProperties
          .RelatedObjects | 'IFC4X3_ADD2.IFCTYPEOBJECT' IN TYPEOF(Types))) = 0;

  Typ teda nesie psety **iba** cez ``HasPropertySets``. Zbierať sa preto
  musia obe cesty — inak by kontrola typy prehliadla. Dvojica
  (pset, vlastník) sa aj tak počíta raz, lebo zdieľaný pset visí na viacerých.
* Applicability sa v docs píše aj s ``PredefinedType`` za lomkou. Pre bod 2
  sa lomka odreže, hodnota sa kontroluje zvlášť v bode 7.
* Meno ``IfcElementQuantity``/``IfcPropertySet`` môže byť ``None``.
"""

from __future__ import annotations

import argparse
import collections
import glob
import html
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v25.ifc")

LEX = os.environ.get(
    "IFC_DOCS", "/workspace/bs-output/IFC/RELEASE/IFC4_3/lexical"
)
DOCS = os.path.dirname(LEX)
PSD_ZIP = os.path.join(DOCS, "annex-a-psd.zip")

# QtoType v šablóne → entita, ktorá tú veličinu v modeli nesie.
QTO_KIND = {
    "Q_LENGTH": "IfcQuantityLength",
    "Q_AREA": "IfcQuantityArea",
    "Q_VOLUME": "IfcQuantityVolume",
    "Q_COUNT": "IfcQuantityCount",
    "Q_WEIGHT": "IfcQuantityWeight",
    "Q_TIME": "IfcQuantityTime",
}

# PropertyType v šablóne → entita IfcProperty, ktorá ju v modeli nesie.
PROP_KIND = {
    "TypePropertySingleValue": "IfcPropertySingleValue",
    "TypePropertyBoundedValue": "IfcPropertyBoundedValue",
    "TypePropertyEnumeratedValue": "IfcPropertyEnumeratedValue",
    "TypePropertyListValue": "IfcPropertyListValue",
    "TypePropertyTableValue": "IfcPropertyTableValue",
    "TypePropertyReferenceValue": "IfcPropertyReferenceValue",
    "TypeComplexProperty": "IfcComplexProperty",
}


class Template:
    """Jedna definícia z ``annex-a-psd.zip``."""

    __slots__ = ("name", "kind", "templatetype", "classes", "predefined", "props")

    def __init__(self, name, kind, templatetype, classes, predefined, props):
        self.name = name
        self.kind = kind                  # "pset" | "qto"
        self.templatetype = templatetype  # PSET_TYPEDRIVENOVERRIDE, …
        self.classes = classes            # ["IfcWall", "IfcWallType"]
        self.predefined = predefined      # {"IfcActuator": "ELECTRICACTUATOR"}
        self.props = props                # meno → (druh, dátový typ | None)


def load_templates() -> dict:
    """Načíta 760 definícií zo ZIPu publikovaných docs."""
    if not os.path.exists(PSD_ZIP):
        sys.exit("annex-a-psd.zip nenájdený: %s" % PSD_ZIP)
    out = {}
    with zipfile.ZipFile(PSD_ZIP) as z:
        for info in z.infolist():
            if not info.filename.endswith(".xml"):
                continue
            root = ET.fromstring(z.read(info.filename))
            name = (root.findtext("Name") or "").strip()
            if not name:
                continue
            classes, predefined = [], {}
            for cn in root.iter("ClassName"):
                txt = (cn.text or "").strip()
                if not txt:
                    continue
                if "/" in txt:
                    cls, pdt = txt.split("/", 1)
                    classes.append(cls)
                    predefined[cls] = pdt
                else:
                    classes.append(txt)
            props = {}
            for pd in root.iter("PropertyDef"):
                pname = (pd.findtext("Name") or "").strip()
                ptype = pd.find("PropertyType")
                kind, dtype = None, None
                if ptype is not None and len(ptype):
                    child = list(ptype)[0]
                    kind = child.tag
                    dt = child.find("DataType")
                    if dt is not None:
                        dtype = dt.get("type")
                props[pname] = (kind, dtype)
            for qd in root.iter("QtoDef"):
                qname = (qd.findtext("Name") or "").strip()
                props[qname] = (qd.findtext("QtoType"), None)
            out[name] = Template(
                name,
                "qto" if root.tag == "QtoSetDef" else "pset",
                root.get("templatetype") or "",
                classes,
                predefined,
                props,
            )
    return out


def lexical_applicability(name: str):
    """To isté prečítané z ``lexical/<meno>.html``. ``None`` = stránka nie je.

    Vracia ``(templatetype, [triedy])``. Sekcia „Applicable entities" má
    tvar: nadpis, ``PSET_*`` konštanta, veta, a potom odkazy na triedy.
    Berú sa odkazy na ``../<Trieda>.htm``, čo vylučuje ``IfcTypeObject``
    a ``IfcObject`` z vysvetľujúcej vety — tie sú v nej ako plain text.
    """
    path = os.path.join(LEX, name + ".html")
    if not os.path.exists(path):
        return None
    raw = open(path, encoding="utf-8").read()
    m = re.search(
        r"Applicable entities(.*?)(?:</section>|Properties</h4>|Properties</h3>)",
        raw,
        re.S,
    )
    if not m:
        return None
    chunk = m.group(1)
    tt = re.search(r"\b((?:PSET|QTO)_[A-Z]+)\b", re.sub(r"<[^>]+>", " ", chunk))
    classes = []
    for href, label in re.findall(
        r'<a[^>]+href="[^"]*?([A-Za-z0-9_]+)\.htm"[^>]*>(.*?)</a>', chunk, re.S
    ):
        label = html.unescape(re.sub(r"<[^>]+>", "", label)).strip()
        if label.startswith("Ifc") and label not in classes:
            classes.append(label)
    return (tt.group(1) if tt else None), classes


def owner_pairs(model):
    """(definícia psetu, vlastník, cesta) — bez duplicít.

    Cesty sú tri: ``IfcRelDefinesByProperties`` (occurrence aj typ),
    ``IfcTypeObject.HasPropertySets`` a ``IfcMaterialProperties``.
    """
    seen, pairs = set(), []
    for rel in model.by_type("IfcRelDefinesByProperties"):
        pdef = rel.RelatingPropertyDefinition
        if pdef is None:
            continue
        for obj in rel.RelatedObjects or []:
            key = (pdef.id(), obj.id())
            if key in seen:
                continue
            seen.add(key)
            pairs.append((pdef, obj, "rel"))
    for tobj in model.by_type("IfcTypeObject"):
        for pdef in tobj.HasPropertySets or []:
            key = (pdef.id(), tobj.id())
            if key in seen:
                continue
            seen.add(key)
            pairs.append((pdef, tobj, "type"))
    for mp in model.by_type("IfcMaterialProperties"):
        pairs.append((mp, mp.Material, "material"))
    return pairs


def value_type(prop):
    """Skutočný dátový typ hodnoty, alebo ``None`` keď ho nemá zmysel merať."""
    if prop.is_a("IfcPropertySingleValue"):
        v = prop.NominalValue
        return v.is_a() if v is not None else None
    if prop.is_a("IfcPropertyBoundedValue"):
        for v in (prop.UpperBoundValue, prop.LowerBoundValue, prop.SetPointValue):
            if v is not None:
                return v.is_a()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--json", default="",
                    help="kam zapísať strojovo čitateľný nález (GlobalId a všetko)")
    args = ap.parse_args()

    tpl = load_templates()
    print("šablón z annex-a-psd.zip :", len(tpl))
    print("model                    :", args.src)
    model = ifcopenshell.open(args.src)
    print("schéma                   :", model.schema_identifier)
    print()

    pairs = owner_pairs(model)
    print("dvojíc (pset, vlastník)  :", len(pairs))

    # ---- 0. zhoda oboch zdrojov docs, len pre mená, ktoré v modeli sú -----
    used = sorted({p.Name for p, _, _ in pairs if p.Name})
    print("rôznych mien v modeli    :", len(used))
    mismatch = []
    for name in used:
        t = tpl.get(name)
        lex = lexical_applicability(name)
        if t is None or lex is None:
            continue
        ltt, lclasses = lex
        zclasses = [c + ("/" + t.predefined[c] if c in t.predefined else "")
                    for c in t.classes]
        # lexical uvádza triedu bez PredefinedType, ten je vo vete zvlášť
        zbase = [c.split("/")[0] for c in zclasses]
        if ltt != t.templatetype or sorted(lclasses) != sorted(zbase):
            mismatch.append((name, t.templatetype, zbase, ltt, lclasses))
    print("nezhoda psd × lexical    :", len(mismatch))
    for m in mismatch:
        print("   ", m)
    print()

    unknown = collections.Counter()      # 1 meno mimo štandardu
    wrong_class = collections.Counter()  # 2 trieda nepripúšťa
    wrong_carrier = collections.Counter()  # 3 zlý nosič
    wrong_tmpl = collections.Counter()   # 4 typ × occurrence
    extra_prop = collections.Counter()   # 5 property mimo šablóny
    wrong_dtype = collections.Counter()  # 6 dátový typ
    wrong_pdt = collections.Counter()    # 7 PredefinedType

    detail = collections.defaultdict(list)
    records = []   # strojovo čitateľný nález

    def rec(bod, pset, owner, **kw):
        records.append(dict(
            bod=bod, pset=pset,
            owner_gid=getattr(owner, "GlobalId", None) if owner is not None else None,
            owner_class=owner.is_a() if owner is not None else None,
            owner_name=getattr(owner, "Name", None) if owner is not None else None,
            **kw))

    for pdef, owner, path in pairs:
        name = pdef.Name
        if not name:
            unknown[("(bez mena)", pdef.is_a(), owner.is_a() if owner else "—")] += 1
            continue
        t = tpl.get(name)
        ocls = owner.is_a() if owner is not None else "—"

        if t is None:
            if name.startswith(("Pset_", "Qto_", "PEnum_")):
                unknown[(name, pdef.is_a(), ocls)] += 1
                detail[("1", name, ocls)].append(owner)
                rec(1, name, owner, carrier=pdef.is_a())
            continue

        # 3 · nosič
        want = "IfcElementQuantity" if t.kind == "qto" else "IfcPropertySet"
        if t.templatetype.endswith("MATERIALDRIVEN"):
            want = "IfcMaterialProperties"
        elif t.templatetype.endswith("PROFILEDRIVEN"):
            want = "IfcProfileProperties"
        if not pdef.is_a(want):
            wrong_carrier[(name, pdef.is_a(), want)] += 1
            detail[("3", name, ocls)].append(owner)
            rec(3, name, owner, carrier=pdef.is_a(), want=want)

        # 2 · trieda
        if owner is not None and not any(owner.is_a(c) for c in t.classes):
            wrong_class[(name, ocls, ",".join(t.classes))] += 1
            detail[("2", name, ocls)].append(owner)
            rec(2, name, owner, applicable=t.classes,
                members=[x.Name for x in (
                    (pdef.HasProperties if pdef.is_a("IfcPropertySet")
                     else pdef.Quantities if pdef.is_a("IfcElementQuantity")
                     else pdef.Properties) or [])])
        else:
            # 7 · PredefinedType — len keď trieda sedí
            for c, pdt in t.predefined.items():
                if owner is not None and owner.is_a(c):
                    have = getattr(owner, "PredefinedType", None)
                    if have != pdt:
                        wrong_pdt[(name, ocls, str(have), pdt)] += 1
                        detail[("7", name, ocls)].append(owner)
                        rec(7, name, owner, have=str(have), want=pdt)

        # 4 · šablóna vs typ/occurrence
        is_type = owner is not None and owner.is_a("IfcTypeObject")
        if owner is not None and not owner.is_a("IfcMaterial"):
            if t.templatetype.endswith("TYPEDRIVENONLY") and not is_type:
                wrong_tmpl[(name, t.templatetype, ocls, "na occurrence")] += 1
                detail[("4", name, ocls)].append(owner)
                rec(4, name, owner, templatetype=t.templatetype, kde="occurrence")
            if t.templatetype.endswith("OCCURRENCEDRIVEN") and is_type:
                wrong_tmpl[(name, t.templatetype, ocls, "na type")] += 1
                detail[("4", name, ocls)].append(owner)
                rec(4, name, owner, templatetype=t.templatetype, kde="type")

        # 5, 6 · vlastnosti a ich typy
        if pdef.is_a("IfcPropertySet"):
            members = pdef.HasProperties or []
        elif pdef.is_a("IfcElementQuantity"):
            members = pdef.Quantities or []
        elif pdef.is_a("IfcMaterialProperties"):
            members = pdef.Properties or []
        else:
            members = []
        for prop in members:
            pn = prop.Name
            if pn not in t.props:
                extra_prop[(name, pn, ocls)] += 1
                detail[("5", name, ocls)].append(owner)
                rec(5, name, owner, prop=pn, sablona=sorted(t.props))
                continue
            kind, dtype = t.props[pn]
            if t.kind == "qto":
                want_e = QTO_KIND.get(kind)
                if want_e and not prop.is_a(want_e):
                    wrong_dtype[(name, pn, prop.is_a(), want_e)] += 1
                    detail[("6", name, ocls)].append(owner)
                    rec(6, name, owner, prop=pn, have=prop.is_a(), want=want_e)
            else:
                want_e = PROP_KIND.get(kind)
                if want_e and not prop.is_a(want_e):
                    wrong_dtype[(name, pn, prop.is_a(), want_e)] += 1
                    detail[("6", name, ocls)].append(owner)
                    rec(6, name, owner, prop=pn, have=prop.is_a(), want=want_e)
                elif dtype:
                    have = value_type(prop)
                    if have is not None and have != dtype:
                        wrong_dtype[(name + "." + pn, "hodnota", have, dtype)] += 1
                        detail[("6", name, ocls)].append(owner)
                        rec(6, name, owner, prop=pn, have=have, want=dtype)

    def dump(title, counter, limit):
        total = sum(counter.values())
        print("%-52s %d" % (title, total))
        for k, c in counter.most_common(limit):
            print("      %6d  %s" % (c, "  |  ".join(str(x) for x in k)))
        if len(counter) > limit:
            print("      … a ďalších %d druhov" % (len(counter) - limit))
        print()
        return total

    print("=" * 78)
    n1 = dump("1 · meno mimo štandardu s vyhradenou predponou", unknown, args.show)
    n2 = dump("2 · trieda vlastníka pset nepripúšťa", wrong_class, args.show)
    n3 = dump("3 · zlý nosič (Pset × Qto × Material)", wrong_carrier, args.show)
    n4 = dump("4 · šablóna typ × occurrence", wrong_tmpl, args.show)
    n5 = dump("5 · property mimo šablóny", extra_prop, args.show)
    n6 = dump("6 · dátový typ proti šablóne", wrong_dtype, args.show)
    n7 = dump("7 · PredefinedType proti applicability", wrong_pdt, args.show)
    print("=" * 78)
    print("spolu porušení: %d" % (n1 + n2 + n3 + n4 + n5 + n6 + n7))

    # GlobalId nositeľov bodu 2 — to je to, čo sa bude opravovať
    if wrong_class:
        print("\nnositelia bodu 2 (prvých %d):" % args.show)
        shown = 0
        for (key, owners) in sorted(detail.items()):
            if key[0] != "2":
                continue
            for o in owners[: args.show]:
                print("   %-14s %-22s %s" % (
                    getattr(o, "GlobalId", "—"), o.is_a(), getattr(o, "Name", "")))
                shown += 1
                if shown >= args.show:
                    break
            if shown >= args.show:
                break
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "subject": args.src,
                "docs": DOCS,
                "sablon": len(tpl),
                "dvojic": len(pairs),
                "psd_vs_lexical_nezhoda": len(mismatch),
                "porusenia": records,
            }, fh, ensure_ascii=False, indent=1)
        print("\nzapísané:", args.json, "—", len(records), "záznamov")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
