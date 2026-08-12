"""Invarianty modelu OCB.

Deväť invariantov. Sedem podľa ``CLAUDE_CODE_START.md`` § „Invarianty po
každom kroku", ôsmy pribudol po fáze 19 (viď :func:`inv8_spatial_fit`)
a deviaty po fáze 21 (viď :func:`inv9_skladby_rozklad`).

Konvencia (zámerná, viď AUDIT.md §8 „každý skript overí, čo tvrdí"):

* každá kontrola vracia **zoznam** :class:`Violation`, nikdy ``bool``;
  prázdny zoznam znamená „prešlo".
* každá kontrola prijíma ``allowlist`` — množinu ``GlobalId``, ktoré daný
  krok pipeline smie zmeniť. Porušenie na povolenom GlobalId sa nepočíta.

Pasce, na ktoré sme už narazili (nemeniť bez dôvodu):

* geometria sa porovnáva cez ``geom.iterator`` s multiprocessingom, **nie**
  opakovaným ``geom.create_shape`` — dávajú rozdielne výsledky;
* ``settings.set('use-world-coords', True)``;
* ``create_shape`` vracia **metre**, súbor je v **milimetroch**;
* entity sa porovnávajú cez ``.id()``, nie ``is``.
"""

from __future__ import annotations

import csv
import multiprocessing
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
import spatial  # noqa: E402

# --------------------------------------------------------------------------
# cesty
# --------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")

#: nemenný zdroj, referencia pre invariant 1 a 3
REFERENCE = os.path.join(DATA, "ASR.ifc")

#: vstup fázy 1
BASELINE = os.path.join(OUT, "ASR_final_v2.ifc")


# --------------------------------------------------------------------------
# výsledok
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """Jedno porušenie invariantu.

    ``global_id`` je ``None`` len pri entitách, ktoré nie sú ``IfcRoot``
    (napr. osirelý ``IfcLocalPlacement``); vtedy identifikuje ``express_id``.
    """

    invariant: int
    global_id: str | None
    entity: str
    detail: str
    express_id: int | None = None

    def __str__(self) -> str:  # pragma: no cover - iba pre výpis
        ident = self.global_id or (
            "#%d" % self.express_id if self.express_id is not None else "?"
        )
        return "inv%d  %-22s %-24s %s" % (
            self.invariant,
            self.entity,
            ident,
            self.detail,
        )


def _filter(violations: Iterable[Violation], allowlist: Iterable[str]) -> list[Violation]:
    """Vyhodí porušenia na GlobalId, ktoré daný krok smie meniť."""
    allow = set(allowlist or ())
    return [v for v in violations if v.global_id not in allow]


def _model(m):
    """Prijme cestu aj otvorený model."""
    return ifcopenshell.open(m) if isinstance(m, (str, os.PathLike)) else m


# --------------------------------------------------------------------------
# známe vady základne
# --------------------------------------------------------------------------

#: GlobalId vád, ktoré sú vo vstupe už pred pipeline a rieši ich neskoršia
#: fáza. Do allowlistu brány sa púšťajú **menovite**, nikdy paušálne —
#: aby brána merala len to, čo daná fáza zmenila, a nič sa nezamlčalo.
KNOWN_BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "known_baseline.json")


