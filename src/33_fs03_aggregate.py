"""Fáza 14 — sedem `FS03.01` bez celku.

Register: #AO (zvyšok). Rozhodnutie 9 a §4 z ``AUDIT.md``.

    python src/33_fs03_aggregate.py            # dry-run
    python src/33_fs03_aggregate.py --apply    # zapíše out/ASR_v21.ifc

Čo robí
-------
Sedem `FS03.01` — obvodová izolácia základovej dosky, XPS 120 mm — nemá
celok, do ktorého by patrilo. Fáza 6a ich minula, lebo hľadala **stenu**,
ktorú krytina pokrýva, a tieto žiadnu nepokrývajú.

Skript ich agreguje do `ZD02.01.0001` a odoberie z kontajnmentu podlažia,
presne ako fáza 6a spravila s ostatnými krytinami.

Prečo práve základová doska
---------------------------
Zmerané na `ASR_v20.ifc`: **všetkých deväť** kusov `FS03.01` dosadá na ten
istý prvok, `ZD02.01.0001` (Z −800…−300). Sedem z nich sa nedotýka ničoho
iného. Izolácia má Z −800…0, takže pokrýva celú zvislú hranu dosky
(prekryv 500 mm, čiže plná hrúbka dosky) a pokračuje 300 mm nad ňu.

Typ sa volá **`Izolace_ZD_120`** — izolácia ZD, teda základovej dosky.
Meno, geometria aj dotyk hovoria to isté.

§4 test *„je časť fyzicky zviazaná s celkom a bez neho neexistuje?"*
vychádza kladne — XPS je k hrane dosky lepené. Precedens v §4 existuje:
*„S3 | `PD02` na doske, `IH01` pod doskou | áno | lepené, natavené
celoplošne"*. Krytina na doske do dosky patrí.

Čo NEROBÍ a prečo
-----------------
`FS03.01.0008` a `.0009` **nechávam tak.** Fáza 6a ich agregovala do stien
(`SN02.02.0019`, `SN05.01.0005`) a stena, ktorú pokrývajú, tam naozaj je.
Tým ale vzniká stav, že deväť kusov toho istého výrobku má dva rôzne
celky — sedem dosku, dva stenu. `.0009` je pritom obvodový pás dlhý
33 500 mm, teda tá istá vec ako `.0004`–`.0007`.

**To si žiada rozhodnutie, nie domnienku.** Zjednotiť by znamenalo
prerobiť časť fázy 6a, čo je nad rámec otvorenej položky registra, ktorá
znie „7× `FS03.01` bez priradenej steny". Skript preto rieši tých sedem
a nesúmernosť hlási.

Pasce
-----
* prvok nesmie byť súčasne agregovaný **aj** kontajnovaný — invariant 7.
  Po agregácii sa preto odoberá z `IfcRelContainedInSpatialStructure`.
* shape z ``create_shape`` sa drží v premennej (§31).
"""

from __future__ import annotations

import argparse
import json
import os

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.guid
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v20.ifc")
OUT = os.path.join(ROOT, "out", "ASR_v21.ifc")

DRY_RUN = True
HOSTITEL = "ZD02.01.0001"
TOL = 60.0          # mm, dotyk
MIN_PREKRYV_Z = 10.0


def bbox(settings, element):
    shape = ifcopenshell.geom.create_shape(settings, element)
    v = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3) * 1000.0
    del shape
    return v.min(0), v.max(0)


def dosada(a, b):
    """Dotýkajú sa telesá a prekrývajú sa vo zvislom smere?"""
    (alo, ahi), (blo, bhi) = a, b
    ox = min(ahi[0], bhi[0]) - max(alo[0], blo[0])
    oy = min(ahi[1], bhi[1]) - max(alo[1], blo[1])
    oz = min(ahi[2], bhi[2]) - max(alo[2], blo[2])
    return oz > MIN_PREKRYV_Z and ox > -TOL and oy > -TOL and max(ox, oy) > 200


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--out", dest="dst", default=OUT)
    args = ap.parse_args()
    dry = not args.apply

    model = ifcopenshell.open(args.src)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    print("vstup :", args.src)
    print("režim :", "DRY-RUN" if dry else "APPLY", "\n")

    host = [e for e in model.by_type("IfcSlab") if e.Name == HOSTITEL]
    if len(host) != 1:
        raise SystemExit("STOP: hostiteľ %r nájdený %d× (čakal som 1)"
                         % (HOSTITEL, len(host)))
    host = host[0]
    hb = bbox(settings, host)

    vsetky = [e for e in model.by_type("IfcCovering")
              if (e.Name or "").startswith("FS03.01")]
    volne = [e for e in vsetky if not e.Decomposes]
    obsadene = [(e, e.Decomposes[0].RelatingObject) for e in vsetky if e.Decomposes]

    print("hostiteľ: %s  Z %.0f..%.0f" % (HOSTITEL, hb[0][2], hb[1][2]))
    print("FS03.01 spolu %d, bez celku %d, s celkom %d\n"
          % (len(vsetky), len(volne), len(obsadene)))

    if not volne:
        print("Idempotencia: všetkých %d kusov už celok má, niet čo robiť."
              % len(vsetky))
        return 0

    # každý kus musí na hostiteľa naozaj dosadať — inak sa nefabrikuje väzba
    for e in volne:
        eb = bbox(settings, e)
        if not dosada(eb, hb):
            raise SystemExit("STOP: %s na %s nedosadá — väzba by bola vymyslená"
                             % (e.Name, HOSTITEL))
        oz = min(eb[1][2], hb[1][2]) - max(eb[0][2], hb[0][2])
        print("  %-16s Z %7.0f..%-7.0f  prekryv s doskou %5.0f mm  ✓"
              % (e.Name, eb[0][2], eb[1][2], oz))

    print("\nnesúmernosť, ktorú skript nerieši:")
    for e, rodic in sorted(obsadene, key=lambda x: x[0].Name or ""):
        print("  %-16s už agregované do %s %r"
              % (e.Name, rodic.is_a(), rodic.Name))

    if dry:
        print("\nDRY-RUN — nič sa nezapísalo. Spusti s --apply.")
        return 0

    # --- agregácia ---------------------------------------------------------
    owner = (model.by_type("IfcOwnerHistory") or [None])[0]
    existing = [r for r in host.IsDecomposedBy]
    nove_guid = []
    if existing:
        rel = existing[0]
        rel.RelatedObjects = tuple(rel.RelatedObjects) + tuple(volne)
    else:
        rel = model.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner,
            Name="Obvodová izolácia základovej dosky",
            RelatingObject=host, RelatedObjects=list(volne))
        nove_guid.append(rel.GlobalId)

    # --- odobrať z kontajnmentu (invariant 7) ------------------------------
    odobrane = 0
    for e in volne:
        for r in list(e.ContainedInStructure or []):
            zvysok = tuple(x for x in r.RelatedElements if x.id() != e.id())
            if zvysok:
                r.RelatedElements = zvysok
            else:
                model.remove(r)
            odobrane += 1

    print("\nagregovaných %d do %s, odobraných z kontajnmentu %d"
          % (len(volne), HOSTITEL, odobrane))

    model.write(args.dst)
    print("zapísané:", args.dst)

    with open(args.dst + ".allowlist.json", "w", encoding="utf-8") as fh:
        json.dump({"removed": [], "added": sorted(nove_guid)}, fh, indent=2)
        fh.write("\n")
    print("allowlist : %d nových GlobalId" % len(nove_guid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
