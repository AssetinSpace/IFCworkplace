"""Sonda: obstojí odvodenie hostiteľa dverí z fázy 6b? (**nič nemení**)

    python src/probe_boundaries.py                     # out/ASR_v26.ifc
    python src/probe_boundaries.py --in out/ASR_v11.ifc

Prečo
-----
``AUDIT.md`` §38 bod 5. Fáza 6b priradila 52 dverám ``ParentBoundary``
**z polohy**, lebo ``FillsVoids`` im chýba (#AZ). §38 to menuje ako
neoverené a má pravdu — skript vtedy dokázal, že odvodenie *prebehlo*,
nie že je *správne*.

Ako sa to dá overiť, keď „správnu odpoveď" nepoznáme
-----------------------------------------------------
Poznáme ju pri dverách, ktoré ``FillsVoids`` **majú**. Tam je hostiteľ
doložený reťazou ``IfcRelFillsElement`` → ``IfcOpeningElement`` →
``IfcRelVoidsElement``, teda vzťahom, nie odhadom. To je držaná vzorka:
pustí sa na ňu to isté odvodenie z polohy a porovná sa s pravdou.

Čo sonda meria
--------------
A  **držaná vzorka** — odvodenie z polohy proti ``FillsVoids``
B  **nezávislý geometrický test** priradených dvojíc, iným signálom než
   ktorým sa priraďovalo
C  **zhoda so schémou** — ``ParentBoundary`` v tom istom priestore,
   ``InnerBoundaries`` ako inverz, nikto nie je rodičom sám sebe
D  **výplne bez rodiča** a prečo
E  **chýbajúce hranice** — keď sú dvere hranicou priestoru, musí ňou byť
   aj stena, v ktorej sedia: dvere sú otvor **v nej**

Prečo bbox nestačí a ako sa test kalibruje
------------------------------------------
Fáza 6b hľadala stenu, ktorej bbox obsahuje stred bboxu dverí (+150 mm),
a brala tú s najmenším objemom bboxu. Bbox je osovo zarovnaný, takže pri
dlhej stene pokrýva veľký kus pôdorysu, v ktorom stena nie je; „najmenší
objem" je tie-break, nie dôkaz.

Prvá verzia tejto sondy merala **podiel pôdorysného prekryvu dverí
a steny** a označila 10 dvojíc za podozrivé. Bola to chyba testu, nie
modelu: **dvere sú hrubšie než stena** — zárubňa presahuje na obe strany
(275 mm dvere v 150 mm stene, 160 v 100, 375 v 250) — takže plošný podiel
je systematicky pod 1 a nikdy nedosiahne prah. Prezradilo to práve to, že
medzi „podozrivými" boli aj dvojice s ``FillsVoids``, teda isté.

Poučenie je zapísané v postupe: **kritérium sa najprv kalibruje na držanej
vzorke a použije sa, len keď ju prejde celú.** To dnešné meria štyri veci
v osiach steny, nie podielom plochy dverí:

* stred dverí leží v hrúbke steny;
* dvere sú po dĺžke vnútri steny;
* zvislý rozsah dverí je v rozsahu steny;
* dvere aj stena sú tenké v tej istej osi.

Konvencie prevzaté z ``23_space_boundaries.py``: ``geom.iterator``,
``use-world-coords``, výsledok v **milimetroch** (``create_shape`` vracia
metre). Shape sa drží v premennej — ``np.array(create_shape(...).verts)``
v jednom výraze číta pamäť dočasného objektu (``CLAUDE_CODE_START.md``).
"""

from __future__ import annotations

import argparse
import collections
import os
import statistics

import ifcopenshell
import ifcopenshell.geom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "out", "ASR_v26.ifc")

TOL = 150.0   # tolerancia fázy 6b, mm


def bboxes(model, products):
    """``{GlobalId: (xmin, ymin, zmin, xmax, ymax, zmax)}`` v mm."""
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


def vol(b):
    return (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2])


def tenka_os(b):
    """Os, v ktorej je prvok najtenší — pri stene jej hrúbka."""
    d = [b[3] - b[0], b[4] - b[1], b[5] - b[2]]
    return d.index(min(d[:2])) if min(d[:2]) < d[2] else d.index(min(d))


def sedi_v_stene(db, wb):
    """Kritérium kalibrované na držanej vzorke. ``{test: bool}``."""
    tw = tenka_os(wb)
    dlz = [a for a in (0, 1) if a != tw]
    stred = (db[tw] + db[tw + 3]) / 2
    out = {"hrúbka": wb[tw] - TOL <= stred <= wb[tw + 3] + TOL,
           "zvisle": wb[2] - TOL <= db[2] and db[5] <= wb[5] + TOL,
           "os": tenka_os(db) == tw}
    out["dĺžka"] = bool(dlz) and (wb[dlz[0]] - TOL <= db[dlz[0]]
                                 and db[dlz[0] + 3] <= wb[dlz[0] + 3] + TOL)
    return out


