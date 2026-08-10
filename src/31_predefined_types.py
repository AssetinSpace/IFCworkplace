"""Fáza 12 — ``PredefinedType`` prvkov, ktoré si triedu ponechávajú.

Register: #AM (zvyšok), rozhodnutia z ``AUDIT.md`` §29.

    python src/31_predefined_types.py            # dry-run
    python src/31_predefined_types.py --apply    # zapíše out/ASR_v19.ifc

Čo robí
-------
A  `SC01`     3 occ + typ  ``IfcStair``       → ``HALF_TURN_STAIR``
B  `SD04`     2 occ        ``IfcStairFlight`` → ``STRAIGHT`` (typ ho už má)
C  `ZV01.01`  4 occ + typ  ``IfcRailing``     → ``GUARDRAIL``
D  `ZV01.02`  6 occ + typ  ``IfcRailing``     → ``HANDRAIL``
E  `KV02`     2 occ + typ  ``IfcRailing``     → ``HANDRAIL``

Tým sa #AM zatvára. Bez ``PredefinedType`` zostanú **67 `IfcCurtainWall`**,
kde je to uzavreté schémou (§25: enum má len ``USERDEFINED`` a
``NOTDEFINED``), a 7 `OV02` ako ``IfcBuiltElement``, ktorý atribút nemá
vôbec — význam nesie ``ObjectType`` (§30).

Opora
-----
A  Spec: ``HALF_TURN_STAIR`` = *„A stair making a 180° turn, consisting of
   two straight flights connected."* Skript to **overí z geometrie**, nie
   z popisu: pre každé schodisko spočíta smer stúpania oboch ramien
   z ťažiska najnižších a najvyšších vrcholov a vyžaduje, aby zvierali
   viac než 150°. Ak nie, zastaví sa.
C  ``GUARDRAIL`` = *„designed to guard human or vehicle occupants from
   falling off a stair, ramp or landing where there is a vertical drop"*.
   Popis typu: „Zábradlí 1000 se svislou výplní".
D, E  ``HANDRAIL`` = *„structural support for loads applied by human
   occupants (at hand height). Generally located adjacent to ramps and
   stairs."* Popisy: „Madlo 1000", „Madlo – kovové". Rozhodnutie Samuela
   z 10. 8. menovalo ``ZV01.02``; ``KV02`` spadá pod to isté pravidlo
   a bolo potvrdené 10. 8.

Prečo to nešlo spraviť vo fáze 11
---------------------------------
Tieto prvky triedu **nemenia**. Fáza 11 nastavovala enum len tam, kde bol
súčasťou rozhodnutia o triede — na ``IfcStair`` sa nedá prejsť bez toho,
aby sme povedali ``LADDER``. Oddelené preto, aby pri zlyhaní brány bolo
jasné, ktorý z dvoch zásahov ho spôsobil.

Pasce
-----
* ``PredefinedType`` sa nastavuje aj na **type**, nielen na occurrences —
  inak by typ a occurrence tvrdili každý niečo iné.
* Skript sa pred zápisom presvedčí, že popis typu sedí s očakávaním. Keby
  sa kód medzitým použil na iný výrobok, radšej zastaví, než by nastavil
  enum naslepo.
"""

from __future__ import annotations

import argparse
import math
import os

import ifcopenshell
import ifcopenshell.geom
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v18.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v19.ifc")

DRY_RUN = True

#: typ → (očakávaný popis, PredefinedType, či nastaviť aj na type)
PLAN = [
    ("SC01",    "Prefabrikované schodiště",       "HALF_TURN_STAIR", True),
    ("SD04",    "ŽB. schodišťové rameno",         "STRAIGHT",        True),
    ("ZV01.01", "Zábradlí 1000 se svislou výplní", "GUARDRAIL",      True),
    ("ZV01.02", "Madlo 1000",                     "HANDRAIL",        True),
    ("KV02",    "Madlo – kovové",                 "HANDRAIL",        True),
]

#: minimálny uhol medzi smermi stúpania dvoch ramien, aby to bol obrat o 180°
MIN_UHOL = 150.0


def type_by_name(model, name):
    hits = [t for t in model.by_type("IfcTypeObject") if t.Name == name]
    if len(hits) != 1:
        raise SystemExit("STOP: typ %r nájdený %d× (čakal som 1)" % (name, len(hits)))
    return hits[0]


