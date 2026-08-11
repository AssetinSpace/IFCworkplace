"""Sonda: obstoja rozhodnutia o triede a ``PredefinedType`` proti docs?
(**nič nemení**)

    python src/probe_classes.py                      # out/ASR_v28.ifc
    python src/probe_classes.py --in out/ASR_v27.ifc --json out/class_report.json

Prečo
-----
``AUDIT.md`` §38 bod 2. Rozhodnutí o triede a type je vyše dvadsať a autoritou
pri nich bola dokumentácia plus rozhodnutie Samuela, nie číselník — SNIM excel
``MOC_BEP_05`` neexistuje. Zapísané sú ručne, v dvoch tabuľkách
(``BEP_ANNEX.md`` §3 a ``AUDIT.md`` §5), aj s citáciami zo špecifikácie.

Ručný zápis má dve slabiny a sonda meria obe:

* **citácia sa nemusí zhodovať s docs.** Vetu mohol niekto skrátiť tak, že
  zmenila význam, alebo ju pripísať inej hodnote enumerácie, než z ktorej je.
* **register sa nemusí zhodovať s modelom.** Osemnásť fáz po ňom prešlo;
  rozhodnutie sa mohlo zmeniť a zápis zostať, alebo naopak vzniknúť
  rozhodnutie, ktoré nikto nezapísal. Presne to §38 volá *„nie nič sme
  neprehliadli"*.

Preto sonda zoznam rozhodnutí **neberie z registra** — odvodí si ho z modelu
porovnaním s ``data/ASR.ifc`` a register k nemu až potom priloží. Rozhodnutie,
ktoré register nepokrýva, je nález.

Zdroj pravdy
------------
Publikované docs buildingSMART, ``IFC/RELEASE/IFC4_3`` — dva zdroje, ako
v §39:

* ``IFC4X3_DEV_60a6175.exp`` — strojovo čitateľná schéma: členstvo v enumerácii,
  pravidlá ``CorrectTypeAssigned`` a ``CorrectPredefinedType``, hierarchia
  podtypov, vlastné atribúty entity;
* ``lexical/<meno>.html`` — tá istá vec vetou, plus to, čo v ``.exp`` nie je
  vôbec: definície hodnôt enumerácie, NOTE k ``PredefinedType`` a značka
  ``DEPRECATION`` pri atribútoch.

Enumerácie sa čítajú z **oboch** a porovnajú; nezhoda je vlastný nález sondy.
Bez toho by sonda tvrdila niečo o schéme na základe jedného neovereného
čítania — presne to, čo §8 zakazuje.

Čo meria
--------
1  enum     hodnota ``PredefinedType`` musí byť v enumerácii svojej triedy
2  pairing  ``CorrectTypeAssigned`` — occurrence smie mať len typ svojej triedy
3  USERDEF  ``CorrectPredefinedType`` — ``USERDEFINED`` žiada ``ObjectType``
            (na type ``ElementType``)
4  NOTE     *„The PredefinedType shall only be used, if no IfcXxxType is
            assigned"* — occurrence, ktorá nesie oboje
5  zhoda    hodnota na occurrence proti hodnote na jej type
6  citácia  citácia z registra, ktorá sa hlási k docs, musí byť v docs
            **doslova** — vrátane toho, že vypustené slovo je značené ``…``
7  register rozhodnutie odvodené z modelu, ktoré dokumentácia nepokrýva
8  deprec   atribút, ktorý docs značia ``DEPRECATION``, a model ho napĺňa

Kontroly 1–3 vymáha aj ``validate(express_rules=True)``, a preto sa čakajú
čisté — sú v sonde ako poistka, že sonda číta schému správne. Nález sa dá
očakávať v 4 až 8, lebo to sú väzby **dokumentačné**, nie EXPRESS, a invariant
2 je na ne slepý rovnako, ako bol na applicability psetov v §39.

Pasce, na ktoré sonda naráža
----------------------------
* NOTE k ``PredefinedType`` **nie je na každej stránke**. Nesú ju napr.
  ``IfcCovering`` či ``IfcWall``, ale ``IfcDoor``, ``IfcRailing``,
  ``IfcSanitaryTerminal``, ``IfcWasteTerminal`` a ``IfcFooting`` nie.
  Bod 4 sa preto počíta len tam, kde veta naozaj je — nie paušálne.
* Citácie v registri sú **dvojjazyčné a z rôznych zdrojov**. Niektoré sú
  anglický originál z docs s výpustkou ``…``, iné slovenský preklad tej istej
  vety, ďalšie vôbec nie sú zo špecifikácie (register ich značí ``výkres``
  alebo popisom typu). Rozoznávať ich podľa diakritiky **nefunguje** —
  „vrstva na vyrovnanie povrchu" je preklad a diakritiku nemá ani jednu.
  Sonda preto meria **podiel slov citácie, ktoré v docs stránke naozaj sú**,
  a prah oznamuje. Čo pod prah spadne, nehlási ako nález — vypíše to
  menovite aj s podielom na očné prejdenie a nikdy netvrdí, že to overila.
* Register **nie je len tá jedna tabuľka**. ``BEP_ANNEX.md`` §3 je z definície
  výber — *„rozhodnutia, ktoré nemá excel"* — a triedny model sa rozhodoval
  aj v ``AUDIT.md`` §2, §29, §30 a §31. Bod 7 preto hľadá oporu v **celom
  texte oboch súborov**, po riadkoch: rozhodnutie je pokryté, keď niektorý
  riadok dokumentácie menuje kód aj cieľ. Merať ho proti dvom tabuľkám by
  hlásilo ako nepokryté aj to, čo zapísané je — kritérium, ktoré neprejde
  známu pravdu, meria samo seba (§41).
* SNIM kód je meno typu (``SN07.04``) a predpona mena occurrence
  (``SN07.04.0005``). Priradenie kódu k prvku sa robí na hranici bodky,
  inak by ``SN02.0`` chytilo ``SN02.01``.
* ``PredefinedType`` nemá každá entita — ``IfcBuiltElement`` ani
  ``IfcFurniture`` ho nedefinujú. ``hasattr`` na to nestačí, lebo
  ifcopenshell vracia atribút aj tam, kde je zdedený ako ``None``; berie sa
  zoznam vlastných atribútov z ``.exp``.
"""