def known_baseline(*keys: str) -> set[str]:
    """Zjednotenie GlobalId pre uvedené položky registra, napr. ``"AW"``."""
    import json

    with open(KNOWN_BASELINE_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    out: set[str] = set()
    for k in keys:
        if k not in data:
            raise KeyError("známa vada %r nie je v %s" % (k, KNOWN_BASELINE_PATH))
        out.update(data[k]["global_ids"])
    return out


# --------------------------------------------------------------------------
# 1 — geometria
# --------------------------------------------------------------------------

#: triedy, ktorých tvar sa stráži
GEOMETRY_CLASSES = ("IfcBuiltElement", "IfcSpace")

#: počet procesov pre geom.iterator
THREADS = max(1, (os.cpu_count() or 2) - 1)

#: zhoda bboxu na 6 desatinných miest (v milimetroch)
BBOX_DECIMALS = 6


def bbox_map(path: str, classes: Sequence[str] = GEOMETRY_CLASSES) -> dict[str, tuple]:
    """``{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)}`` v **milimetroch**.

    Používa ``geom.iterator`` s multiprocessingom. ``create_shape`` vracia
    metre, preto sa násobí 1000 — súbor je v mm.
    """
    model = ifcopenshell.open(path)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    products = []
    for cls in classes:
        products.extend(model.by_type(cls))
    # deduplikácia cez .id(), nie cez `is`
    products = list({p.id(): p for p in products}.values())

    out: dict[str, tuple] = {}
    if not products:
        return out

    it = ifcopenshell.geom.iterator(settings, model, THREADS, include=products)
    if not it.initialize():
        return out
    while True:
        shape = it.get()
        verts = shape.geometry.verts
        if verts:
            xs = verts[0::3]
            ys = verts[1::3]
            zs = verts[2::3]
            box = (
                round(min(xs) * 1000.0, BBOX_DECIMALS),
                round(min(ys) * 1000.0, BBOX_DECIMALS),
                round(min(zs) * 1000.0, BBOX_DECIMALS),
                round(max(xs) * 1000.0, BBOX_DECIMALS),
                round(max(ys) * 1000.0, BBOX_DECIMALS),
                round(max(zs) * 1000.0, BBOX_DECIMALS),
            )
            out[shape.guid] = box
        if not it.next():
            break
    return out


def inv1_geometry(
    subject_path: str,
    reference_path: str = REFERENCE,
    allowlist: Iterable[str] = (),
) -> list[Violation]:
    """Bboxy ``IfcBuiltElement`` a ``IfcSpace`` sa zhodujú s referenciou."""
    ref = bbox_map(reference_path)
    sub = bbox_map(subject_path)
    out: list[Violation] = []

    for gid, box in ref.items():
        if gid not in sub:
            out.append(Violation(1, gid, "?", "tvar sa stratil oproti referencii"))
        elif sub[gid] != box:
            delta = tuple(round(a - b, BBOX_DECIMALS) for a, b in zip(sub[gid], box))
            out.append(Violation(1, gid, "?", "bbox sa zmenil o %s mm" % (delta,)))
    for gid in sub:
        if gid not in ref:
            out.append(Violation(1, gid, "?", "tvar pribudol oproti referencii"))
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 2 — EXPRESS
# --------------------------------------------------------------------------


def inv2_express(subject_path: str, allowlist: Iterable[str] = ()) -> list[Violation]:
    """``validate(express_rules=True)`` = 0 hlásení."""
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(subject_path, logger, express_rules=True)

    out: list[Violation] = []
    for st in logger.statements:
        inst = st.get("instance")
        gid = getattr(inst, "GlobalId", None) if inst is not None else None
        out.append(
            Violation(
                2,
                gid if isinstance(gid, str) else None,
                inst.is_a() if inst is not None else "?",
                "%s: %s" % (st.get("type", "?"), st.get("message", ""))[:300],
                inst.id() if inst is not None else None,
            )
        )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 3 — GUID účtovníctvo
# --------------------------------------------------------------------------


def inv3_guid_accounting(
    subject,
    reference=None,
    expected_removed: Iterable[str] = (),
    expected_added: Iterable[str] = (),
    allowlist: Iterable[str] = (),
) -> list[Violation]:
    """Žiadne duplicitné GlobalId; každý stratený a nový GUID vysvetlený.

    Bez ``reference`` sa kontroluje len duplicita — to je jediné, čo sa dá
    o jednom súbore povedať bez porovnávacej bázy.
    """
    sub = _model(subject)
    out: list[Violation] = []

    seen: dict[str, int] = {}
    for e in sub.by_type("IfcRoot"):
        seen[e.GlobalId] = seen.get(e.GlobalId, 0) + 1
    for gid, n in seen.items():
        if n > 1:
            out.append(
                Violation(3, gid, sub.by_guid(gid).is_a(), "GlobalId %dx v súbore" % n)
            )

    if reference is not None:
        ref = _model(reference)
        ref_ids = {e.GlobalId for e in ref.by_type("IfcRoot")}
        sub_ids = set(seen)
        exp_rm = set(expected_removed)
        exp_add = set(expected_added)
        for gid in sorted(ref_ids - sub_ids):
            if gid not in exp_rm:
                out.append(
                    Violation(3, gid, ref.by_guid(gid).is_a(), "GUID zmizol nečakane")
                )
        for gid in sorted(sub_ids - ref_ids):
            if gid not in exp_add:
                out.append(
                    Violation(3, gid, sub.by_guid(gid).is_a(), "GUID pribudol nečakane")
                )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 4 — osirelé entity
# --------------------------------------------------------------------------

#: legitímne top-level entity (CLAUDE_CODE_START.md § Invarianty, bod 4)
#:
#: ``IfcRepresentationContext`` nie je v pôvodnom výpočte — doplnené po fáze 0,
#: rozhodnutie Samuela k #AY. Dôvod: reprezentačné kontexty visia na projekte
#: cez INVERZNÝ ``IfcGeometricRepresentationContext.HasSubContexts``; dopredný
#: odkaz ``ParentContext`` drží dieťa, takže subkontext má **vždy** 0 inverzov,
#: aj keď je riadnou súčasťou stromu projektu. Bez toho test hlási nepoužitý
#: Revit subkontext „Box" (#16) ako osirelý. O jeho zmazaní sa rozhodne
#: v sweepe fázy 9 spolu s #F.
#: ``IfcMaterialProperties`` doplnené po fáze 17 z **toho istého dôvodu**:
#: väzbu drží dopredný atribút ``Material`` a materiál ju vidí len cez
#: inverz ``IfcMaterial.HasProperties``, takže sady vlastností majú vždy
#: 0 inverzov. Overené na ``ASR_v24.ifc``: 15 z 15 má ``Material``
#: vyplnený a všetkých 15 je dosiahnuteľných cez ``HasProperties``.
ORPHAN_WHITELIST = (
    "IfcShapeAspect",
    "IfcMaterialDefinitionRepresentation",
    "IfcPresentationLayerAssignment",
    "IfcMapConversion",
    "IfcRelationship",
    "IfcRepresentationContext",
    "IfcMaterialProperties",
)


def inv4_orphans(
    subject,
    allowlist: Iterable[str] = (),
    whitelist: Sequence[str] = ORPHAN_WHITELIST,
) -> list[Violation]:
    """Entity, na ktoré nič neodkazuje, mimo whitelistu."""
    sub = _model(subject)
    allowed = tuple(whitelist)

    out: list[Violation] = []
    for e in sub:
        if sub.get_total_inverses(e):
            continue
        if any(e.is_a(w) for w in allowed):
            continue
        gid = getattr(e, "GlobalId", None)
        out.append(
            Violation(
                4,
                gid if isinstance(gid, str) else None,
                e.is_a(),
                "nič na ňu neodkazuje",
                e.id(),
            )
        )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 5 — prázdne povinné agregácie
# --------------------------------------------------------------------------

#: atribúty s kardinalitou SET[1:?], ktoré nesmú byť prázdne
MANDATORY_SETS = {
    "IfcRelAggregates": ("RelatedObjects",),
    "IfcRelNests": ("RelatedObjects",),
    "IfcRelContainedInSpatialStructure": ("RelatedElements",),
    "IfcRelReferencedInSpatialStructure": ("RelatedElements",),
    "IfcRelDefinesByProperties": ("RelatedObjects",),
    "IfcRelDefinesByType": ("RelatedObjects",),
    "IfcRelAssociates": ("RelatedObjects",),
    "IfcRelAssignsToGroup": ("RelatedObjects",),
    "IfcRelDeclares": ("RelatedDefinitions",),
    "IfcPropertySet": ("HasProperties",),
    "IfcElementQuantity": ("Quantities",),
    "IfcMaterialLayerSet": ("MaterialLayers",),
    "IfcMaterialConstituentSet": ("MaterialConstituents",),
}


def inv5_empty_sets(subject, allowlist: Iterable[str] = ()) -> list[Violation]:
    """Povinné SET[1:?] nie sú prázdne."""
    sub = _model(subject)
    out: list[Violation] = []
    for cls, attrs in MANDATORY_SETS.items():
        for e in sub.by_type(cls):
            for attr in attrs:
                val = getattr(e, attr, None)
                if val is not None and len(val) == 0:
                    gid = getattr(e, "GlobalId", None)
                    out.append(
                        Violation(
                            5,
                            gid if isinstance(gid, str) else None,
                            e.is_a(),
                            "%s je prázdny" % attr,
                            e.id(),
                        )
                    )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 6 — jednoznačnosť
# --------------------------------------------------------------------------

#: Kódy bez UOT — INST ide hneď za kód (AUDIT.md §2 rozhodnutie 1).
#: Dokumentačná konštanta; ``parse_snim`` ju **nepoužíva**, tam rozhoduje
#: šírka INST. Zdroj: ``data/snim_mapovanie.csv`` (17 kódov) plus to, čo
#: reálne stojí v modeli bez UOT: ``DZ02``, ``PL01`` a ``ST01`` (obal
#: strešného súvrstvia z fázy 1). ``ZD02`` je naopak trojúrovňový —
#: rozhodnutie 12 drží rad ``ZD02.01``–``.04`` dosky, ``.05`` blok.
#: ``LP01`` je tu podľa rozhodnutia 19, ``LP02`` podľa rozhodnutia 4.
TWO_LEVEL_CODES = frozenset(
    {
        "AZ01", "DZ02", "KV01", "KV02", "LP01", "LP02", "LOP02", "OK01",
        "PL01", "SC01", "SD03", "SD04", "ST01", "VP02",
        "WC01", "WC02", "WC03", "WC04", "WC05", "WC06", "WC07",
    }
)

_CODE = re.compile(r"^[A-Z]{2,3}\d{2}$")


def load_two_level_codes(csv_path: str = os.path.join(DATA, "snim_mapovanie.csv")):
    """Kódy bez UOT načítané z mapovacieho CSV (kontrola proti konštante)."""
    codes = set()
    with open(csv_path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            code = (row.get("snim_kod") or "").strip()
            if code:
                codes.add(code)
    return codes


#: pevná šírka INST (AUDIT.md §2 rozhodnutie 2, napr. ``LP02.0001``)
INST_WIDTH = 4


def parse_snim(name: str | None) -> tuple[str | None, str | None]:
    """``name`` → ``(kód, INST)``. ``INST`` je ``None``, ak chýba.

    ``DD01.05.01`` → ``("DD01.05", "01")``   — kód.UOT.INST
    ``LP02.0001``  → ``("LP02", "0001")``    — dvojúrovňový kód.INST
    ``PH01.10``    → ``("PH01.10", None)``   — kód.UOT, INST chýba

    Dvojsegmentové meno je nejednoznačné: ``PL01.0004`` môže byť kód.UOT
    aj kód.INST. Rozhoduje **šírka** — ``INST`` má podľa rozhodnutia 2
    pevne 4 znaky, ``UOT`` v tomto modeli vždy 2. Je to spoľahlivejšie než
    zoznam kódov bez UOT: ten v ``snim_mapovanie.csv`` má 17 položiek, ale
    model ich obsahuje 18 a ďalšie sú len na typoch (``DZ01``, ``IH01``).
    """
    if not name:
        return None, None
    parts = name.split(".")
    if not _CODE.match(parts[0]):
        return None, None
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return parts[0] + "." + parts[1], parts[2]
    if len(parts) == 2 and parts[1].isdigit():
        if len(parts[1]) == INST_WIDTH:
            return parts[0], parts[1]
        return name, None
    if len(parts) == 1:
        return parts[0], None
    return name, None


def snim_occurrences(model):
    """Occurrences, ktoré nesú SNIM kód.

    ``IfcFeatureElement`` (otvory) sa vylučuje: Revit im dáva meno hostiteľa,
    takže každý ``DD*`` otvor by inak vyzeral ako duplicita dverí. Otvor nie
    je SNIM prvok — nemá vlastný kód a do výkazu nevstupuje.
    """
    return [
        e
        for e in model.by_type("IfcProduct")
        if not e.is_a("IfcTypeObject") and not e.is_a("IfcFeatureElement")
    ]


def inv6_uniqueness(subject, allowlist: Iterable[str] = ()) -> list[Violation]:
    """Plný SNIM kód je unikátny; ``Types : SET[0:1]`` na každý typ."""
    sub = _model(subject)
    out: list[Violation] = []

    by_code: dict[str, list] = {}
    for e in snim_occurrences(sub):
        code, inst = parse_snim(e.Name)
        if inst is None:
            continue  # bez INST nie je kód plný — rieši fáza 4
        by_code.setdefault(e.Name, []).append(e)

    for name, elems in sorted(by_code.items()):
        if len(elems) > 1:
            for e in elems:
                out.append(
                    Violation(
                        6, e.GlobalId, e.is_a(), "plný SNIM kód %r je %dx" % (name, len(elems))
                    )
                )

    for t in sub.by_type("IfcTypeObject"):
        if len(t.Types) > 1:
            out.append(
                Violation(
                    6,
                    t.GlobalId,
                    t.is_a(),
                    "Types má %d IfcRelDefinesByType, povolené SET[0:1]" % len(t.Types),
                )
            )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 7 — kontajnment vs agregácia
# --------------------------------------------------------------------------


def inv7_containment_vs_aggregation(
    subject, allowlist: Iterable[str] = ()
) -> list[Violation]:
    """Žiadny prvok nie je súčasne ``Decomposes`` aj ``ContainedInStructure``.

    Kontajnment je exkluzívny: ak je prvok časťou agregátu, do priestorovej
    štruktúry ho viaže celok, nie časť.
    """
    sub = _model(subject)
    out: list[Violation] = []
    for e in sub.by_type("IfcObjectDefinition"):
        dec = getattr(e, "Decomposes", None)
        con = getattr(e, "ContainedInStructure", None)
        if dec and con:
            whole = dec[0].RelatingObject
            struct = con[0].RelatingStructure
            out.append(
                Violation(
                    7,
                    e.GlobalId,
                    e.is_a(),
                    "agregovaný do %s %r a zároveň v %s %r"
                    % (whole.is_a(), whole.Name, struct.is_a(), struct.Name),
                )
            )
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 8 — priestorové zaradenie sedí s geometriou
# --------------------------------------------------------------------------

#: koľko výšky prvku musí padnúť do pásma podlažia, v ktorom je zaradený
MIN_IN_ZONE = 0.5

#: zaokrúhlenie Z pri hľadaní geometricky zhodných súrodencov (mm)
SIBLING_STEP = 50.0

#: koľko výšky musí prvok mať v pásme svojho podlažia, aby sa dal považovať
#: za zámerne rozkročený cez rozhranie. Pod týmto podielom už referencia na
#: druhé podlažie nie je priznanie rozkročenia, ale zakrytie zlého zaradenia
#: — presne tak vyzeralo 24 stĺpov pred fázou 19: 4 % v podlaží, v ktorom
#: viseli, a referencia na to, v ktorom naozaj stoja.
MIN_STRADDLE = 0.2


def inv8_spatial_fit(subject, allowlist: Iterable[str] = ()) -> list[Violation]:
    """Prvok je zaradený v podlaží, ktorého pásmo ho naozaj drží.

    Vznikol po fáze 19, kde sa ukázalo, že 117 prvkov viselo o podlažie
    nižšie, než kde stoja — vrátane 8 strešných vpustí na 3NP a 24 stĺpov,
    ktoré tým boli rozdelené medzi dve podlažia. Kontroluje sa dvojmo:

    **a** prvok kontajnovaný v podlaží (alebo v priestore toho podlažia)
    má v jeho pásme aspoň :data:`MIN_IN_ZONE` svojej výšky. Prvok zámerne
    rozkročený cez rozhranie výnimku dostane, ak v pásme má aspoň
    :data:`MIN_STRADDLE` a na druhé podlažie má
    ``IfcRelReferencedInSpatialStructure`` — presne to je schémou určený
    zápis pre prvok cez viac podlaží.

    **b** prvky rovnakej triedy, rovnakého typu a rovnakého Z-rozsahu sú
    v jednom podlaží. Toto je tá kontrola, ktorá by pôvodnú vadu chytila
    aj bez pásiem: 16 stĺpov `SL02.01` s rozsahom `9050…13000` bolo 6× na
    2NP a 10× na 3NP a jedno z toho muselo byť zle.
    """
    sub = _model(subject)
    zones = spatial.storey_zones(sub)
    elements = [e for e in sub.by_type("IfcElement")
                if e.Representation is not None
                and not getattr(e, "Decomposes", None)
                and spatial.container_of(e) is not None]
    box = spatial.boxes(sub, elements)
    out: list[Violation] = []

    for e in elements:
        b = box.get(e.GlobalId)
        if b is None:
            continue
        storey = spatial.storey_of(spatial.container_of(e))
        if storey is None or storey not in zones:
            continue
        share = spatial.zone_share(b, zones[storey])
        if share >= MIN_IN_ZONE:
            continue
        best, _ = spatial.zone_storey(b, zones)
        if (share >= MIN_STRADDLE
                and any(x.id() == best.id() for x in spatial.references_of(e))):
            continue                       # rozkročený a priznaný referenciou
        out.append(Violation(
            8, e.GlobalId, e.is_a(),
            "je v %r, ale len %.0f %% jeho výšky (z=%.0f…%.0f) je v pásme "
            "tohto podlažia; patrí do %r"
            % (storey.Name, share * 100, b[2], b[5], best.Name)))

    groups: dict[tuple, list] = {}
    for e in elements:
        b = box.get(e.GlobalId)
        if b is None:
            continue
        typ = (e.IsTypedBy[0].RelatingType.Name
               if getattr(e, "IsTypedBy", None) else None)
        key = (e.is_a(), typ,
               round(b[2] / SIBLING_STEP), round(b[5] / SIBLING_STEP))
        groups.setdefault(key, []).append(e)
    for key, items in groups.items():
        seen = {}
        for e in items:
            st = spatial.storey_of(spatial.container_of(e))
            if st is not None:
                seen.setdefault(st.Name, []).append(e)
        if len(seen) < 2:
            continue
        rozpad = {k: len(v) for k, v in sorted(seen.items())}
        for e in items:
            st = spatial.storey_of(spatial.container_of(e))
            if st is None:
                continue
            out.append(Violation(
                8, e.GlobalId, e.is_a(),
                "typ %r, z=%.0f…%.0f — zhodné prvky sú rozdelené medzi "
                "podlažia %s" % (key[1], key[2] * SIBLING_STEP,
                                 key[3] * SIBLING_STEP, rozpad)))
    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# 9 — rozklad skladby na výskyty
# --------------------------------------------------------------------------

#: Rodičovská skupina skladby — presne ``S`` a číslo. Výskyty sú ``S1.01``.
#: Konštanta je tu, nie v kroku, aby ju krok aj invariant brali z jedného
#: miesta; ``src/40_skladby_vyskyty.py`` ju importuje. Rozsah je zámerne
#: úzky: pravidlo „rodič nemá vlastných členov" je konvencia skladieb,
#: nie schémy, a na `IfcZone` alebo `IfcSystem` by neplatilo.
SKLADBA_PARENT = re.compile(r"^S\d+$")


def inv9_skladby_rozklad(subject, allowlist: Iterable[str] = ()) -> list[Violation]:
    """Rozklad skladby na výskyty je úplný a disjunktný.

    ``S1`` je predpis podľa `D.1.1.09`, ``S1.01`` a ``S1.02`` sú jeho
    výskyty na konkrétnych nosičoch (fáza 21). Väzbou je
    ``IfcRelAggregates``, ktorej ``Decomposes : SET [0:1]`` schémou vynúti,
    že výskyt patrí práve jednej skladbe.

    Kontroluje sa štvoro:

    **a** rodič s výskytmi nemá vlastných priamych členov — členstvo je
    len na výskytoch, inak sa prvky pri sčítaní zarátajú dvakrát;

    **b** výskyty tej istej skladby sa neprekrývajú. Toto je tá kontrola,
    ktorá by pôvodnú vadu chytila: ``S1`` mala v jednej skupine súvrstvie
    veľkej aj malej strechy;

    **c** každý výskyt má aspoň jedného člena;

    **d** výskyt visí práve na jednom rodičovi.

    Prekryv **medzi** skladbami sa nekontroluje a nesmie — 26 izolačných
    dosiek patrí do ``S1`` aj ``S2`` naraz, lebo kačírkový pás je 600 mm
    okraj tej istej strešnej plochy, pod ktorou je vegetácia (AUDIT.md §28).

    Úplnosť voči pôvodným počtom tu nie je: to je akceptačné kritérium
    kroku, ktorý rozklad robí, a po ňom už niet s čím porovnávať.
    """
    sub = _model(subject)
    out: list[Violation] = []

    for parent in sub.by_type("IfcGroup"):
        if parent.is_a() != "IfcGroup" or not SKLADBA_PARENT.match(parent.Name or ""):
            continue
        deti = [x for rel in (parent.IsDecomposedBy or ())
                for x in rel.RelatedObjects if x.is_a("IfcGroup")]
        if not deti:
            continue

        priami = [e for rel in (parent.IsGroupedBy or ()) for e in rel.RelatedObjects]
        if priami:
            out.append(Violation(
                9, parent.GlobalId, parent.is_a(),
                "%r má %d vlastných členov aj %d výskytov — členstvo patrí "
                "na výskyty, inak sa prvky rátajú dvakrát"
                % (parent.Name, len(priami), len(deti))))

        kde: dict[int, str] = {}
        for d in deti:
            cleny = [e for rel in (d.IsGroupedBy or ()) for e in rel.RelatedObjects]
            if not cleny:
                out.append(Violation(
                    9, d.GlobalId, d.is_a(),
                    "výskyt %r nemá ani jedného člena" % d.Name))
            if len(d.Decomposes or ()) != 1:
                out.append(Violation(
                    9, d.GlobalId, d.is_a(),
                    "výskyt %r visí na %d rodičoch, má práve na jednom"
                    % (d.Name, len(d.Decomposes or ()))))
            for e in cleny:
                if e.id() in kde:
                    out.append(Violation(
                        9, e.GlobalId, e.is_a(),
                        "%r je vo výskyte %r aj %r tej istej skladby %r"
                        % (e.Name, kde[e.id()], d.Name, parent.Name)))
                else:
                    kde[e.id()] = d.Name

    return _filter(out, allowlist)


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------

ALL = {
    1: inv1_geometry,
    2: inv2_express,
    3: inv3_guid_accounting,
    4: inv4_orphans,
    5: inv5_empty_sets,
    6: inv6_uniqueness,
    7: inv7_containment_vs_aggregation,
    8: inv8_spatial_fit,
    9: inv9_skladby_rozklad,
}


def run_all(
    subject_path: str,
    reference_path: str | None = REFERENCE,
    allowlist: Iterable[str] = (),
    skip: Sequence[int] = (),
) -> dict[int, list[Violation]]:
    """Pustí všetkých sedem a vráti ``{číslo: [porušenia]}``."""
    allowlist = set(allowlist or ())
    res: dict[int, list[Violation]] = {}
    if 1 not in skip:
        if reference_path and os.path.exists(reference_path):
            res[1] = inv1_geometry(subject_path, reference_path, allowlist)
        else:
            raise FileNotFoundError(
                "invariant 1 potrebuje referenciu %s" % reference_path
            )
    if 2 not in skip:
        res[2] = inv2_express(subject_path, allowlist)
    model = ifcopenshell.open(subject_path)
    if 3 not in skip:
        ref = reference_path if (reference_path and os.path.exists(reference_path)) else None
        res[3] = inv3_guid_accounting(model, ref, allowlist=allowlist)
    if 4 not in skip:
        res[4] = inv4_orphans(model, allowlist)
    if 5 not in skip:
        res[5] = inv5_empty_sets(model, allowlist)
    if 6 not in skip:
        res[6] = inv6_uniqueness(model, allowlist)
    if 7 not in skip:
        res[7] = inv7_containment_vs_aggregation(model, allowlist)
    if 9 not in skip:
        res[9] = inv9_skladby_rozklad(model, allowlist)
    return res


# ==========================================================================
# pytest
# ==========================================================================

import pytest  # noqa: E402

SUBJECT = os.environ.get("IFC_SUBJECT", BASELINE)

#: Očakávané zlyhanie invariantu 6 v základni — DD01.05.01 a .02.
#: Opraví sa vo fáze 4 (AUDIT.md #AP + rozhodnutie 6).
EXPECTED_INV6_CODES = {"DD01.05.01", "DD01.05.02"}


#: referencia geometrie. ``data/ASR.ifc`` v repe nie je (viď AUDIT §9), preto
#: sa reťazí: baseline = vstup danej fázy. Prepíše sa cez ``IFC_REFERENCE``.
SUBJECT_REFERENCE = os.environ.get("IFC_REFERENCE", REFERENCE)


@pytest.fixture(scope="module")
def model():
    return ifcopenshell.open(SUBJECT)


@pytest.mark.slow
@pytest.mark.skipif(
    not os.path.exists(SUBJECT_REFERENCE), reason="chýba referencia pre geometriu"
)
def test_inv1_geometry():
    """Tvary sa zhodujú s referenciou.

    Keď je referenciou pôvodný export ``data/ASR.ifc``, púšťajú sa do
    allowlistu zmeny krokov 1–13 (#PIPELINE_1_13). Tie skripty v repe nie
    sú, dotkli sa výlučne priestorov a **žiadneho prvku** — bez tejto
    výnimky by test hlásil zmeny, ktoré fázy 1–10 nespôsobili.
    """
    allow = set()
    if os.path.abspath(SUBJECT_REFERENCE) == os.path.abspath(REFERENCE):
        allow = known_baseline("PIPELINE_1_13")
    assert inv1_geometry(SUBJECT, SUBJECT_REFERENCE, allow) == []


@pytest.mark.slow
def test_inv2_express():
    assert inv2_express(SUBJECT) == []


def test_inv3_guid_accounting(model):
    """Žiadne duplicity; stratené a nové GUID vysvetlené.

    Referenciou tu **nie je** ``data/ASR.ifc``, aj keď v repe je. Kroky
    1–13 sa v ňom nenachádzajú, takže k ich 11 260 zmenám neexistujú
    zapísané očakávania a účtovať sa voči nim nedá — test by len meral
    cudziu prácu. Účtovníctvo tohto repa začína pri ``ASR_final_v2.ifc``
    a robí ho brána každého kroku cez ``--allow-file``.

    Na základni samotnej má teda zmysel len kontrola duplicít, čo je
    druhá polovica invariantu 3 a platí bez referencie.

    Geometria je iné: tú kroky 1–13 nezmenili vôbec, takže invariant 1
    sa proti ``data/ASR.ifc`` púšťa a prechádza (viď `test_inv1_geometry`).
    """
    ref = None if os.path.abspath(SUBJECT) == os.path.abspath(BASELINE) else (
        SUBJECT_REFERENCE if os.path.exists(SUBJECT_REFERENCE) else None)
    assert inv3_guid_accounting(model, ref) == []


def test_inv5_empty_sets(model):
    assert inv5_empty_sets(model) == []


# --- invarianty s otvorenými položkami registra --------------------------
#
# Tieto tri nesmú byť „zelené za každú cenu": kontrolujú, že model je presne
# v stave, ktorý register popisuje. Keď sa niečo neočakávane pohne — v oboch
# smeroch — test spadne.


@pytest.mark.skipif(SUBJECT != BASELINE, reason="rozpad #F platí pre základňu")
def test_inv4_orphans_matches_register(model):
    """#F — 48 osirelých entít, rozpad podľa registra."""
    import json

    with open(KNOWN_BASELINE_PATH, encoding="utf-8") as fh:
        expected = json.load(fh)["F"]
    found = inv4_orphans(model)
    rozpad = {k: sum(1 for v in found if v.entity == k)
              for k in sorted({v.entity for v in found})}
    assert len(found) == expected["pocet"]
    assert rozpad == expected["rozpad"]


@pytest.mark.skipif(SUBJECT != BASELINE, reason="#AP/#AX platí do fázy 4")
def test_inv6_uniqueness_matches_register(model):
    """#AP + #AX — päť duplicitných plných SNIM kódov, žiadny iný."""
    import json

    with open(KNOWN_BASELINE_PATH, encoding="utf-8") as fh:
        expected = json.load(fh)["AP_AX"]
    found = inv6_uniqueness(model)
    codes = sorted({v.detail.split("'")[1] for v in found})
    assert codes == expected["kody"]
    assert sorted({v.global_id for v in found}) == expected["global_ids"]


def test_inv7_containment_vs_aggregation(model):
    """#AW je odložená do fázy 6/7 — mimo nej nesmie byť nič."""
    allow = known_baseline("AW") if os.path.exists(KNOWN_BASELINE_PATH) else set()
    assert inv7_containment_vs_aggregation(model, allow) == []


@pytest.mark.slow
@pytest.mark.skipif(SUBJECT == BASELINE,
                    reason="#BC je vo vstupe, rieši ju fáza 19")
def test_inv8_spatial_fit():
    """Po fáze 19 nesmie žiadny prvok visieť v cudzom podlaží."""
    assert inv8_spatial_fit(SUBJECT) == []


@pytest.mark.slow
@pytest.mark.skipif(not os.path.exists(BASELINE), reason="chýba základňa")
def test_inv8_catches_the_defect_it_was_written_for():
    """Kontrola musí vadu naozaj chytiť, nie len prejsť na opravenom modeli.

    Základňa má 24 stĺpov a 8 strešných vpustí zaradených o podlažie
    vedľa — to je presne to, čo Samuel videl v strome ako „random".
    Vpuste sú v základni ešte ``IfcFlowTerminal``; na ``IfcWasteTerminal``
    ich prepísala až fáza 11, preto sa trieda terminálu neviaže presne.
    """
    found = inv8_spatial_fit(BASELINE)
    triedy = {v.entity for v in found}
    assert "IfcColumn" in triedy
    assert {"IfcFlowTerminal", "IfcWasteTerminal"} & triedy
    assert any("rozdelené medzi podlažia" in v.detail for v in found)


def test_inv9_skladby_rozklad(model):
    """Rozložená skladba nesmie mať prekrývajúce sa výskyty.

    Na modeli pred fázou 21 prejde prázdno — skupiny ešte deti nemajú,
    takže niet čo kontrolovať. Že kontrola naozaj funguje, overuje
    `test_inv9_catches_the_defect_it_was_written_for`.
    """
    assert inv9_skladby_rozklad(model) == []


def test_inv9_catches_the_defect_it_was_written_for():
    """Kontrola musí vadu naozaj chytiť, nie len prejsť na opravenom modeli.

    Pôvodnú vadu — `S1` so súvrstvím veľkej aj malej strechy v jednej
    skupine — nevie inv9 na základni ukázať, lebo tam skupina výskyty
    ešte nemá a kontrola ju preskočí. Vada sa preto postaví: rodič, ktorý
    si nechal vlastných členov, a dva výskyty zdieľajúce jeden prvok.
    """
    m = ifcopenshell.file(schema="IFC4X3_ADD2")
    guid = __import__("ifcopenshell.guid", fromlist=["guid"]).new
    a = m.create_entity("IfcSlab", GlobalId=guid(), Name="ST01.10.0001")
    b = m.create_entity("IfcSlab", GlobalId=guid(), Name="ST01.20.0001")
    rodic = m.create_entity("IfcGroup", GlobalId=guid(), Name="S1")
    d1 = m.create_entity("IfcGroup", GlobalId=guid(), Name="S1.01")
    d2 = m.create_entity("IfcGroup", GlobalId=guid(), Name="S1.02")
    m.create_entity("IfcRelAggregates", GlobalId=guid(),
                    RelatingObject=rodic, RelatedObjects=(d1, d2))
    m.create_entity("IfcRelAssignsToGroup", GlobalId=guid(),
                    RelatedObjects=(a, b), RelatingGroup=d1)
    m.create_entity("IfcRelAssignsToGroup", GlobalId=guid(),
                    RelatedObjects=(a,), RelatingGroup=d2)   # ← prekryv
    m.create_entity("IfcRelAssignsToGroup", GlobalId=guid(),
                    RelatedObjects=(a, b), RelatingGroup=rodic)  # ← členstvo na rodičovi

    found = inv9_skladby_rozklad(m)
    detaily = " | ".join(v.detail for v in found)
    assert "vlastných členov" in detaily
    assert "ST01.10.0001" in detaily and "'S1.01'" in detaily and "'S1.02'" in detaily
    assert len(found) == 2


@pytest.mark.skipif(SUBJECT == BASELINE, reason="vnorená zóna vzniká vo fáze 5c")
def test_inv9_ignores_nested_zones(model):
    """Vnorená `IfcZone` je tiež skupina v skupine, ale rozklad to nie je.

    `Pronajmutelné` má 10 priestorov **plus** vnorenú zónu „Nájomné
    priestory 3NP" s ďalšími 11 (fáza 5c, #Q). Keby sa rozsah invariantu
    určoval tvarom vzťahu a nie menom skladby, nahlásil by tu prebytky
    aj diery — a pritom je to legitímny model. Rozsah preto drží
    `SKLADBA_PARENT` a táto kontrola to zafixuje.
    """
    zony = [z for z in model.by_type("IfcZone") if z.IsGroupedBy]
    assert any(any(x.is_a("IfcZone") for x in rel.RelatedObjects)
               for z in zony for rel in z.IsGroupedBy), "vnorená zóna z #Q chýba"
    assert [v for v in inv9_skladby_rozklad(model) if v.entity == "IfcZone"] == []


def test_two_level_codes_cover_csv():
    """Každý kód bez UOT z CSV musí byť v konštante, okrem ZD02."""
    csv_codes = load_two_level_codes()
    assert csv_codes - TWO_LEVEL_CODES == {"ZD02"}, "ZD02 je kód.UOT (rozhodnutie 12)"


def test_parse_snim_width_rule():
    """Dvojsegmentové meno rozhoduje šírkou, nie zoznamom kódov."""
    assert parse_snim("DD01.05.01") == ("DD01.05", "01")
    assert parse_snim("LP02.0001") == ("LP02", "0001")
    assert parse_snim("PL01.0004") == ("PL01", "0004")
    assert parse_snim("PH01.10") == ("PH01.10", None)
    assert parse_snim("ZD02.01") == ("ZD02.01", None)
    assert parse_snim("OK01") == ("OK01", None)
    assert parse_snim("Openspace") == (None, None)