def host_z_fillsvoids(e):
    """Hostiteľ doložený vzťahom, nie odhadom."""
    for r in (getattr(e, "FillsVoids", None) or ()):
        op = r.RelatingOpeningElement
        for v in (getattr(op, "VoidsElements", None) or ()):
            return v.RelatingBuildingElement
    return None


def odvod_z_polohy(model, dvere, sid, hranice, ebox):
    """Presne to, čo robila fáza 6b — aby sa testovalo ono, nie iné."""
    db = ebox.get(dvere.GlobalId)
    if db is None:
        return None
    dc = [(db[0] + db[3]) / 2, (db[1] + db[4]) / 2, (db[2] + db[5]) / 2]
    best = None
    for (s2, e2) in hranice:
        if s2 != sid:
            continue
        cand = model.by_id(e2)
        if not cand.is_a("IfcWall"):
            continue
        cb = ebox.get(cand.GlobalId)
        if cb is None:
            continue
        if all(cb[i] - TOL <= dc[i] <= cb[i + 3] + TOL for i in range(3)):
            if best is None or vol(cb) < vol(ebox[best.GlobalId]):
                best = cand
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=IN)
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args()

    m = ifcopenshell.open(args.src)
    print("model :", args.src)
    rels = m.by_type("IfcRelSpaceBoundary")
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
                    if r.RelatedBuildingElement is not None},
                   key=lambda e: e.id())
    print("prvkov v hraniciach:", len(prvky), "— počítam bboxy…")
    ebox = bboxes(m, prvky + steny + list(m.by_type("IfcSpace")))
    print("bboxov:", len(ebox))
    print()

    # ---------- C · zhoda so schémou -------------------------------------
    zle_priestor = zle_inverz = sam_sebe = 0
    for r in rels:
        p = getattr(r, "ParentBoundary", None)
        if p is None:
            continue
        if p.RelatingSpace is None or r.RelatingSpace is None or \
                p.RelatingSpace.id() != r.RelatingSpace.id():
            zle_priestor += 1
        if r not in (getattr(p, "InnerBoundaries", None) or ()):
            zle_inverz += 1
        if p.id() == r.id():
            sam_sebe += 1
    print("C · ParentBoundary v inom priestore než dieťa :", zle_priestor)
    print("C · InnerBoundaries nesedí ako inverz         :", zle_inverz)
    print("C · rodičom je tá istá hranica                :", sam_sebe)
    print()

    # ---------- A · držaná vzorka ----------------------------------------
    kluce = list(hranice.keys())
    zhoda = nezhoda = nenaslo = 0
    zle = []
    for (sid, eid), r in hranice.items():
        e = m.by_id(eid)
        if not e.is_a("IfcDoor"):
            continue
        pravda = host_z_fillsvoids(e)
        if pravda is None:
            continue
        odhad = odvod_z_polohy(m, e, sid, kluce, ebox)
        if odhad is None:
            nenaslo += 1
        elif odhad.GlobalId == pravda.GlobalId:
            zhoda += 1
        else:
            nezhoda += 1
            zle.append((e.Name, m.by_id(sid).Name, pravda.Name, odhad.Name))
    celkom = zhoda + nezhoda + nenaslo
    print("A · DRŽANÁ VZORKA — dvere, kde hostiteľa poznáme z FillsVoids")
    print("    porovnateľných hraníc :", celkom)
    print("    odvodenie trafilo     :", zhoda)
    print("    odvodenie sa MÝLILO   :", nezhoda)
    print("    odvodenie nič nenašlo :", nenaslo)
    for x in zle[: args.show]:
        print("      dvere %-16s v %-10s pravda %-14s odhad %s" % x)
    print()

    # ---------- B · geometrický test, kalibrovaný na vzorke ---------------
    vzorka, merane = [], []
    ine = collections.Counter()
    for (sid, eid), r in hranice.items():
        e = m.by_id(eid)
        p = getattr(r, "ParentBoundary", None)
        if not e.is_a("IfcDoor") or p is None:
            continue
        w = p.RelatedBuildingElement
        if w is None or not w.is_a("IfcWall"):
            ine["rodič je " + (w.is_a() if w else "—")] += 1
            continue
        db, wb = ebox.get(e.GlobalId), ebox.get(w.GlobalId)
        if db is None or wb is None:
            ine["chýba bbox"] += 1
            continue
        k = sedi_v_stene(db, wb)
        (vzorka if host_z_fillsvoids(e) else merane).append((e.Name, w.Name, k))

    def zhrn(nadpis, data):
        presli = sum(1 for _, _, k in data if all(k.values()))
        print("    %-42s %3d / %3d" % (nadpis, presli, len(data)))
        for a, b, k in data:
            if not all(k.values()):
                print("        %-16s → %-14s zlyhalo: %s"
                      % (a, b, ", ".join(x for x, v in k.items() if not v)))
        return presli, len(data)

    print("B · GEOMETRICKÝ TEST (iný signál než ktorým sa priraďovalo)")
    kp, kn = zhrn("kalibrácia na FillsVoids", vzorka)
    mp, mn = zhrn("odvodené z polohy", merane)
    for k, c in ine.most_common():
        print("    %-42s %3d" % (k, c))
    if kn and kp != kn:
        print("    ⚠️  kritérium neprešlo držanú vzorku — meraniu sa nedá veriť")
    print()

    # ---------- D · bez rodiča -------------------------------------------
    bez = collections.Counter()
    bez_zoznam = []
    for (sid, eid), r in hranice.items():
        e = m.by_id(eid)
        if not (e.is_a("IfcDoor") or e.is_a("IfcWindow")):
            continue
        if getattr(r, "ParentBoundary", None) is None:
            bez[(e.is_a(), "má FillsVoids" if host_z_fillsvoids(e)
                 else "nemá FillsVoids")] += 1
            bez_zoznam.append((sid, e))
    print("D · výplne bez ParentBoundary:", sum(bez.values()))
    for k, c in bez.most_common():
        print("    %4d  %s  %s" % (c, k[0], k[1]))
    print()

    # ---------- E · chýbajúce hranice ------------------------------------
    #
    # Dvere sú otvor **v stene**. Keď teda dvere hranicou priestoru sú,
    # musí ňou byť aj stena, ktorá ich obklopuje — spec k
    # IfcRelSpaceBoundary1stLevel: hranice „form a closed shell around
    # the space … and include overlapping boundaries representing
    # openings (filled or not) in the building elements".
    print("E · CHÝBAJÚCE HRANICE — hostiteľ dverí, ktorý hranicou nie je")
    chyba = []
    for sid, e in bez_zoznam:
        db = ebox.get(e.GlobalId)
        sb = ebox.get(m.by_id(sid).GlobalId)
        if db is None or sb is None:
            continue
        kand = [w for w in steny
                if ebox.get(w.GlobalId) and all(sedi_v_stene(db, ebox[w.GlobalId]).values())]
        vonku = [w for w in kand if w.id() not in je_hranicou[sid]]
        if not vonku:
            continue
        w = vonku[0]
        wb = ebox[w.GlobalId]
        tw = tenka_os(wb)
        osi = [a for a in (0, 1, 2) if a != tw]
        def olap(a, b, i):
            return max(0.0, min(a[i + 3], b[i + 3]) - max(a[i], b[i]))
        plocha = (olap(sb, wb, osi[0]) * olap(sb, wb, osi[1])
                  - olap(sb, db, osi[0]) * olap(sb, db, osi[1])) / 1e6
        medzera = max(max(0.0, max(sb[i], wb[i]) - min(sb[i + 3], wb[i + 3]))
                      for i in range(3))
        chyba.append((e.Name, m.by_id(sid).Name, w.Name, len(kand),
                      medzera, max(0.0, plocha),
                      sum(1 for s2 in je_hranicou if w.id() in je_hranicou[s2])))
    print("    dverí, ktorých hostiteľ hranicou priestoru NIE JE:", len(chyba))
    if chyba:
        print("    %-14s %-8s %-16s %5s %8s %10s %6s"
              % ("dvere", "priestor", "stena", "kand", "medzera", "voľná pl.", "inde"))
        for x in chyba[: args.show]:
            print("    %-14s %-8s %-16s %5d %6.0f mm %8.2f m² %6d" % x)
        if len(chyba) > args.show:
            print("    … a ďalších %d" % (len(chyba) - args.show))
        pl = [x[5] for x in chyba]
        print("    voľná plocha steny voči priestoru: medián %.2f m², min %.2f, "
              "max %.2f  (prah fázy 6b 0,05 m²)"
              % (statistics.median(pl), min(pl), max(pl)))
        print("    stena je hranicou iného priestoru: %d z %d"
              % (sum(1 for x in chyba if x[6]), len(chyba)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