from __future__ import annotations

import argparse
import collections
import html
import json
import os
import re
import sys

import ifcopenshell

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v28.ifc")
REF = os.path.join(ROOT, "data", "ASR.ifc")

LEX = os.environ.get(
    "IFC_DOCS", "/workspace/bs-output/IFC/RELEASE/IFC4_3/lexical"
)
DOCS = os.path.dirname(LEX)

# Slovenské diakritické znaky — rozoznávač prekladu od anglického originálu.
SK = set("áäčďéěíĺľňóôŕřšťúůýž")

# Registre rozhodnutí, tak ako sú naozaj zapísané.
REGISTRE = (
    (os.path.join(ROOT, "BEP_ANNEX.md"),
     "3. Rozhodnutia o triede a type, ktoré nemá excel"),
    (os.path.join(ROOT, "AUDIT.md"),
     "5. Návrh `PredefinedType` pre `IfcWall`"),
)


# --------------------------------------------------------------------------
# zdroj pravdy 1 — EXPRESS
# --------------------------------------------------------------------------

class Schema:
    """To, čo sa dá o triede zistiť z ``.exp``."""

    def __init__(self, path):
        raw = open(path, encoding="utf-8", errors="replace").read()
        self.enums = {}        # IfcWallTypeEnum -> ["SOLIDWALL", …]
        self.supertype = {}    # IfcWall -> IfcBuiltElement
        self.attrs = {}        # IfcWall -> ["PredefinedType"]  (len vlastné)
        self.pdt_enum = {}     # IfcWall -> IfcWallTypeEnum
        self.type_of = {}      # IfcWall -> IFCWALLTYPE  (CorrectTypeAssigned)
        self.userdef_attr = {}  # IfcWall -> ObjectType | ElementType

        for m in re.finditer(r"TYPE\s+(\w+)\s*=\s*ENUMERATION OF\s*\((.*?)\)\s*;",
                             raw, re.S):
            self.enums[m.group(1)] = [
                v.strip() for v in m.group(2).replace("\n", "").split(",")
                if v.strip()
            ]

        for m in re.finditer(r"\nENTITY\s+(\w+)(.*?)END_ENTITY\s*;", raw, re.S):
            name, body = m.group(1), m.group(2)
            sup = re.search(r"SUBTYPE OF\s*\(\s*(\w+)\s*\)", body)
            if sup:
                self.supertype[name] = sup.group(1)

            # vlastné atribúty: od konca hlavičky po INVERSE/DERIVE/WHERE/UNIQUE
            head = re.split(r"\n\s*(?:INVERSE|DERIVE|WHERE|UNIQUE)\b", body)[0]
            head = re.sub(r"^.*?;", "", head, count=1, flags=re.S)
            own = []
            for a in re.finditer(r"(\w+)\s*:\s*(OPTIONAL\s+)?([\w\\\[\]:\s]+?);",
                                 head):
                own.append(a.group(1))
            self.attrs[name] = own

            pdt = re.search(r"\bPredefinedType\s*:\s*(?:OPTIONAL\s+)?(\w+)\s*;",
                            head)
            if pdt:
                self.pdt_enum[name] = pdt.group(1)

            cta = re.search(r"CorrectTypeAssigned[^;]*?'[\w\.]+\.([A-Z0-9_]+)'",
                            body, re.S)
            if cta:
                self.type_of[name] = cta.group(1)

            cpt = re.search(r"CorrectPredefinedType[^;]*?EXISTS\s*\(\s*SELF\\"
                            r"\w+\.(\w+)\s*\)", body, re.S)
            if cpt:
                self.userdef_attr[name] = cpt.group(1)

    def is_a(self, cls, want):
        """Je ``cls`` podtypom ``want``? Reťaz sa ide z ``.exp``, nie z modelu."""
        seen = 0
        while cls and seen < 40:
            if cls == want:
                return True
            cls = self.supertype.get(cls)
            seen += 1
        return False


