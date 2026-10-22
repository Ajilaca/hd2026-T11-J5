# ECO kapasitansi dari laporan STA setelah routing (checks.rpt): per pin driver yang melanggar max capacitance:
#  - pin makro (batas lib kecil): buffer tepat di samping pin, semua sink dipindah ke keluaran buffer;
#  - driver clock (clkbuf_*): klon driver (master sama, masukan sama), sink dibagi dua menurut posisi;
#  - lainnya: buffer di titik tengah driver -> pusat sink, sink yang lebih jauh dari titik itu dipindah ke buffer.
# Sel baru hanya diberi lokasi kasar (PLACED); legalisasi + GRT dilakukan sesudahnya (eco_antenna.tcl tanpa target).
# Pakai: openroad -python cap_eco.py in.odb out.odb pins.txt   (pins.txt: "pin batas_pF cap_pF ...")
import os, sys, functools, math
from openroad import Tech, Design
import odb
print = functools.partial(print, flush=True)

src, dst, lst = sys.argv[1:4]
routed = sys.argv[4] if len(sys.argv) > 4 else None
t = Tech(); d = Design(t); d.readDb(src)
db = t.getDB(); b = d.getBlock()
BUF = db.findMaster("sky130_fd_sc_hd__buf_8")

def find_inst(name):
    i = b.findInst(name)
    if i: return i
    key = name.replace("\\", "")
    return next((x for x in b.getInsts() if x.getName().replace("\\", "") == key), None)

def center(it):
    r = it.getBBox(); return ((r.xMin() + r.xMax()) // 2, (r.yMin() + r.yMax()) // 2)

def place(inst, x, y):
    inst.setLocation(int(x), int(y)); inst.setPlacementStatus("PLACED")

MARGIN = 8000   # jarak minimum dari tepi makro (dbu)
MACROS = [i.getBBox() for i in b.getInsts() if i.getMaster().isBlock()]
_rows = [r.getBBox() for r in b.getRows()]
CORE = (min(r.xMin() for r in _rows), min(r.yMin() for r in _rows), max(r.xMax() for r in _rows), max(r.yMax() for r in _rows))

def legal(x, y):
    if not (CORE[0] <= x <= CORE[2] - 20000 and CORE[1] <= y <= CORE[3] - 3000): return False
    return not any(m.xMin() - MARGIN < x < m.xMax() + MARGIN and m.yMin() - MARGIN < y < m.yMax() + MARGIN for m in MACROS)

def split_point(dx, dy, sx, sy, step=5000):
    # titik legal (di luar makro) di sepanjang dua jalur L driver -> pusat sink yang paling menyeimbangkan kedua bagian kabel
    best = None
    for corner in ((sx, dy), (dx, sy)):
        pts = []
        for (ax, ay), (bx, by) in (((dx, dy), corner), (corner, (sx, sy))):
            n = max(1, int((abs(bx - ax) + abs(by - ay)) / step))
            pts += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n + 1)]
        for px, py in pts:
            if not legal(px, py): continue
            a = abs(px - dx) + abs(py - dy); c = abs(sx - px) + abs(sy - py)
            if best is None or max(a, c) < best[0]: best = (max(a, c), px, py)
    return best

GRID = 2000
RB = None
if routed:
    rdb = odb.dbDatabase.create(); odb.read_db(rdb, routed); RB = rdb.getChip().getBlock()

def snap(x, y): return (int(round(x / GRID)) * GRID, int(round(y / GRID)) * GRID)

def route_graph(name):
    # graf rute dari kabel ter-route: titik sampel setiap GRID di sepanjang segmen, simpul dengan koordinat sama digabung
    n = RB.findNet(name) if RB else None
    if not n or not n.getWire(): return None
    dec = odb.dbWireDecoder(); dec.begin(n.getWire())
    adj = {}; last = None
    def edge(a, c):
        if a == c: return
        w = abs(a[0] - c[0]) + abs(a[1] - c[1])
        adj.setdefault(a, {})[c] = w; adj.setdefault(c, {})[a] = w
    pts = []
    while True:
        op = dec.next()
        if op == odb.dbWireDecoder.END_DECODE: break
        if op in (odb.dbWireDecoder.PATH, odb.dbWireDecoder.JUNCTION, odb.dbWireDecoder.SHORT, odb.dbWireDecoder.VWIRE): last = None
        elif op in (odb.dbWireDecoder.POINT, odb.dbWireDecoder.POINT_EXT):
            p = dec.getPoint()[:2]
            if last is not None:
                k = max(1, int((abs(p[0] - last[0]) + abs(p[1] - last[1])) / GRID))
                prev = snap(*last)
                for i in range(1, k + 1):
                    q = snap(last[0] + (p[0] - last[0]) * i / k, last[1] + (p[1] - last[1]) * i / k); edge(prev, q); prev = q
            else:
                adj.setdefault(snap(*p), {})
            last = p
    return adj

def dijkstra(adj, src):
    import heapq
    dist = {src: 0}; h = [(0, src)]
    while h:
        dd, u = heapq.heappop(h)
        if dd > dist.get(u, 1e18): continue
        for v, w in adj[u].items():
            if dd + w < dist.get(v, 1e18): dist[v] = dd + w; heapq.heappush(h, (dd + w, v))
    return dist

def nearest(adj, xy): return min(adj, key=lambda q: abs(q[0] - xy[0]) + abs(q[1] - xy[1]))

