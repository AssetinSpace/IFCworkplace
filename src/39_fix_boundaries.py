"""Fáza 20 — #BH: doplní 20 chýbajúcich `IfcRelSpaceBoundary`.

    python src/39_fix_boundaries.py            # dry-run
    python src/39_fix_boundaries.py --apply    # zapíše out/ASR_v27.ifc

Nález opravuje ``src/probe_boundaries.py`` (§41).

Čo a prečo
----------
Dvere sú otvor **v stene**. Keď sú teda dvere hranicou priestoru, musí ňou
byť aj stena, ktorá ich obklopuje — spec k ``IfcRelSpaceBoundary1stLevel``:

    1st level space boundaries form a closed shell around the space (so long
    as the space is completely enclosed) and include overlapping boundaries
    representing openings (filled or not) in the building elements.

V modeli to na 20 miestach neplatí a je to presne tých 20 výplní bez
``ParentBoundary``. Skript hranicu steny doplní a rodiča dverám nastaví.

**Nefabrikuje sa geometria.** Vzniká vzťah, počítaný z geometrie, ktorá
v modeli už je — to isté, čo robila fáza 6b pre zvyšných 649. Hranice sú
bez ``ConnectionGeometry``, ako všetky ostatné (rozhodnutie 23).

Ako sa hostiteľ hľadá
---------------------
Kritériom kalibrovaným na **držanej vzorke**: dvere s ``FillsVoids`` majú
hostiteľa doloženého vzťahom, a to kritérium na nich sedí 24 z 24. Meria
sa v osiach steny — stred dverí v hrúbke steny, dvere po dĺžke vnútri
steny, zvislý rozsah v rozsahu steny, tenká os oboch tá istá. Nie podielom
pôdorysného prekryvu: dvere sú hrubšie než stena, lebo zárubňa presahuje
na obe strany, takže plošný podiel je systematicky pod 1 (§41).

Čo skript overí, kým niečo zmení
--------------------------------
* kritérium **musí prejsť držanú vzorku celú**; keď neprejde, skript sa
  zastaví a nič nezmení — kritérium, ktoré neprejde známu pravdu, nemeria
  model, ale samo seba;
* hostiteľ musí byť **jednoznačný** — práve jeden kandidát;
* stena nesmie už hranicou toho priestoru byť;
* stena musí na priestor liehať. Prah je **1 mm**, nie nula: bbox sa
  počíta v metroch a násobí tisícom, takže dotyk vyjde ako 1,5·10⁻¹¹ mm,
  nie ako presná nula. Skutočná najväčšia medzera sa vypisuje.

Atribúty sa preberajú z fázy 6b doslova: ``PHYSICAL``,
``InternalOrExternalBoundary`` z ``IsExternal`` prvku (occurrence, potom
typ), meno ``"<priestor> / <prvok>"``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.guid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_boundaries import (  # noqa: E402
    bboxes, host_z_fillsvoids, sedi_v_stene, odvod_z_polohy, tenka_os,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v26.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v27.ifc")

#: Dotyk bboxov nevyjde ako presná nula — počítajú sa v metroch a násobia
#: tisícom, takže zostane rádovo 1e-11 mm. Prah je 1 mm, čo je stále
#: o tri rády pod hrúbkou akejkoľvek škáry v modeli.
MAX_MEDZERA = 1.0


def is_external(e):
    """Prevzaté z ``23_space_boundaries.py`` — occurrence, potom typ."""
    for r in (getattr(e, "IsDefinedBy", None) or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcPropertySet"):
                for p in (d.HasProperties or ()):
                    if p.Name == "IsExternal" and p.is_a("IfcPropertySingleValue"):
                        return bool(p.NominalValue.wrappedValue)
    t = getattr(e, "IsTypedBy", None)
    if t:
        for p in (t[0].RelatingType.HasPropertySets or ()):
            if p.is_a("IfcPropertySet"):
                for q in (p.HasProperties or ()):
                    if q.Name == "IsExternal" and q.is_a("IfcPropertySingleValue"):
                        return bool(q.NominalValue.wrappedValue)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dry = not args.apply

    m = ifcopenshell.open(args.src)
    rels = m.by_type("IfcRelSpaceBoundary")
    print("vstup :", args.src)
    print("hraníc:", len(rels))

    hranice = {}
    for r in rels:
        if r.RelatingSpace is None or r.RelatedBuildingElement is None:
            continue
        hranice[(r.RelatingSpace.id(), r.RelatedBuildingElement.id())] = r
    je_hranicou = collections.defaultdict(set)
    for (sid, eid) in hranice:
        je_hranicou[sid].add(eid)

    steny = list(m.by_type("IfcWall"))
    prvky = sorted({r.RelatedBuildingElement for r in rels
                    if r.RelatedBuildingElement is not None}, key=lambda e: e.id())
    ebox = bboxes(m, prvky + steny + list(m.by_type("IfcSpace")))

    # ---- kalibrácia: kritérium musí prejsť držanú vzorku -----------------
    vzorka = trafene = 0
    for (sid, eid), r in hranice.items():
        e = m.by_id(eid)
        if not e.is_a("IfcDoor"):
            continue
        pravda = host_z_fillsvoids(e)
        if pravda is None:
            continue
        wb = ebox.get(pravda.GlobalId)
        db = ebox.get(e.GlobalId)
        if wb is None or db is None:
            continue
        vzorka += 1
        if all(sedi_v_stene(db, wb).values()):
            trafene += 1
    print("kalibrácia kritéria na držanej vzorke: %d z %d" % (trafene, vzorka))
    if not vzorka or trafene != vzorka:
        sys.exit("kritérium neprešlo držanú vzorku — nemeria model, ale samo "
                 "seba. Zastavené, nič sa nemení.")

    # ---- plán ------------------------------------------------------------
    plan = []          # (priestor, stena)
    podla_dveri = {}
    najhorsia = [0.0]
    for (sid, eid), r in sorted(hranice.items()):
        e = m.by_id(eid)
        if not (e.is_a("IfcDoor") or e.is_a("IfcWindow")):
            continue
        if getattr(r, "ParentBoundary", None) is not None:
            continue
        db, sb = ebox.get(e.GlobalId), ebox.get(m.by_id(sid).GlobalId)
        if db is None or sb is None:
            continue
        kand = [w for w in steny if ebox.get(w.GlobalId)
                and all(sedi_v_stene(db, ebox[w.GlobalId]).values())]
        vonku = [w for w in kand if w.id() not in je_hranicou[sid]]
        if not vonku:
            continue
        if len(vonku) > 1:
            sys.exit("dvere %s v %s majú %d kandidátov na hostiteľa — "
                     "jednoznačné to nie je. Zastavené."
                     % (e.Name, m.by_id(sid).Name, len(vonku)))
        w = vonku[0]
        wb = ebox[w.GlobalId]
        medzera = max(max(0.0, max(sb[i], wb[i]) - min(sb[i + 3], wb[i + 3]))
                      for i in range(3))
        if medzera > MAX_MEDZERA:
            sys.exit("stena %s nelieha na priestor %s (medzera %.3f mm). "
                     "Zastavené." % (w.Name, m.by_id(sid).Name, medzera))
        najhorsia[0] = max(najhorsia[0], medzera)
        podla_dveri[r.id()] = (sid, w.id())
        plan.append((sid, w.id()))

    pary = sorted(set(plan))
    print("najväčšia medzera stena↔priestor: %.3g mm (prah %.1f)"
          % (najhorsia[0], MAX_MEDZERA))
    print("výplní bez rodiča, ktorým hostiteľ chýba medzi hranicami:", len(plan))
    print("z toho rôznych dvojíc (priestor, stena):", len(pary))
    for sid, wid in pary:
        print("    %-10s ← %-16s" % (m.by_id(sid).Name, m.by_id(wid).Name))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    owner = m.by_type("IfcSpace")[0].OwnerHistory
    added = []
    nove = {}
    for sid, wid in pary:
        sp, w = m.by_id(sid), m.by_id(wid)
        ext = is_external(w)
        gid = ifcopenshell.guid.new()
        rel = m.create_entity(
            "IfcRelSpaceBoundary1stLevel",
            GlobalId=gid, OwnerHistory=owner,
            Name="%s / %s" % (sp.Name, w.Name),
            RelatingSpace=sp, RelatedBuildingElement=w,
            ConnectionGeometry=None,
            PhysicalOrVirtualBoundary="PHYSICAL",
            InternalOrExternalBoundary=("EXTERNAL" if ext else
                                        "INTERNAL" if ext is False else "NOTDEFINED"))
        nove[(sid, wid)] = rel
        added.append(gid)

    napojene = 0
    for rid, (sid, wid) in podla_dveri.items():
        m.by_id(rid).ParentBoundary = nove[(sid, wid)]
        napojene += 1

    print("\nzaložených hraníc :", len(added))
    print("napojených rodičov:", napojene)
    m.write(args.dst)
    print("zapísané:", args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": added}, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
