"""Fáza 5b — priestory (#I #Z #R).

    python src/20_fix_spaces.py           # dry-run
    python src/20_fix_spaces.py --apply   # zapíše out/ASR_v8.ifc

Čo robí
-------
A  #I  14 MEP priestorov prečísluje a pomenuje podľa ``AUDIT.md`` §6.
       Umiestnenie sa **nemení**, mení sa len ``Name`` a ``LongName``;
       ``PredefinedType`` ostáva ``INTERNAL``.
B  #Z  22 rekonštruovaných priestorov na 1NP dostane
       ``Qto_BodyGeometryValidation`` (``NetSurfaceArea``, ``NetVolume``)
       dopočítaný z ich vlastnej geometrie.
C  #R  vypíše zosúhlasenie plôch po podlažiach.

Čo NEROBÍ a prečo
-----------------
* **#J šachty na 1NP** — rekonštrukcia geometrie, Samuel si ju vyhradil
  na samostatný rozhovor.
* **#Q prenajímateľná zóna pre 3NP** — prenajímateľnosť nesú
  ``IfcSpatialZone`` ``PZ01``–``PZ10`` zoskupené do ``IfcZone``
  „Pronajmutelné". Nová zóna pre 3NP by znamenala **vyrobiť geometriu**,
  ktorá v modeli nie je, a to §8 zakazuje. Treba rozhodnutie.

Kontrola výpočtu
----------------
``NetSurfaceArea`` a ``NetVolume`` sa počítajú z trianguláce: plocha ako
súčet plôch trojuholníkov, objem cez divergenčnú vetu. Overené proti 47
priestorom, ktoré ten ``Qto`` už majú — zhoda na dve desatinné miesta.
Jednotky sú m² a m³ priamo z ``create_shape``; súbor má síce dĺžky v mm,
ale ``AREAUNIT`` je ``SQUARE_METRE`` a ``VOLUMEUNIT`` ``CUBIC_METRE``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v7.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v8.ifc")

DRY_RUN = True

QTO_NAME = "Qto_BodyGeometryValidation"

#: AUDIT.md §6 — (podlažie, staré) → (nové, LongName, kontrolná plocha m²)
RENUMBER = {
    ("2NP", "1.31"): ("2.15", "Inštalačná šachta", 2.89),
    ("2NP", "1.34"): ("2.16", "Inštalačná šachta", 1.23),
    ("2NP", "1.36"): ("2.17", "Inštalačná šachta", 1.29),
    ("2NP", "1.35"): ("2.18", "Inštalačná šachta", 5.05),
    ("2NP", "1.28"): ("2.19", "Inštalačná šachta", 0.75),
    ("2NP", "1.29"): ("2.20", "Schodiskový priestor", 19.71),
    ("3NP", "2.22"): ("3.15", "Inštalačná šachta", 2.89),
    ("3NP", "2.29"): ("3.16", "Inštalačná šachta", 1.29),
    ("3NP", "2.28"): ("3.17", "Inštalačná šachta", 5.05),
    ("3NP", "2.20"): ("3.18", "Inštalačná šachta", 0.75),
    ("3NP", "2.27"): ("3.19", "Inštalačná šachta", 1.48),
    ("3NP", "2.26"): ("3.20", "Schodiskový priestor", 17.82),
    ("4NP", "3.21"): ("4.05", "Inštalačná šachta", 1.48),
    ("4NP", "3.20"): ("4.06", "Schodiskový priestor", 17.15),
}
AREA_TOL = 0.02


def storey_name(s):
    for r in (s.Decomposes or ()):
        return r.RelatingObject.Name
    return None


def quantities(space, qto_name):
    for r in (space.IsDefinedBy or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcElementQuantity") and d.Name == qto_name:
                return d
    return None


def net_floor_area(space):
    for r in (space.IsDefinedBy or ()):
        if r.is_a("IfcRelDefinesByProperties"):
            d = r.RelatingPropertyDefinition
            if d.is_a("IfcElementQuantity"):
                for q in d.Quantities:
                    if q.Name == "NetFloorArea":
                        return q.AreaValue
    return None


def mesh_area_volume(shape):
    """Plocha povrchu a objem z trianguláce, v m² a m³."""
    v, f = shape.geometry.verts, shape.geometry.faces
    area = vol = 0.0
    for i in range(0, len(f), 3):
        p = [v[f[i + k] * 3: f[i + k] * 3 + 3] for k in range(3)]
        ux, uy, uz = (p[1][j] - p[0][j] for j in range(3))
        wx, wy, wz = (p[2][j] - p[0][j] for j in range(3))
        cx = uy * wz - uz * wy
        cy = uz * wx - ux * wz
        cz = ux * wy - uy * wx
        area += 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5
        vol += (p[0][0] * cx + p[0][1] * cy + p[0][2] * cz) / 6.0
    return area, abs(vol)


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
    log: list[str] = []
    spaces = list(m.by_type("IfcSpace"))

    # ---- A · #I prečíslovanie podľa §6 ----------------------------------
    plan = []
    for s in spaces:
        target = RENUMBER.get((storey_name(s), s.Name))
        if target is None:
            continue
        new, longname, area = target
        got = net_floor_area(s)
        if got is None or abs(got - area) > AREA_TOL:
            raise SystemExit(
                "STOP: %s/%s má plochu %s, §6 čaká %.2f — nesedí mapovanie"
                % (storey_name(s), s.Name, got, area))
        plan.append((s, new, longname))
    for s, new, longname in plan:            # naraz, až po overení všetkých
        s.Name = new
        s.LongName = longname
    if plan:
        log.append("#I   prečíslovaných MEP priestorov: %d" % len(plan))
        for s, new, longname in plan:
            log.append("       %-5s → %-5s  %s" % (
                next(k[1] for k, v in RENUMBER.items() if v[0] == new), new, longname))
    else:
        already = sum(1 for s in spaces
                      if (storey_name(s), s.Name) in
                      {(k[0], v[0]) for k, v in RENUMBER.items()})
        log.append("#I   už prečíslované (%d priestorov) — preskočené" % already)

    # ---- B · #Z Qto_BodyGeometryValidation ------------------------------
    missing = [s for s in spaces if quantities(s, QTO_NAME) is None and s.Representation]
    if missing:
        template = None
        for s in spaces:
            d = quantities(s, QTO_NAME)
            if d is not None:
                template = d
                break
        st = ifcopenshell.geom.settings()
        st.set("use-world-coords", True)
        it = ifcopenshell.geom.iterator(
            st, m, max(1, (os.cpu_count() or 2) - 1), include=missing)
        done = 0
        if it.initialize():
            while True:
                sh = it.get()
                space = m.by_guid(sh.guid)
                area, vol = mesh_area_volume(sh)
                q = m.create_entity(
                    "IfcElementQuantity",
                    GlobalId=ifcopenshell.guid.new(),
                    OwnerHistory=space.OwnerHistory,
                    Name=QTO_NAME,
                    MethodOfMeasurement=(template.MethodOfMeasurement
                                         if template is not None else None),
                    Quantities=(
                        m.create_entity("IfcQuantityArea",
                                        Name="NetSurfaceArea", AreaValue=area),
                        m.create_entity("IfcQuantityVolume",
                                        Name="NetVolume", VolumeValue=vol),
                    ),
                )
                rel = m.create_entity(
                    "IfcRelDefinesByProperties",
                    GlobalId=ifcopenshell.guid.new(),
                    OwnerHistory=space.OwnerHistory,
                    RelatedObjects=(space,),
                    RelatingPropertyDefinition=q,
                )
                added.extend([q.GlobalId, rel.GlobalId])
                done += 1
                if not it.next():
                    break
        log.append("#Z   %s doplnený na %d priestorov (%s)"
                   % (QTO_NAME, done,
                      dict(collections.Counter(storey_name(s) for s in missing))))
    else:
        log.append("#Z   %s má už každý priestor — preskočené" % QTO_NAME)

    # ---- C · #R zosúhlasenie plôch --------------------------------------
    per = collections.Counter()
    for s in m.by_type("IfcSpace"):
        a = net_floor_area(s)
        if a:
            per[storey_name(s)] += a

    print("ZMENY")
    for line in log:
        print("  " + line)
    print("\n#R  ZOSÚHLASENIE PLÔCH")
    for k in sorted(per, key=str):
        print("     %-5s %8.2f m²  (%d priestorov)"
              % (k, per[k], sum(1 for s in m.by_type("IfcSpace") if storey_name(s) == k)))
    print("     %-5s %8.2f m²  spolu, %d priestorov"
          % ("", sum(per.values()), len(m.by_type("IfcSpace"))))
    print("     handover uvádzal 2031.95 m² — rozdiel %.2f m²"
          % (2031.95 - sum(per.values())))
    print("\n  GlobalId nových: %d" % len(added))
    print("  NEROBÍ: #J šachty na 1NP a #Q zóna pre 3NP — obe potrebujú rozhodnutie")

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    m.write(args.dst)
    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(added)},
                  fh, ensure_ascii=False, indent=2)
    print("\nzapísané:", args.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