# --------------------------------------------------------------------------
# zdroj pravdy 2 — lexical
# --------------------------------------------------------------------------

_TXT = {}


def lex_text(page):
    """Stránka ako súvislý text. ``None`` = stránka nie je."""
    if page in _TXT:
        return _TXT[page]
    f = os.path.join(LEX, page + ".html")
    if not os.path.exists(f):
        _TXT[page] = None
        return None
    raw = open(f, encoding="utf-8").read()
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    _TXT[page] = re.sub(r"\s+", " ", txt)
    return _TXT[page]


def lex_enum(name):
    """Hodnoty enumerácie a ich definície z ``lexical/<meno>.html``."""
    f = os.path.join(LEX, name + ".html")
    if not os.path.exists(f):
        return None
    raw = open(f, encoding="utf-8").read()
    out = {}
    for m in re.finditer(
        r'<td data-label="Name"><code>\s*([A-Z0-9_]+)\s*'
        r'<td data-label="Description">(.*?)</td>', raw, re.S
    ):
        out[m.group(1)] = re.sub(
            r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        ).strip()
    return out or None


_NOTE = re.compile(
    r"The\s+PredefinedType\s+shall only be used,?\s+if no\s+(Ifc\w+)\s+is assigned",
    re.I)


def lex_pdt_note(entity):
    """Trieda typu z NOTE, alebo ``None`` keď stránka NOTE nemá."""
    txt = lex_text(entity)
    if txt is None:
        return None
    m = _NOTE.search(txt)
    return m.group(1) if m else None


_DEPREC = re.compile(
    r"(?:-DEPRECATION\s+This attribute is deprecated"
    r"|The attribute has been deprecated)", re.I)


def lex_deprecated(entity, own_attrs):
    """Vlastné atribúty entity, ktoré docs značia ako zrušené.

    Blok atribútu sa reže od jeho hlavičky (``Meno OPTIONAL IfcTyp``) po
    hlavičku nasledujúceho — tak sa značka nepripíše susedovi.
    """
    txt = lex_text(entity)
    if txt is None:
        return {}
    marks = []
    for a in own_attrs:
        m = re.search(r"\b%s\b\s+(?:OPTIONAL\s+)?(?:SET|LIST|Ifc)\w*" % re.escape(a),
                      txt)
        if m:
            marks.append((m.start(), a))
    marks.sort()
    out = {}
    for i, (pos, a) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else min(len(txt), pos + 1200)
        blok = txt[pos:end]
        if _DEPREC.search(blok):
            veta = re.search(r"[^.]*deprecated[^.]*\.", blok, re.I)
            out[a] = veta.group(0).strip() if veta else "označené DEPRECATION"
    return out


