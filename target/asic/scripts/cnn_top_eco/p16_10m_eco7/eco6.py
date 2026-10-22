# ECO tanpa GRT ulang (putaran 6): route guide net yang ada tidak diubah, sehingga jumper putaran sebelumnya tetap.
#  - antena: satu sky130_fd_sc_hd__diode_2 di situs kosong terdekat pin gate pelanggar (di dalam guide met1 net-nya);
#  - kapasitansi, driver sel standar: master diperbesar satu ukuran (buf_6 -> buf_8, dst.) di tempat, digeser seperlunya
#    di dalam celah kosong baris yang sama;
#  - kapasitansi, pin makro: buffer di situs kosong terdekat pin (di dalam guide met1 net-nya); pin makro pindah ke net
#    baru pendek makro -> buffer, yang diberi salinan guide net lama di sekitar pin dan buffer.
# Pakai: openroad -python eco6.py in.odb out.odb antena_pins.txt cap_pins.txt resize.txt
#   antena_pins.txt: "net inst/pin lapisan"; cap_pins.txt: "inst/pin ..."; resize.txt (keluaran): "inst master x y",
#   diterapkan oleh eco6_views.tcl
import os, sys, functools, re
from openroad import Tech, Design
import odb
print = functools.partial(print, flush=True)

src, dst, ant_lst, cap_lst, resize_lst = sys.argv[1:6]
resize = []
TAG = os.environ.get("ECO_TAG", "6")  # nomor putaran, untuk nama sel/net ECO yang unik
t = Tech(); d = Design(t); d.readDb(src)
db = t.getDB(); b = d.getBlock(); tech = db.getTech()
DIODE = db.findMaster("sky130_fd_sc_hd__diode_2")
MBUF = db.findMaster("sky130_fd_sc_hd__buf_2")
M1 = tech.findLayer("met1")
SIZES = [1, 2, 4, 6, 8, 12]

def find_by(getter, allf, name):
    x = getter(name)
    if x: return x
    key = name.replace("\\", "")
    return next((y for y in allf() if y.getName().replace("\\", "") == key), None)

def nguides(): return sum(len(n.getGuides()) for n in b.getNets())
def inside(r, x, y): return r.xMin() <= x <= r.xMax() and r.yMin() <= y <= r.yMax()
def center(r): return (r.xMin() + r.xMax()) // 2, (r.yMin() + r.yMax()) // 2
def met1_guides(net): return [g.getBox() for g in net.getGuides() if g.getLayer().getName() == "met1"]

