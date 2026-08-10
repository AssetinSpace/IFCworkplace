"""Fáza 7 — polia ľahkého obvodového plášťa.

Register: LOP, §2 „Fasáda LOP" a §18.

    python src/24_lop_fields.py           # dry-run
    python src/24_lop_fields.py --apply   # zapíše out/ASR_v12.ifc

Čo robí
-------
Delí 12 `PL01` na **48 vnorených `IfcCurtainWall`** podľa výkresu
`D.1.1.08`, prevesí na ne diely a doplní `Pset_CurtainWallCommon`
s `ThermalTransmittance` a `Qto_CurtainWallQuantities` z geometrie.

Odkiaľ sa berie delenie
-----------------------
Nie z rastra výkresu, ale z **osnovy v modeli**: zhluky stĺpov dávajú
6 osí v X po 6500 mm a 4 osi v Y. Červené deliace čiary na `D.1.1.08`
ležia práve na nich. Dlhá fasáda sa tak delí na 5 polí, krátka na 3 —
16 na podlažie, 48 spolu, presne ako výkres.

Orientácia
----------
`2.02 Openspace - Východ` leží na `Y = −2703`, `2.01 Západ` na `Y = +7922`,
takže **−Y je východ**. Pri klasickej konvencii (sever hore, východ
vpravo) z toho vychádza **sever = +X** — rozhodnutie Samuela.

Poradie názvov je preto v smere rastúcej súradnice, čo pre západ a juh
znamená opačné poradie, než v akom sú kódy na výkrese: tie pohľady sa
kreslia zrkadlovo (pozorovateľ stojí na druhej strane).

Odchýlka od podkladu
--------------------
Južný pohľad má v treťom poli 1NP kód `C1-S`, hoci systematicky tam patrí
`C1-J`, a `C1-J` sa vo výkrese nevyskytuje. Model používa `C1-J`;
odchýlka je zapísaná v registri a patrí do BEP.

Mená inštancií
--------------
Kód nesie **typ poľa**, nie kus — `E3-V` je na východe trikrát. Za kód sa
preto pridáva poradie v rámci kódu, rovnakým princípom ako INST pri SNIM
(rozhodnutie 1 a 2), len na dve miesta: `E3-V.01`.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v11.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v12.ifc")

DRY_RUN = True

#: poznámka výkresu D.1.1.08: „uvažovaný súčiniteľ prestupu tepla podľa
#: teplo-technickej analýzy U_cw = 0,64 W/m²K"
UCW = 0.64

#: systém z tej istej poznámky
SYSTEM = "SCHUECO FWS 50.SI"

#: vnútorné osi, na ktorých sa fasáda delí (mm) — zo zhlukov stĺpov
AXES_X = (36885.0, 43385.0, 49885.0, 56385.0)
AXES_Y = (-1141.0, 6359.0)

#: názvy polí v smere **rastúcej** súradnice
FIELDS = {
    ("V", "1NP"): ["I1-V", "K1-V", "L1-V", "K1-V", "D1-V"],
    ("V", "2NP"): ["M2-V", "E2-V", "E2-V", "E2-V", "C2-V"],
    ("V", "3NP"): ["M3-V", "E3-V", "E3-V", "E3-V", "C3-V"],
    ("Z", "1NP"): ["I1-Z", "H1-Z", "G1-Z", "F1-Z", "D1-Z"],
    ("Z", "2NP"): ["M2-Z", "E2-Z", "E2-Z", "E2-Z", "C2-Z"],
    ("Z", "3NP"): ["M3-Z", "E3-Z", "E3-Z", "E3-Z", "C3-Z"],
    ("S", "1NP"): ["C1-S", "B1-S", "A1-S"],
    ("S", "2NP"): ["C2-S", "B2-S", "A2-S"],
    ("S", "3NP"): ["C3-S", "B3-S", "A3-S"],
    ("J", "1NP"): ["C1-J", "B1-J", "A1-J"],   # výkres tu má C1-S, viď §18
    ("J", "2NP"): ["C2-J", "B2-J", "A2-J"],
    ("J", "3NP"): ["C3-J", "B3-J", "A3-J"],
}

SMER = {"V": "východ", "Z": "západ", "S": "sever", "J": "juh"}


def bboxes(model, products):
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


def storey_of(e):
    for r in (getattr(e, "ContainedInStructure", None) or ()):
        return r.RelatingStructure
    for r in (getattr(e, "Decomposes", None) or ()):
        return storey_of(r.RelatingObject)
    return None


def detach_containment(model, e, removed):
    for rid in [r.id() for r in (getattr(e, "ContainedInStructure", None) or ())]:
        rel = model.by_id(rid)
        rest = tuple(x for x in rel.RelatedElements if x.id() != e.id())
        if rest:
            rel.RelatedElements = rest
        else:
            removed.append(rel.GlobalId)
            model.remove(rel)


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
    removed: list[str] = []

    pl = [e for e in m.by_type("IfcCurtainWall") if (e.Name or "").startswith("PL01")]
    if any(any(o.is_a("IfcCurtainWall") for o in r.RelatedObjects)
           for e in pl for r in (e.IsDecomposedBy or ())):
        print("polia už existujú — skript je idempotentný, končí")
        return 0
    if len(pl) != 12:
        raise SystemExit("STOP: čakám 12 PL01, našiel som %d" % len(pl))

    parts = {e.GlobalId: [o for r in (e.IsDecomposedBy or ()) for o in r.RelatedObjects]
             for e in pl}
    box = bboxes(m, [p for v in parts.values() for p in v])

    # ---- klasifikácia fasád ---------------------------------------------
    info = {}
    for e in pl:
        bs = [box[p.GlobalId] for p in parts[e.GlobalId] if p.GlobalId in box]
        if not bs:
            raise SystemExit("STOP: %s nemá diely s tvarom" % e.Name)
        b = (min(x[0] for x in bs), min(x[1] for x in bs), min(x[2] for x in bs),
             max(x[3] for x in bs), max(x[4] for x in bs), max(x[5] for x in bs))
        dx, dy = b[3] - b[0], b[4] - b[1]
        if dx > dy:                       # beží pozdĺž X → východ alebo západ
            smer = "V" if (b[1] + b[4]) / 2 < 0 else "Z"
            axis, axes = 0, AXES_X
        else:                             # beží pozdĺž Y → sever alebo juh
            smer = "S" if (b[0] + b[3]) / 2 > 46635 else "J"
            axis, axes = 1, AXES_Y
        st = storey_of(e)
        info[e.GlobalId] = (smer, st.Name, axis, axes, b)

    print("FASÁDY")
    for e in sorted(pl, key=lambda x: x.Name):
        smer, stn, axis, axes, b = info[e.GlobalId]
        print("   %-12s %-6s %-8s polí %d  dielov %d"
              % (e.Name, stn, SMER[smer], len(axes) + 1, len(parts[e.GlobalId])))

    # ---- rozdelenie dielov a založenie polí ------------------------------
    poradie: collections.Counter = collections.Counter()
    vyrobene = []
    for e in sorted(pl, key=lambda x: x.Name):
        smer, stn, axis, axes, b = info[e.GlobalId]
        mena = FIELDS[(smer, stn)]
        if len(mena) != len(axes) + 1:
            raise SystemExit("STOP: %s čaká %d polí, tabuľka má %d"
                             % (e.Name, len(axes) + 1, len(mena)))

        kose = [[] for _ in mena]
        for p in parts[e.GlobalId]:
            pb = box.get(p.GlobalId)
            if pb is None:
                kose[0].append(p)          # bez tvaru — k prvému poľu
                continue
            c = (pb[axis] + pb[axis + 3]) / 2.0
            i = 0
            while i < len(axes) and c >= axes[i]:
                i += 1
            kose[i].append(p)

        prazdne = [mena[i] for i, k in enumerate(kose) if not k]
        if prazdne:
            raise SystemExit("STOP: %s — pole bez dielov: %s" % (e.Name, prazdne))

        polia = []
        for i, (kod, diely) in enumerate(zip(mena, kose)):
            poradie[kod] += 1
            nazov = "%s.%02d" % (kod, poradie[kod])
            pole = m.create_entity(
                "IfcCurtainWall",
                GlobalId=ifcopenshell.guid.new(), OwnerHistory=e.OwnerHistory,
                Name=nazov,
                Description="Pole LOP %s, %s, %s; %s" % (kod, SMER[smer], stn, SYSTEM))
            added.append(pole.GlobalId)
            polia.append(pole)

            # diely z rodiča na pole; Decomposes je SET[0:1], takže presun
            for p in diely:
                for r in list(p.Decomposes or ()):
                    rest = tuple(x for x in r.RelatedObjects if x.id() != p.id())
                    if rest:
                        r.RelatedObjects = rest
                    else:
                        removed.append(r.GlobalId)
                        m.remove(r)
                detach_containment(m, p, removed)
            rel = m.create_entity(
                "IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=e.OwnerHistory, RelatingObject=pole,
                RelatedObjects=tuple(diely))
            added.append(rel.GlobalId)

            bs = [box[p.GlobalId] for p in diely if p.GlobalId in box]
            fb = (min(x[0] for x in bs), min(x[1] for x in bs), min(x[2] for x in bs),
                  max(x[3] for x in bs), max(x[4] for x in bs), max(x[5] for x in bs))
            dlzka = fb[3] - fb[0] if axis == 0 else fb[4] - fb[1]
            hrubka = fb[4] - fb[1] if axis == 0 else fb[3] - fb[0]
            vyska = fb[5] - fb[2]
            plocha = dlzka * vyska / 1e6

            pset = m.create_entity(
                "IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=e.OwnerHistory, Name="Pset_CurtainWallCommon",
                HasProperties=[
                    m.create_entity("IfcPropertySingleValue", Name="Reference",
                                    NominalValue=m.create_entity("IfcIdentifier", kod)),
                    m.create_entity("IfcPropertySingleValue", Name="IsExternal",
                                    NominalValue=m.create_entity("IfcBoolean", True)),
                    m.create_entity(
                        "IfcPropertySingleValue", Name="ThermalTransmittance",
                        NominalValue=m.create_entity(
                            "IfcThermalTransmittanceMeasure", UCW))])
            qto = m.create_entity(
                "IfcElementQuantity", GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=e.OwnerHistory, Name="Qto_CurtainWallQuantities",
                Quantities=[
                    m.create_entity("IfcQuantityLength", Name="Length", LengthValue=dlzka),
                    m.create_entity("IfcQuantityLength", Name="Height", LengthValue=vyska),
                    m.create_entity("IfcQuantityLength", Name="Width", LengthValue=hrubka),
                    m.create_entity("IfcQuantityArea", Name="GrossSideArea",
                                    AreaValue=round(plocha, 4)),
                    m.create_entity("IfcQuantityArea", Name="NetSideArea",
                                    AreaValue=round(plocha, 4))])
            for d in (pset, qto):
                r = m.create_entity(
                    "IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                    OwnerHistory=e.OwnerHistory, RelatedObjects=(pole,),
                    RelatingPropertyDefinition=d)
                added.extend([d.GlobalId, r.GlobalId])

            vyrobene.append((nazov, SMER[smer], stn, len(diely), dlzka, vyska, plocha))

        # rodič teraz agreguje polia namiesto jednotlivých dielov
        rel = m.create_entity(
            "IfcRelAggregates", GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=e.OwnerHistory, RelatingObject=e,
            RelatedObjects=tuple(polia))
        added.append(rel.GlobalId)

    print("\nPOLIA")
    for n, s, st, d, dl, v, pl_ in vyrobene:
        print("   %-10s %-8s %-5s dielov %4d  %6.0f × %5.0f mm  %7.2f m²"
              % (n, s, st, d, dl, v, pl_))
    print("   ---- %d polí, súčet %.2f m²" % (len(vyrobene), sum(x[6] for x in vyrobene)))

    bad = [e for e in m.by_type("IfcObjectDefinition")
           if getattr(e, "Decomposes", None) and getattr(e, "ContainedInStructure", None)]
    if bad:
        raise SystemExit("STOP: invariant 7 porušený na %d prvkoch" % len(bad))
    print("   kontrola inv 7: 0 prvkov s dvojitou väzbou")

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