# --------------------------------------------------------------------------
# registre rozhodnutí
# --------------------------------------------------------------------------

def expand(code):
    """``ZD02.03/.04`` → dva kódy. ``SN07.01–.05`` → päť."""
    code = code.replace("`", "").strip()
    out, base = [], None
    for part in re.split(r"[/,]", code):
        part = part.strip()
        if not part:
            continue
        rng = re.match(r"^(\.?[\w.]+?)[–-](\.[\w.]+)$", part)
        if rng:
            a, b = rng.group(1), rng.group(2)
            head = a if not a.startswith(".") else (base or "") + a
            base = base or head.rsplit(".", 1)[0]
            try:
                lo = int(head.rsplit(".", 1)[1])
                hi = int(b.lstrip(".").split(".")[0])
                pref = head.rsplit(".", 1)[0]
                out += ["%s.%02d" % (pref, n) for n in range(lo, hi + 1)]
                continue
            except ValueError:
                part = head
        if part.startswith("."):
            part = (base or "") + part
        else:
            base = part.rsplit(".", 1)[0] if "." in part else part
        out.append(part)
    return out


def load_registre():
    """Riadky oboch tabuliek: (súbor, kódy, tvrdenie, citácie)."""
    rows = []
    for path, nadpis in REGISTRE:
        if not os.path.exists(path):
            continue
        raw = open(path, encoding="utf-8").read()
        i = raw.find("## " + nadpis)
        if i < 0:
            continue
        blok = raw[i:]
        konec = blok.find("\n## ", 4)
        if konec > 0:
            blok = blok[:konec]
        for line in blok.splitlines():
            if not line.startswith("|"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) < 2 or set(cols[0]) <= set("-: ") or cols[0] in (
                    "prvok", "kód"):
                continue
            kod = cols[0].replace("`", "").strip()
            if not re.match(r"^[A-Z]{2}\d", kod):
                continue
            tvrd = " ".join(cols[1:])
            # zdroj citácie register značí slovom pred úvodzovkou
            cit = []
            for m in re.finditer(r"[„\"]([^„\"]{12,})[\"“]", tvrd):
                pred = tvrd[max(0, m.start() - 40):m.start()].lower()
                zdroj = "—"
                for kluc in ("výkres", "spec", "docs", "popis"):
                    if kluc in pred:
                        zdroj = kluc
                cit.append((m.group(1), zdroj))
            rows.append({
                "subor": os.path.basename(path),
                "kod_raw": kod,
                "kody": expand(kod),
                "tvrdenie": tvrd,
                "citacie": cit,
            })
    return rows


def dokumentacia():
    """Celý text oboch súborov po riadkoch — opora pre bod 7."""
    riadky = []
    for path in {p for p, _ in REGISTRE}:
        if os.path.exists(path):
            riadky += [r for r in open(path, encoding="utf-8").read().splitlines()
                       if r.strip()]
    return riadky


def kod_prvku(name):
    """SNIM kód z mena. ``SN07.04.0005`` → predpony, od najdlhšej."""
    if not name:
        return []
    diely = name.split(".")
    return [".".join(diely[:n]) for n in range(len(diely), 0, -1)]


# --------------------------------------------------------------------------