def smer_stupania(settings, flight):
    """Vodorovný vektor od spodku ramena k jeho vrchu.

    Ťažisko XY vrcholov v spodnej desatine výšky → ťažisko XY vrcholov
    v hornej desatine. Robustnejšie než bbox, ktorý o smere nehovorí nič.
    """
    # POZOR: shape sa musí držať v premennej. ``create_shape(...).geometry.verts``
    # v jednom výraze vráti pohľad do pamäte dočasného objektu, ktorý medzitým
    # zanikne — numpy potom číta uvoľnenú pamäť a vracia nuly a hodnoty rádu
    # 1e260. Prvý beh tohto skriptu na to naletel.
    shape = ifcopenshell.geom.create_shape(settings, flight)
    v = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
    del shape
    z = v[:, 2]
    lo, hi = z.min(), z.max()
    if hi - lo < 1e-9:
        raise SystemExit("STOP: rameno %r má nulovú výšku" % flight.Name)
    prah = (hi - lo) * 0.1
    dole = v[z <= lo + prah][:, :2].mean(axis=0)
    hore = v[z >= hi - prah][:, :2].mean(axis=0)
    d = hore - dole
    n = np.linalg.norm(d)
    if n < 1e-9:
        raise SystemExit("STOP: rameno %r nemá vodorovný priemet stúpania"
                         % flight.Name)
    return d / n


def over_obrat(model, rep):
    """Overí, že každé `SC01` má dve ramená otočené proti sebe."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    for stair in sorted(model.by_type("IfcStair"), key=lambda s: s.Name or ""):
        if not (stair.Name or "").startswith("SC01"):
            continue
        ramena = [o for r in stair.IsDecomposedBy for o in r.RelatedObjects
                  if o.is_a("IfcStairFlight")]
        if len(ramena) != 2:
            raise SystemExit("STOP: %s má %d ramien, HALF_TURN_STAIR čaká 2"
                             % (stair.Name, len(ramena)))
        a, b = (smer_stupania(settings, r) for r in ramena)
        uhol = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a, b))))))
        if uhol < MIN_UHOL:
            raise SystemExit(
                "STOP: %s — ramená zvierajú %.1f°, na obrat o 180° je málo. "
                "HALF_TURN_STAIR by bol nepodložený." % (stair.Name, uhol))
        rep.append(("  overené", stair.Name,
                    "ramená zvierajú %.1f° → obrat o 180°" % uhol))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY", "\n")

    geom_rep: list[tuple] = []
    over_obrat(model, geom_rep)
    for r in geom_rep:
        print("%s  %-12s %s" % r)
    print()

    rows: list[tuple] = []
    zmien = 0
    for name, popis, pdt, aj_typ in PLAN:
        typ = type_by_name(model, name)
        if (typ.Description or "") != popis:
            raise SystemExit("STOP: typ %r má popis %r, čakal som %r"
                             % (name, typ.Description, popis))
        occ = list(typ.Types[0].RelatedObjects) if typ.Types else []

        n_occ = 0
        for o in occ:
            if o.PredefinedType != pdt:
                o.PredefinedType = pdt
                n_occ += 1
        n_typ = 0
        if aj_typ and typ.PredefinedType != pdt:
            typ.PredefinedType = pdt
            n_typ = 1

        zmien += n_occ + n_typ
        rows.append((name, typ.is_a().replace("Ifc", "").replace("Type", ""),
                     pdt, len(occ), n_occ, n_typ))

    w = "  %-9s %-12s %-16s %5s %6s %5s"
    print(w % ("kód", "trieda", "PredefinedType", "occ", "zmen.", "typ"))
    print("  " + "-" * 58)
    for r in rows:
        print(w % r)
    print("\nspolu zmenených hodnôt: %d" % zmien)

    if zmien == 0:
        print("Idempotencia: všetko už hodnotu má, niet čo meniť.")
        return 0
    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    model.write(args.dst)
    print("\nzapísané:", args.dst)

    # PredefinedType nemení geometriu ani GlobalId — allowlist je prázdny,
    # ale súbor sa zapisuje, aby reťaz krokov mala konzistentný tvar.
    import json
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": []}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
