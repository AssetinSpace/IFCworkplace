"""Fáza 19 — #BC: kontajnment podlaží podľa pásiem z nosných dosiek.

    python src/38_storey_zones.py           # dry-run
    python src/38_storey_zones.py --apply   # zapíše out/ASR_v26.ifc

Čo sa opravuje
--------------
Prvok kontajnovaný v podlaží, ktorého **pásmo ho neobsahuje**, sa presunie
do podlažia, v ktorého pásme leží väčšina jeho výšky. Pásmo je definované
v ``spatial.storey_zones`` — od vrchu nosnej dosky po vrch nasledujúcej,
nie od `Elevation`.

Prečo to bola jedna vada a nie tri
----------------------------------
Samuel hlásil tri veci: strešné vpuste na 3NP, stĺpy „náhodne" na dvoch
podlažiach a dvere len na podlaží. Prvé dve majú **spoločný koreň**:

* `Elevation` je čistá podlaha, ale stĺp aj priečka toho istého podlažia
  začínajú 150 mm nižšie, na vrchu nosnej dosky. Pásmo počítané od
  `Elevation` ich preto hodí o podlažie nižšie;
* v origináli z Revitu to nebolo dôsledné ani v jednom smere — 16 stĺpov
  `SL02.01` s **rovnakým** rozsahom `9050…13000` je 6× v 2NP a 10× v 3NP.
  Tá nedôslednosť je presne to „random", ktoré vidno v strome;
* strešné vpuste sedia v súvrství strechy `13040…13836`, teda **na
  rozhraní** 3NP a 4NP. Ťažisko rozhodovalo raz tak, raz onak, takže
  osem skončilo v 3NP a osem v 4NP — pritom obe skupiny prechádzajú tou
  istou strechou `ST01.0001`, ktorá je v 4NP.

Tretia vec — dvere — je vec izby, nie podlažia, a rieši ju fáza 20.

Čo pravidlo **ne**smie spraviť
------------------------------
Skladba podlahy `PD02.44.01` má rozsah `4850…5000`, teda leží celá **pod**
`Elevation` 2NP, a do 2NP patrí správne. Naivné pásmo od `Elevation` by ju
presunulo do 1NP — teda by vyrobilo novú vadu. Posunuté pásmo ju necháva
tam, kde je. Overuje sa to kontrolou na konci behu.

Pasce
-----
* prvky **v priestore** (`IfcSpace`) sa nepresúvajú — priestor je pod
  podlažím, jeho kontajnment je konkrétnejší a rieši ho fáza 20;
* agregované prvky sa nepresúvajú vôbec — do štruktúry ich viaže celok
  (invariant 7);
* ``IfcRelContainedInSpatialStructure`` je pre prvok jediný — presun je
  odobratie zo starého a pridanie do nového, nie druhý vzťah.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ifcutil import detach_from_containment  # noqa: E402
import spatial  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v25.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v26.ifc")

DRY_RUN = True

#: o koľko musí navrhované pásmo vyhrať nad súčasným, aby sa prvok presunul.
#:
#: Prah nie je zvolený od oka — je zmeraný. Prvky, ktoré presunúť treba,
#: vyhrávajú aspoň o 23 percentuálnych bodov (najtesnejšia je strešná vpusť
#: `OV04.01.197`, 38 % v 3NP proti 61 % v 4NP, lebo jej telo sedí v súvrství
#: rozkročenom cez rozhranie). Prvky, ktoré presunúť netreba, lebo cez
#: rozhranie idú zámerne, vyhrávajú najviac o 6 bodov: stena schodiska
#: `SN02.03.0013` 49/51 a schodisko `ZV04.01.0001` 47/53. Medzi 6 a 23 je
#: dosť miesta; 20 leží v ňom.
MIN_GAIN = 0.20

#: pod týmto podielom v aktuálnom pásme sa prvok v záverečnej správe hlási
#: ako rozkročený cez rozhranie. Nie je to podmienka presunu.
MAX_STAY = 0.50


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
    removed: list[str] = []

    zones = spatial.storey_zones(m)
    print("PÁSMA PODLAŽÍ (vrch nosnej dosky → vrch nasledujúcej)")
    for st, (lo, hi) in sorted(zones.items(), key=lambda kv: kv[1][0]):
        print("  %-5s Elevation=%9.1f   pásmo %11s … %s"
              % (st.Name, st.Elevation or 0.0,
                 "-∞" if lo == -float("inf") else "%.1f" % lo,
                 "∞" if hi == float("inf") else "%.1f" % hi))
    print()

    # ---- A · prvok patrí do podlažia, v ktorého pásme leží ---------------
    # kandidáti: kontajnované **priamo v podlaží**, s tvarom, neagregované
    cand = [e for e in m.by_type("IfcElement")
            if e.Representation is not None
            and not getattr(e, "Decomposes", None)
            and isinstance(spatial.container_of(e), ifcopenshell.entity_instance)
            and spatial.container_of(e).is_a("IfcBuildingStorey")]
    box = spatial.boxes(m, cand)

    moves: list = []
    straddling: list = []
    for e in cand:
        b = box.get(e.GlobalId)
        if b is None:
            continue
        cur = spatial.container_of(e)
        own = spatial.zone_share(b, zones[cur])
        best, share = spatial.zone_storey(b, zones)
        if best.id() == cur.id():
            continue
        if share - own < MIN_GAIN:
            straddling.append((e, cur, best, own, share, b))
            continue
        moves.append((e, cur, best, own, share, b))

    if not moves:
        print("ZMENY\n  kontajnment už sedí s pásmami — preskočené")
    else:
        rozpad = collections.Counter(
            (e.is_a(), cur.Name, new.Name) for e, cur, new, _, _, _ in moves)
        print("ZMENY  %d prvkov" % len(moves))
        for (cls, a, b_), n in sorted(rozpad.items(), key=lambda kv: -kv[1]):
            print("  %-16s %s → %-4s  %3d ks" % (cls.replace("Ifc", ""), a, b_, n))
        print()
        print("  rozpis")
        for e, cur, new, own, share, b in sorted(moves, key=lambda x: x[0].Name or ""):
            print("    %-16s %-14s %s → %-4s  z=%9.1f…%-9.1f  %3.0f%% → %3.0f%%"
                  % (e.Name, e.is_a().replace("Ifc", ""), cur.Name, new.Name,
                     b[2], b[5], own * 100, share * 100))
        # referenciu na nové podlažie, ktorá sa presunom stane duplicitou
        # kontajnmentu, zmetie oddiel C
        for e, _, new, _, _, _ in moves:
            detach_from_containment(m, e, removed)
            spatial.contain_in(m, new, e, added)

    # ---- B · prvok rozkročený cez rozhranie ------------------------------
    # Kontajnment ostáva, ale druhé podlažie sa dopĺňa ako **referencia** —
    # presne prípad z dokumentácie: „A curtain wall might span through
    # several stories, in this case it can be contained within the ground
    # floor, but it would be referenced by all additional stories it spans."
    if straddling:
        print()
        print("  rozkročené cez rozhranie — kontajnment ostáva, dopĺňa sa referencia")
        for e, cur, new, own, share, b in straddling:
            had = any(x.id() == new.id() for x in spatial.references_of(e))
            if not had:
                spatial.reference_in(m, new, e, added)
            print("    %-16s %-14s ostáva v %s (%3.0f %%), referencia %s (%3.0f %%)%s"
                  % (e.Name, e.is_a().replace("Ifc", ""), cur.Name, own * 100,
                     new.Name, share * 100, "  [už bola]" if had else "  [nová]"))

    # ---- C · referencia na vlastný kontajner je nadbytočná ---------------
    # „IfcRelReferencedInSpatialStructure is used to assign elements **in
    # addition to** those levels …, but **not primarily contained**."
    # Referencia na to isté podlažie, v ktorom je prvok kontajnovaný, teda
    # nehovorí nič — a po presunoch vyššie by ich pribudlo.
    dup = 0
    for rel in list(m.by_type("IfcRelReferencedInSpatialStructure")):
        target = rel.RelatingStructure
        for e in list(rel.RelatedElements):
            cur = spatial.container_of(e)
            if cur is not None and cur.id() == target.id():
                spatial.drop_reference(m, target, e, removed)
                dup += 1
    print()
    print("  nadbytočných referencií na vlastný kontajner zrušených: %d" % dup)

    # ---- kontroly na vlastnom výsledku ----------------------------------
    print()
    print("KONTROLY")

    bad = [e for e in m.by_type("IfcObjectDefinition")
           if getattr(e, "Decomposes", None)
           and getattr(e, "ContainedInStructure", None)]
    if bad:
        raise SystemExit("STOP: invariant 7 porušený na %d prvkoch" % len(bad))
    print("  inv 7 · dvojitá väzba: 0")

    # každý prvok leží vo svojom pásme
    left = []
    for e in cand:
        b = box.get(e.GlobalId)
        cur = spatial.container_of(e)
        if b is None or not cur.is_a("IfcBuildingStorey"):
            continue
        if spatial.zone_share(b, zones[cur]) < MAX_STAY:
            left.append((e.Name, e.is_a(), cur.Name, b[2], b[5]))
    print("  prvkov pod %.0f %% vo svojom pásme: %d%s"
          % (MAX_STAY * 100, len(left),
             ("  — %s" % [x[0] for x in left][:6]) if left else ""))

    # Strešné vpuste tej istej strechy patria k sebe. Namiesto hľadania
    # hostiteľskej strechy — súvrstvie hornej strechy je v modeli rozdelené
    # medzi obe agregácie `ST01`, takže hostiteľ vyjde raz tak, raz onak —
    # sa kontroluje priamo to, čo Samuel hlásil: vpuste, ktorých zvislé
    # rozsahy sa prekrývajú, sú v jednom podlaží.
    drains = [e for e in m.by_type("IfcFlowTerminal")
              if getattr(e, "PredefinedType", None) == "ROOFDRAIN"]
    dbox = spatial.boxes(m, drains)
    groups: list[list] = []
    for d in sorted(drains, key=lambda e: dbox.get(e.GlobalId, (0,) * 6)[2]):
        b = dbox.get(d.GlobalId)
        if b is None:
            continue
        for g in groups:
            if any(spatial.z_inter(b, dbox[x.GlobalId]) > 0.0 for x in g):
                g.append(d)
                break
        else:
            groups.append([d])
    split = []
    for g in groups:
        st = collections.Counter(
            (spatial.storey_of(spatial.container_of(x)) or type("", (), {"Name": "-"})).Name
            for x in g)
        zs = [dbox[x.GlobalId] for x in g]
        print("  vpuste z=%.0f…%.0f — %d ks, podlažia %s"
              % (min(z[2] for z in zs), max(z[5] for z in zs), len(g), dict(st)))
        if len(st) > 1:
            split.append(dict(st))
    if split:
        raise SystemExit("STOP: vpuste jednej strechy skončili na rôznych "
                         "podlažiach — %s" % split)

    # skladby podlahy pod Elevation zostali vo svojom podlaží
    finishes = [e for e in m.by_type("IfcCovering")
                if (e.Name or "").startswith("PD")]
    fbox = spatial.boxes(m, finishes)
    slipped = []
    for e in finishes:
        b = fbox.get(e.GlobalId)
        cur = spatial.container_of(e)
        st = spatial.storey_of(cur) if cur is not None else None
        if b is None or st is None:
            continue
        if b[5] <= (st.Elevation or 0.0) + 1.0 and spatial.zone_share(b, zones[st]) < 0.5:
            slipped.append(e.Name)
    print("  skladieb podlahy mimo svojho pásma: %d%s"
          % (len(slipped), ("  — %s" % slipped[:6]) if slipped else ""))

    print("\n  GlobalId nových: %d, zrušených: %d" % (len(added), len(removed)))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": sorted(set(removed)), "added": sorted(set(added))},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