def norm(s):
    """Na porovnanie citácie: malé písmená, jedna medzera, bez interpunkcie."""
    s = html.unescape(s).lower().replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--reference", default=REF,
                    help="pôvodný export — z neho sa odvodí zoznam rozhodnutí")
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    exp_path = os.path.join(DOCS, "IFC4X3_DEV_60a6175.exp")
    if not os.path.exists(exp_path):
        sys.exit("EXPRESS schéma nenájdená: %s" % exp_path)
    sch = Schema(exp_path)
    print("EXPRESS                  :", os.path.basename(exp_path))
    print("   enumerácií            :", len(sch.enums))
    print("   entít                 :", len(sch.attrs))
    print("model                    :", args.src)
    model = ifcopenshell.open(args.src)
    print("schéma modelu            :", model.schema_identifier)
    print()

    objekty = list(model.by_type("IfcObject")) + list(model.by_type("IfcTypeObject"))
    triedy = sorted({o.is_a() for o in objekty})
    print("tried v modeli           :", len(triedy))

    # ---- 0 · zhoda oboch zdrojov docs ------------------------------------
    enum_mena = sorted({sch.pdt_enum[c] for c in triedy if c in sch.pdt_enum})
    nezhoda = []
    for en in enum_mena:
        lx = lex_enum(en)
        if lx is None:
            nezhoda.append((en, "lexical stránka nie je", "", ""))
            continue
        a, b = sorted(sch.enums.get(en, [])), sorted(lx)
        if a != b:
            nezhoda.append((en, "exp × lexical",
                            [x for x in a if x not in b],
                            [x for x in b if x not in a]))
    print("enumerácií v hre         :", len(enum_mena))
    print("nezhoda exp × lexical    :", len(nezhoda))
    for n in nezhoda:
        print("   ", n)
    print()

    zaznamy = []

    def rec(bod, e, **kw):
        zaznamy.append(dict(
            bod=bod,
            gid=getattr(e, "GlobalId", None),
            trieda=e.is_a(),
            meno=getattr(e, "Name", None),
            **kw))

    b1 = collections.Counter()   # hodnota mimo enumerácie
    b2 = collections.Counter()   # CorrectTypeAssigned
    b3 = collections.Counter()   # USERDEFINED bez ObjectType
    b4 = collections.Counter()   # NOTE — occurrence nesie oboje
    b5 = collections.Counter()   # occurrence × typ nezhoda hodnoty
    b8 = collections.Counter()   # zrušený atribút je naplnený

    def vlastny_pdt(e):
        """Hodnota ``PredefinedType``, len keď ju trieda naozaj definuje."""
        if e.is_a() not in sch.pdt_enum:
            return None
        return getattr(e, "PredefinedType", None)

    # deprecated atribúty sa čítajú raz na triedu
    dep_cache = {c: lex_deprecated(c, sch.attrs.get(c, [])) for c in triedy}
    note_cache = {c: lex_pdt_note(c) for c in triedy}

    for e in objekty:
        cls = e.is_a()
        pdt = vlastny_pdt(e)

        # 1 · enum
        if pdt is not None:
            en = sch.pdt_enum[cls]
            if pdt not in sch.enums.get(en, []):
                b1[(cls, pdt, en)] += 1
                rec(1, e, hodnota=pdt, enum=en)

        # 3 · USERDEFINED
        if pdt == "USERDEFINED":
            attr = sch.userdef_attr.get(cls,
                                        "ElementType" if e.is_a("IfcTypeObject")
                                        else "ObjectType")
            if not getattr(e, attr, None):
                b3[(cls, attr)] += 1
                rec(3, e, chyba="USERDEFINED bez " + attr)

        # 8 · zrušený atribút
        for a, veta in dep_cache.get(cls, {}).items():
            if getattr(e, a, None) is not None:
                b8[(cls + "." + a, veta[:90])] += 1
                rec(8, e, atribut=a, hodnota=str(getattr(e, a)), docs=veta)

        if e.is_a("IfcTypeObject"):
            continue

        typy = [r.RelatingType for r in getattr(e, "IsTypedBy", None) or []]
        if not typy:
            continue
        t = typy[0]

        # 2 · CorrectTypeAssigned
        want = sch.type_of.get(cls)
        if want and t.is_a().upper() != want:
            b2[(cls, t.is_a(), want)] += 1
            rec(2, e, typ=t.is_a(), want=want)

        # 4 · NOTE
        note = note_cache.get(cls)
        if note and pdt is not None:
            b4[(cls, note, pdt)] += 1
            rec(4, e, typ_triedy=note, hodnota=pdt,
                hodnota_typu=vlastny_pdt(t), typ_meno=getattr(t, "Name", None))

        # 5 · zhoda s typom
        tpdt = vlastny_pdt(t)
        if pdt is not None and tpdt is not None and pdt != tpdt:
            b5[(cls, pdt, tpdt)] += 1
            rec(5, e, hodnota=pdt, hodnota_typu=tpdt,
                typ_meno=getattr(t, "Name", None))

    def dump(nadpis, counter, limit=None):
        limit = args.show if limit is None else limit
        total = sum(counter.values())
        print("%-56s %d" % (nadpis, total))
        for k, c in counter.most_common(limit):
            print("      %6d  %s" % (c, "  |  ".join(str(x) for x in k)))
        if len(counter) > limit:
            print("      … a ďalších %d druhov" % (len(counter) - limit))
        print()
        return total

    print("=" * 78)
    n1 = dump("1 · hodnota PredefinedType mimo enumerácie", b1)
    n2 = dump("2 · CorrectTypeAssigned — typ inej triedy", b2)
    n3 = dump("3 · USERDEFINED bez ObjectType/ElementType", b3)
    n4 = dump("4 · NOTE: occurrence nesie PredefinedType aj typ", b4, 12)
    n5 = dump("5 · hodnota na occurrence sa líši od typu", b5)

    # provenancia bodu 4 — priniesol si to model, alebo to spravila pipeline?
    if n4 and os.path.exists(args.reference):
        orig4 = ifcopenshell.open(args.reference)
        mal = {o.GlobalId: getattr(o, "PredefinedType", None)
               for o in orig4.by_type("IfcObject")
               if o.is_a() in sch.pdt_enum}
        z_originalu = pridala_pipeline = nove_gid = 0
        for z in zaznamy:
            if z["bod"] != 4:
                continue
            if z["gid"] not in mal:
                nove_gid += 1
            elif mal[z["gid"]] is None:
                pridala_pipeline += 1
            else:
                z_originalu += 1
        print("   provenancia bodu 4:")
        print("      hodnotu nieslo už data/ASR.ifc     : %d" % z_originalu)
        print("      v origináli bola prázdna           : %d" % pridala_pipeline)
        print("      GUID v origináli vôbec nie je      : %d" % nove_gid)
        print()

    # ---- 6 · citácie -----------------------------------------------------
    # Prah: aký podiel slov citácie musí byť v cieľovej stránke, aby sa
    # citácia dala čítať ako anglický originál a nie ako preklad.
    PRAH = 0.8
    reg = load_registre()
    print("riadkov registra         :", len(reg))
    cit_ok = cit_zle = 0
    zle, mimo_docs, preklady = [], [], []
    for r in reg:
        strany = []
        for m in re.finditer(r"`?(Ifc[A-Za-z]+)\s*/\s*([A-Z_]+)`?", r["tvrdenie"]):
            strany += [m.group(1), m.group(1) + "Type",
                       sch.pdt_enum.get(m.group(1), "")]
            r.setdefault("hodnoty", []).append((m.group(1), m.group(2)))
        for m in re.finditer(r"`(Ifc[A-Za-z]+)`", r["tvrdenie"]):
            strany += [m.group(1), m.group(1) + "Type",
                       sch.pdt_enum.get(m.group(1), "")]
        for m in re.finditer(r"`([A-Z][A-Z_]{3,})`", r["tvrdenie"]):
            r.setdefault("hodnoty", []).append((None, m.group(1)))
        strany = [p for p in dict.fromkeys(strany) if p]
        korpus = " ".join(norm(lex_text(p) or "") for p in strany)
        slova = set(korpus.split())
        for c, zdroj in r["citacie"]:
            if zdroj in ("výkres", "popis"):
                mimo_docs.append((r["kod_raw"], c, zdroj))
                continue
            kusy = [k for k in re.split(r"…|\.\.\.", c) if norm(k)]
            vsetky = [w for k in kusy for w in norm(k).split() if len(w) >= 3]
            podiel = (sum(1 for w in vsetky if w in slova) / len(vsetky)
                      if vsetky else 0.0)
            if podiel < PRAH:
                preklady.append((r["kod_raw"], c, podiel, zdroj))
                continue
            chybne = [k.strip() for k in kusy if norm(k) not in korpus]
            if not chybne:
                cit_ok += 1
            else:
                cit_zle += 1
                zle.append((r["kod_raw"], c, chybne, strany, podiel))
                zaznamy.append(dict(bod=6, kod=r["kod_raw"], citacia=c,
                                    nenajdene=chybne, podiel_slov=round(podiel, 3)))

    print("citácií v registri       :",
          sum(len(r["citacie"]) for r in reg))
    print("   z docs, overiteľných  :", cit_ok + cit_zle,
          "(podiel slov ≥ %.0f %%)" % (PRAH * 100))
    print("   z iného zdroja        :", len(mimo_docs), "(výkres, popis typu)")
    print("   preklad či parafráza  :", len(preklady))
    print()
    print("6 · citácia sa hlási k docs, ale doslova v nich nie je   %d" % cit_zle)
    for z in zle[: args.show]:
        print("      %-16s „%s\"" % (z[0], z[1][:60]))
        print("         nenašlo sa : %s" % (z[2],))
        print("         hľadané na : %s" % (", ".join(z[3]),))
        print("         podiel slov: %.0f %%" % (z[4] * 100))
    print()
    print("citácie, ktoré sonda overiť nevie — na oči:")
    for k, c, p, zdroj in preklady:
        print("      %-16s %-52s slov v docs %3.0f %%%s"
              % (k, "„%s\"" % c[:50], p * 100,
                 "  [značené: %s]" % zdroj if zdroj != "—" else ""))
    for k, c, zdroj in mimo_docs:
        print("      %-16s %-52s zdroj %s" % (k, "„%s\"" % c[:50], zdroj))
    print()

    # ---- 7 · register proti odvodenému zoznamu rozhodnutí ----------------
    n7 = 0
    if os.path.exists(args.reference):
        orig = ifcopenshell.open(args.reference)

        def snap(m):
            d = {}
            for o in list(m.by_type("IfcObject")) + list(m.by_type("IfcTypeObject")):
                pdt = getattr(o, "PredefinedType", None) \
                    if o.is_a() in sch.pdt_enum else None
                d[o.GlobalId] = (o.is_a(), pdt, getattr(o, "Name", None))
            return d

        a, b = snap(orig), snap(model)
        spolu = set(a) & set(b)

        # SNIM kód prvku: meno jeho typu, inak predpona vlastného mena.
        # IfcSpace meno SNIM kód nie je (je to číslo miestnosti) — tam sa
        # rozhodnutie vedie na triedu, nie na kód.
        kod_typu = {}
        for r in model.by_type("IfcRelDefinesByType"):
            for o in r.RelatedObjects or []:
                kod_typu[o.GlobalId] = getattr(r.RelatingType, "Name", None)

        def kod(gid, meno):
            k = kod_typu.get(gid) or meno
            if not k or not re.match(r"^[A-Z]{2}\d", k):
                return None
            d = k.split(".")
            return ".".join(d[:-1]) if len(d) > 1 and d[-1].isdigit() \
                and len(d[-1]) >= 3 else k

        rozh = collections.Counter()   # (kód|trieda, staré, nové) -> počet
        for g in sorted(spolu):
            ac, apd, _ = a[g]
            bc, bpd, bn = b[g]
            if ac == bc and apd == bpd:
                continue
            rozh[(kod(g, bn) or ("(bez kódu) " + bc),
                  "%s/%s" % (ac, apd or "—"),
                  "%s/%s" % (bc, bpd or "—"))] += 1

        # Opora sa hľadá v celom texte, nie v jednom riadku. Rozhodnutie
        # o triede padalo dvojako: menovite na kód (``DZ02`` → ``SOLIDWALL``),
        # alebo pravidlom na celú skupinu (*„vrstvy strechy sú krytina"*).
        # Žiadať oboje na jednom riadku by druhý spôsob hlásilo ako
        # nezapísaný, hoci zapísaný je — preto sa merajú **dve veci zvlášť**
        # a ani jedna sa nevydáva za tú druhú.
        riadky = dokumentacia()
        kody_v_dok = set()
        skupiny = set()      # zápis `PD02.*` — pravidlo na celú skupinu
        for line in riadky:
            for m in re.finditer(r"`([A-Z]{2}\d[\w./–-]*)`", line):
                kody_v_dok |= set(expand(m.group(1)))
            # `ST01.*` je zaužívaný zápis tejto dokumentácie pre pravidlo
            # na skupinu. Bez neho by sonda hlásila ako nezapísané aj to,
            # čo zapísané je — len nie po jednom kóde.
            for m in re.finditer(r"`([A-Z]{2}\d[\w.]*)\.\*`", line):
                skupiny.add(m.group(1))
            # rozsah písaný cez dve úvodzovky: `PZ01`–`PZ10`. Bez tohto by
            # sonda hlásila PZ05 ako nezapísané, hoci zapísané je.
            for m in re.finditer(
                    r"`([A-Z]{2}\d+)`\s*[–-]\s*`([A-Z]{2}\d+)`", line):
                a_, b_ = m.group(1), m.group(2)
                pref = re.match(r"^([A-Z]+)", a_).group(1)
                if pref == re.match(r"^([A-Z]+)", b_).group(1):
                    lo, hi = int(a_[len(pref):]), int(b_[len(pref):])
                    sirka = len(a_) - len(pref)
                    kody_v_dok |= {"%s%0*d" % (pref, sirka, n)
                                   for n in range(lo, hi + 1)}
        text_dok = "\n".join(riadky)

        bez_kodu = collections.Counter()    # 7a
        bez_ciela = collections.Counter()   # 7b
        for (k, st, no), c in rozh.items():
            ciel_cls, ciel_pdt = no.split("/", 1)
            kluc = k.replace("(bez kódu) ", "")
            v_skupine = any(kluc == g or kluc.startswith(g + ".")
                            for g in skupiny)
            if not k.startswith("(bez kódu)") and kluc not in kody_v_dok \
                    and not v_skupine:
                bez_kodu[(k, st, no)] += c
            # ``IfcSanitaryTerminalType`` dokumentácia nepíše, píše
            # ``IfcSanitaryTerminal`` — trieda typu sa preto hľadá aj
            # v occurrence tvare, inak by sonda hlásila zapísané rozhodnutie.
            zaklad = re.sub(r"Type$", "", ciel_cls)
            chyba = []
            if ciel_cls not in text_dok and zaklad not in text_dok:
                chyba.append("trieda " + ciel_cls)
            if ciel_pdt != "—" and ciel_pdt not in text_dok:
                chyba.append("hodnota " + ciel_pdt)
            if chyba:
                bez_ciela[(k, no, ", ".join(chyba))] += c

        print("spoločných GUID s pôvodným exportom :", len(spolu))
        print("rozhodnutí odvodených z modelu      :", sum(rozh.values()),
              "v", len(rozh), "druhoch, na", len({x[0] for x in rozh}), "kódoch")
        print("riadkov dokumentácie prehľadaných   :", len(riadky))
        print("kódov, ktoré dokumentácia menuje    :", len(kody_v_dok))
        print()
        n7 = dump("7a · kód, ktorý dokumentácia nemenuje vôbec", bez_kodu)
        n7 += dump("7b · cieľ, ktorý dokumentácia nemenuje vôbec", bez_ciela)
        for r in ([dict(bod="7a", kod=k[0], zo=k[1], na=k[2], kusov=c)
                   for k, c in bez_kodu.items()]
                  + [dict(bod="7b", kod=k[0], zo=k[1], na=k[2], kusov=c)
                     for k, c in bez_ciela.items()]):
            zaznamy.append(r)
    else:
        print("referencia nenájdená, bod 7 sa nemeral:", args.reference)
        print()

    n8 = dump("8 · zrušený atribút je v modeli naplnený", b8)

    print("=" * 78)
    print("spolu nálezov: %d" % (n1 + n2 + n3 + n4 + n5 + cit_zle + n7 + n8))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "subject": args.src,
                "reference": args.reference,
                "docs": DOCS,
                "enum_exp_vs_lexical": nezhoda,
                "citacii_overenych": cit_ok,
                "citacii_neoveritelnych": len(preklady),
                "citacii_z_ineho_zdroja": len(mimo_docs),
                "nalezy": zaznamy,
            }, fh, ensure_ascii=False, indent=1)
        print("\nzapísané:", args.json, "—", len(zaznamy), "záznamov")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