rows = list(b.getRows())
RH = rows[0].getSite().getHeight()
Y0 = min(r.getBBox().yMin() for r in rows)
occ = {}
def mark(x0, y0, x1, y1):
    for k in range((y0 - Y0) // RH, (y1 - 1 - Y0) // RH + 1):
        occ.setdefault(k, []).append((x0, x1))
for i in b.getInsts():
    r = i.getBBox(); mark(r.xMin(), r.yMin(), r.xMax(), r.yMax())
for bl in b.getBlockages():
    r = bl.getBBox(); mark(r.xMin(), r.yMin(), r.xMax(), r.yMax())

def gaps_of(k, x0, x1, skip=None):
    cur, out = x0, []
    for a, e in sorted(occ.get(k, [])):
        if skip and (a, e) == skip: continue
        if a > cur: out.append((cur, a))
        cur = max(cur, e)
    out.append((cur, x1))
    return out

def find_site(px, py, w, m1, rad):
    # situs kosong selebar w terdekat (px, py); diutamakan yang pusatnya di dalam guide met1 m1
    best = None
    for rw in rows:
        rb = rw.getBBox(); cy = rb.yMin() + RH // 2
        if abs(cy - py) > max(4 * RH, rad) or rb.xMax() < px - rad or rb.xMin() > px + rad: continue
        sw = rw.getSite().getWidth(); k = (rb.yMin() - Y0) // RH
        for a, e in gaps_of(k, rb.xMin(), rb.xMax()):
            lo = rb.xMin() + -(-(a - rb.xMin()) // sw) * sw
            hi = rb.xMin() + ((e - w - rb.xMin()) // sw) * sw
            if lo > hi: continue
            x = min(max(rb.xMin() + round((px - w // 2 - rb.xMin()) / sw) * sw, lo), hi)
            cx = x + w // 2
            cost = (0 if any(inside(r, cx, cy) for r in m1) else 1, abs(cx - px) + abs(cy - py))
            if best is None or cost < best[0]: best = (cost, x, rb.yMin(), rw.getOrient(), k)
    return best

def put(master, name, site):
    (out, dist), x, y, orient, k = site
    inst = odb.dbInst.create(b, master, name)
    inst.setOrient(orient); inst.setLocation(x, y); inst.setPlacementStatus("PLACED")
    occ.setdefault(k, []).append((x, x + master.getWidth()))
    return inst

g0 = nguides()
print(f"ECO6: guide sebelum {g0}")

# ---- antena: dioda -------------------------------------------------------------------------------------------------
n = 0
for line in open(ant_lst):
    if not line.strip(): continue
    nname, pname = line.split()[:2]
    net = find_by(b.findNet, b.getNets, nname)
    iname, pin = pname.rsplit("/", 1)
    inst = find_by(b.findInst, b.getInsts, iname)
    if not net or not inst or not inst.findITerm(pin):
        print("ECO6: tidak ditemukan", nname, pname); continue
    px, py = center(inst.findITerm(pin).getBBox())
    m1 = met1_guides(net)
    site = find_site(px, py, DIODE.getWidth(), m1, 20000)
    if site is None: print("ECO6: tidak ada situs untuk dioda", nname, pname); continue
    n += 1
    di = put(DIODE, f"ANT{TAG}_DIODE_{n}", site)
    di.findITerm("DIODE").connect(net)
    if site[0][0]:
        g = min(m1, key=lambda r: 0 if inside(r, px, py) else abs(center(r)[0] - px) + abs(center(r)[1] - py))
        odb.dbGuide.create(net, M1, M1, odb.Rect(min(g.xMin(), site[1]), min(g.yMin(), site[2]),
                                                 max(g.xMax(), site[1] + DIODE.getWidth()), max(g.yMax(), site[2] + RH)))
    print(f"ECO6: dioda {nname} {pname} -> ANT{TAG}_DIODE_{n} jarak {site[0][1]/1000:.1f} um, "
          f"{'guide met1 ditambah' if site[0][0] else 'di dalam guide met1'}")

# ---- kapasitansi ---------------------------------------------------------------------------------------------------
def pin_in_guides(it):
    net = it.getNet(); x, y = center(it.getBBox())
    return net is None or any(inside(g.getBox(), x, y) for g in net.getGuides())

def guide_component_ok(boxes, a, c):
    # boxes: [(layer, rect)]; apakah titik a dan c berada di komponen guide yang tersambung
    lv = {ly.getName(): ly.getRoutingLevel() for ly in tech.getLayers()}
    par = list(range(len(boxes)))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    def touch(p, q): return p.xMin() <= q.xMax() and q.xMin() <= p.xMax() and p.yMin() <= q.yMax() and q.yMin() <= p.yMax()
    for i, (li, ri) in enumerate(boxes):
        for j in range(i):
            lj, rj = boxes[j]
            if abs(lv[li] - lv[lj]) <= 1 and touch(ri, rj): par[f(i)] = f(j)
    ca = {f(i) for i, (_, r) in enumerate(boxes) if inside(r, *a)}
    cc = {f(i) for i, (_, r) in enumerate(boxes) if inside(r, *c)}
    return bool(ca & cc)

nb = 0
seen = set()
for line in open(cap_lst):
    if not line.strip(): continue
    pname = line.split()[0]
    if pname in seen: continue
    seen.add(pname)
    iname, pin = pname.rsplit("/", 1)
    inst = find_by(b.findInst, b.getInsts, iname)
    if not inst or not inst.findITerm(pin): print("ECO6: tidak ditemukan", pname); continue
    it = inst.findITerm(pin); net = it.getNet()
    if inst.getMaster().isBlock():
        px, py = center(it.getBBox())
        m1 = met1_guides(net)
        site = find_site(px, py, MBUF.getWidth(), m1, 40000)
        if site is None: print("ECO6: tidak ada situs untuk buffer", pname); continue
        nb += 1
        buf = put(MBUF, f"ECO{TAG}_MBUF_{nb}", site)
        nn = odb.dbNet.create(b, f"eco{TAG}_mbuf_net_{nb}")
        it.disconnect(); it.connect(nn)
        buf.findITerm("A").connect(nn); buf.findITerm("X").connect(net)
        bx, by = center(buf.getBBox())
        gs = [g.getBox() for g in net.getGuides()]
        gc = min(min(r.dx(), r.dy()) for r in gs)
        bx0, by0, bx1, by1 = min(px, bx) - gc, min(py, by) - gc, max(px, bx) + gc, max(py, by) + gc
        sel = [(g.getLayer().getName(), g.getViaLayer().getName(), g.getBox()) for g in net.getGuides()
               if g.getBox().xMin() < bx1 and bx0 < g.getBox().xMax() and g.getBox().yMin() < by1 and by0 < g.getBox().yMax()]
        for ly, via, r in sel: odb.dbGuide.create(nn, tech.findLayer(ly), tech.findLayer(via), r)
        ok = guide_component_ok([(ly, r) for ly, _, r in sel], (px, py), (bx, by))
        print(f"ECO6: buffer makro {pname} -> ECO{TAG}_MBUF_{nb} jarak {site[0][1]/1000:.1f} um, "
              f"{'di dalam guide met1' if not site[0][0] else 'DI LUAR guide met1'}, guide net baru {len(sel)} kotak, "
              f"tersambung {'ya' if ok else 'TIDAK'}")
    else:
        mn = inst.getMaster().getName()
        m = re.match(r"(.*_)(\d+)$", mn)
        nxt = [s for s in SIZES if m and s > int(m.group(2))]
        big = db.findMaster(m.group(1) + str(nxt[0])) if nxt else None
        if not big: print("ECO6: tidak ada ukuran lebih besar untuk", pname, mn); continue
        bb = inst.getBBox(); r = odb.Rect(bb.xMin(), bb.yMin(), bb.xMax(), bb.yMax())
        k = (r.yMin() - Y0) // RH; w = big.getWidth()
        rw = next(rw for rw in rows if rw.getBBox().yMin() == r.yMin() and rw.getBBox().xMin() <= r.xMin() < rw.getBBox().xMax())
        rb = rw.getBBox(); sw = rw.getSite().getWidth()
        want = r.xMin() - (w - r.dx()) // 2
        best = None
        for a, e in gaps_of(k, rb.xMin(), rb.xMax(), skip=(r.xMin(), r.xMax())):
            if not (a <= r.xMin() and r.xMax() <= e): continue
            lo = rb.xMin() + -(-(a - rb.xMin()) // sw) * sw
            hi = rb.xMin() + ((e - w - rb.xMin()) // sw) * sw
            if lo <= hi: best = min(max(rb.xMin() + round((want - rb.xMin()) / sw) * sw, lo), hi)
        if best is None: print("ECO6: tidak ada ruang untuk memperbesar", pname, mn, "->", big.getName()); continue
        # swapMaster butuh liberty (callback STA): penggantian dilakukan di eco6_views.tcl (replace_cell)
        occ[k].remove((r.xMin(), r.xMax())); occ[k].append((best, best + w))
        resize.append(f"{inst.getName()} {big.getName()} {best} {r.yMin()}")
        print(f"ECO6: perbesar {pname} {mn} -> {big.getName()}, geser {(best - r.xMin())/1000:+.2f} um")

print(f"ECO6: {n} dioda, {nb} buffer makro, {len(resize)} diperbesar; guide sesudah {nguides()} (sebelum {g0})")
with open(resize_lst, "w") as f:
    for s in resize: print(s, file=f)
d.writeDb(dst)
print("ECO6: tulis selesai")
