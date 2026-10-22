# ECO tanpa GRT ulang (putaran 8): route guide net yang ada tidak diubah, sehingga jumper putaran sebelumnya tetap.
#  - antena: satu sky130_fd_sc_hd__diode_2 di situs kosong terdekat pin gate pelanggar (di dalam guide met1 net-nya);
#    net pelanggar met1 juga ditulis ke jumper.txt untuk guide_jumper.py;
#  - kapasitansi, driver sel standar: separuh sink terjauh dipindah ke net baru yang digerakkan buffer pemecah
#    (net baru diberi salinan guide net lama);
#  - kapasitansi, pin makro: buffer di situs kosong terdekat pin (di dalam guide met1 net-nya); pin makro pindah ke net
#    baru pendek makro -> buffer, yang diberi salinan guide net lama di sekitar pin dan buffer.
# Pakai: openroad -python eco8.py in.odb out.odb antena_pins.txt cap_pins.txt resize.txt jumper.txt
#   antena_pins.txt: "net inst/pin lapisan"; cap_pins.txt: "inst/pin ..."; resize.txt (keluaran, kosong di putaran ini):
#   "inst master x y", diterapkan oleh eco8_views.tcl; jumper.txt (keluaran): target guide_jumper.py
import os, sys, functools, re
from openroad import Tech, Design
import odb
print = functools.partial(print, flush=True)

src, dst, ant_lst, cap_lst, resize_lst, jumper_lst = sys.argv[1:7]
resize, jumper = [], []
TAG = os.environ.get("ECO_TAG", "6")  # nomor putaran, untuk nama sel/net ECO yang unik
t = Tech(); d = Design(t); d.readDb(src)
db = t.getDB(); b = d.getBlock(); tech = db.getTech()
DIODE = db.findMaster("sky130_fd_sc_hd__diode_2")
MBUF = db.findMaster("sky130_fd_sc_hd__buf_2")
SBUF = db.findMaster("sky130_fd_sc_hd__buf_4")
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
            if abs(cx - px) > rad: continue
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
    if line.split()[2:3] == ["met1"]: jumper.append(f"{nname} {pname} x 0")

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

nb = ns = 0
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
        # batas 0,2 pF (MAX_CAPACITANCE_CONSTRAINT) sama untuk semua ukuran sel, jadi beban dipecah: separuh sink terjauh
        # dari driver pindah ke net baru yang digerakkan buffer di antara driver dan sink itu; net baru diberi salinan semua
        # guide net lama (buffer dan sink pindahan berada di dalamnya)
        dx, dy = center(it.getBBox())
        sinks = [x for x in net.getITerms() if x.isInputSignal() and x.getInst().getMaster().getName() != DIODE.getName()]
        sinks.sort(key=lambda x: abs(center(x.getBBox())[0] - dx) + abs(center(x.getBBox())[1] - dy))
        far = sinks[len(sinks) // 2:]
        if not far: print("ECO6: tidak ada sink untuk dipecah", pname); continue
        cx = sum(center(x.getBBox())[0] for x in far) // len(far); cy = sum(center(x.getBBox())[1] for x in far) // len(far)
        # titik pecah dicari di sepanjang guide rute (bukan titik tengah garis lurus, yang bisa jatuh di atas makro atau di
        # luar rute): pusat guide met1/met2 yang jarak tempuhnya paling seimbang ke driver dan ke pusat sink pindahan;
        # situs di dalam guide met1, atau di gcell guide met2 (guide met1 satu gcell ditambahkan di sana)
        m1 = met1_guides(net)
        boxes = [(g.getLayer().getName(), g.getBox()) for g in net.getGuides()]
        gc = min(min(r.dx(), r.dy()) for _, r in boxes)
        cands = sorted({center(r) for ly, r in boxes if ly in ("met1", "met2")},
                       key=lambda p: abs(abs(p[0] - dx) + abs(p[1] - dy) - abs(p[0] - cx) - abs(p[1] - cy)))
        site, add = None, None
        for qx, qy in cands:
            s = find_site(qx, qy, SBUF.getWidth(), m1, 8000)
            if not s: continue
            if not s[0][0]: site = s; break
            sx, sy = s[1] + SBUF.getWidth() // 2, s[2] + RH // 2
            g2 = next((r for ly, r in boxes if ly == "met2" and inside(r, sx, sy)), None)
            if g2:
                y0 = g2.yMin() + ((sy - g2.yMin()) // gc) * gc
                site, add = s, odb.Rect(g2.xMin(), y0, g2.xMax(), min(y0 + gc, g2.yMax())); break
        if site is None:
            print(f"ECO6: tidak ada situs untuk buffer pemecah {pname} (driver {dx},{dy}; {len(sinks)} sink)")
            continue
        tx, ty = site[1] + SBUF.getWidth() // 2, site[2] + RH // 2
        ns += 1
        buf = put(SBUF, f"ECO{TAG}_SBUF_{ns}", site)
        nn = odb.dbNet.create(b, f"eco{TAG}_sbuf_net_{ns}")
        for g in list(net.getGuides()): odb.dbGuide.create(nn, g.getLayer(), g.getViaLayer(), g.getBox())
        for x in far: x.disconnect(); x.connect(nn)
        buf.findITerm("A").connect(net); buf.findITerm("X").connect(nn)
        if add:
            for nt in (net, nn): odb.dbGuide.create(nt, M1, M1, add)
        dd = abs(tx - dx) + abs(ty - dy); ds = abs(tx - cx) + abs(ty - cy)
        print(f"ECO6: pecah beban {pname}: {len(far)} dari {len(sinks)} sink -> ECO{TAG}_SBUF_{ns}, "
              f"ke driver {dd/1000:.0f} um, ke sink {ds/1000:.0f} um, "
              f"{'guide met1 1 gcell ditambah di guide met2' if add else 'di dalam guide met1'}")

print(f"ECO6: {n} dioda, {nb} buffer makro, {ns} buffer pemecah; guide sesudah {nguides()} (sebelum {g0})")
with open(resize_lst, "w") as f:
    for s in resize: print(s, file=f)
with open(jumper_lst, "w") as f:
    for s in jumper: print(s, file=f)
d.writeDb(dst)
print("ECO6: tulis selesai")