def route_split(name, drv_xy, sinks_xy):
    adj = route_graph(name)
    if not adj or len(adj) < 3: return None
    s0 = nearest(adj, drv_xy); d1 = dijkstra(adj, s0)
    far = max((nearest(adj, s) for s in sinks_xy), key=lambda q: d1.get(q, -1))
    if far not in d1: return None
    d2 = dijkstra(adj, far); tot = d1[far]
    best = None
    for q in adj:
        if q not in d1 or q not in d2 or d1[q] + d2[q] > tot * 1.02 + GRID: continue   # hanya simpul di jalur driver -> sink terjauh
        if not legal(*q): continue
        sc = max(d1[q], d2[q])
        if best is None or sc < best[0]: best = (sc, q[0], q[1], d1, tot, q)
    if best: best = best + (adj,)
    return best

def io(master):
    i = o = None
    for m in master.getMTerms():
        if m.getSigType() in ("POWER", "GROUND"): continue
        if m.getIoType() == "INPUT": i = m.getName()
        elif m.getIoType() == "OUTPUT": o = m.getName()
    return i, o

n_new = 0
def new_inst(master, tag):
    global n_new
    n_new += 1
    pre = os.environ.get("CAP_PREFIX", "ECO_CAP")
    return odb.dbInst.create(b, master, f"{pre}_{tag}_{n_new}"), odb.dbNet.create(b, f"{pre.lower()}_net_{n_new}")

done = set(); stats = {"makro": 0, "clock": 0, "tengah": 0, "lewati": 0}
for line in open(lst):
    f = line.split()
    if len(f) < 3: continue
    pin = f[0]
    if pin in done: continue
    done.add(pin)
    iname, pname = pin.rsplit("/", 1)
    inst = find_inst(iname)
    if not inst: print("CAPECO: instans tidak ada", pin); stats["lewati"] += 1; continue
    drv = inst.findITerm(pname); net = drv.getNet()
    sinks = [x for x in net.getITerms() if x.isInputSignal()]
    if not sinks: stats["lewati"] += 1; continue
    dx, dy = center(drv)
    mname = inst.getMaster().getName()
    if inst.getMaster().isBlock():                       # pin makro
        buf, nn = new_inst(BUF, "M")
        bi, bo = io(BUF)
        r = inst.getBBox()
        # geser keluar dari makro ke arah sisi pin terdekat
        side = min((dy - r.yMin(), (dx, r.yMin() - 3000)), (r.yMax() - dy, (dx, r.yMax() + 1000)),
                   (dx - r.xMin(), (r.xMin() - 3000, dy)), (r.xMax() - dx, (r.xMax() + 1000, dy)))[1]
        place(buf, *side)
        for s in sinks: s.disconnect(); s.connect(nn)
        buf.findITerm(bo).connect(nn); buf.findITerm(bi).connect(net)
        # buf.X -> nn (sink lama), buf.A <- net (pin makro)
        stats["makro"] += 1
    elif "clkbuf" in mname and len(sinks) >= 8:          # driver clock: klon
        ci, co = io(inst.getMaster())
        a_net = inst.findITerm(ci).getNet()
        pts = [(s, *center(s)) for s in sinks]
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        axis = 1 if max(xs) - min(xs) >= max(ys) - min(ys) else 2
        pts.sort(key=lambda p: p[axis]); half = pts[len(pts) // 2:]
        clone, nn = new_inst(inst.getMaster(), "C")
        cx = sum(p[1] for p in half) / len(half); cy = sum(p[2] for p in half) / len(half)
        place(clone, (dx + cx) / 2, (dy + cy) / 2)
        nn.setSigType("CLOCK")
        clone.findITerm(ci).connect(a_net); clone.findITerm(co).connect(nn)
        for s, _, _ in half: s.disconnect(); s.connect(nn)
        stats["clock"] += 1
    else:                                                 # buffer di tengah
        real = [s for s in sinks if "diode" not in s.getInst().getMaster().getName()] or sinks
        sx = sum(center(s)[0] for s in real) / len(real); sy = sum(center(s)[1] for s in real) / len(real)
        rs = route_split(net.getName(), (dx, dy), [center(x) for x in real]) if RB else None
        if rs:
            _, mx, my, d1r, tot, q, adj = rs; stats["rute"] = stats.get("rute", 0) + 1
            dq = dijkstra(adj, q)
            if os.environ.get("CAP_DEBUG") and stats["rute"] <= 12: print(f"CAPDBG: {pin} rute={tot/1000:.0f}um bagian_terpanjang={rs[0]/1000:.0f}um buffer@({mx/1000:.0f},{my/1000:.0f}) driver@({dx/1000:.0f},{dy/1000:.0f})")
            rfar = [x for x in sinks if (lambda nq: dq.get(nq, 1e18) < d1r.get(nq, 1e18))(nearest(adj, center(x)))]
        else:
            sp = split_point(dx, dy, sx, sy)
            if sp is None: print("CAPECO: tidak ada titik legal", pin); stats["lewati"] += 1; continue
            _, mx, my = sp
        md = lambda s, x, y: abs(center(s)[0] - x) + abs(center(s)[1] - y)
        far = rfar if rs else [s for s in sinks if md(s, mx, my) < md(s, dx, dy)]
        if not far: stats["lewati"] += 1; continue
        buf, nn = new_inst(BUF, "W")
        bi, bo = io(BUF)
        place(buf, mx, my)
        for s in far: s.disconnect(); s.connect(nn)
        buf.findITerm(bo).connect(nn); buf.findITerm(bi).connect(net)
        stats["tengah"] += 1
print(f"CAPECO: {stats} sel baru {n_new}")
d.writeDb(dst)
print("CAPECO: tulis selesai")
