# Dioda antena tanpa GRT ulang: untuk tiap pin gate yang melanggar antena pasca-DRT, satu sky130_fd_sc_hd__diode_2
# dipasang di situs kosong terdekat (diutamakan yang masih di dalam guide met1 net itu), lalu disambung ke net.
# Guide net lain tidak disentuh, sehingga jumper putaran sebelumnya tetap. Bila situs terpilih di luar guide met1,
# satu guide met1 ditambahkan yang mencakup guide pin dan dioda.
# Pakai: openroad -python dioda_eco.py in.odb out.odb pins.txt   (pins.txt: "net inst/pin lapisan")
import sys, functools
from openroad import Tech, Design
import odb
print = functools.partial(print, flush=True)

src, dst, lst = sys.argv[1:4]
t = Tech(); d = Design(t); d.readDb(src)
db = t.getDB(); b = d.getBlock(); tech = db.getTech()
DIODE = db.findMaster("sky130_fd_sc_hd__diode_2")
M1 = tech.findLayer("met1")
DW = DIODE.getWidth()
RAD = 20000   # radius pencarian situs kosong (dbu)

def find_by(getter, allf, name):
    x = getter(name)
    if x: return x
    key = name.replace("\\", "")
    return next((y for y in allf() if y.getName().replace("\\", "") == key), None)

def nguides(): return sum(len(n.getGuides()) for n in b.getNets())

def inside(r, x, y): return r.xMin() <= x <= r.xMax() and r.yMin() <= y <= r.yMax()

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

g0 = nguides()
print(f"DIODA: guide sebelum {g0}")
n = 0
for line in open(lst):
    if not line.strip(): continue
    nname, pname = line.split()[:2]
    net = find_by(b.findNet, b.getNets, nname)
    iname, pin = pname.rsplit("/", 1)
    inst = find_by(b.findInst, b.getInsts, iname)
    if not net or not inst or not inst.findITerm(pin):
        print("DIODA: tidak ditemukan", nname, pname); continue
    pr = inst.findITerm(pin).getBBox(); px, py = (pr.xMin() + pr.xMax()) // 2, (pr.yMin() + pr.yMax()) // 2
    m1 = [g.getBox() for g in net.getGuides() if g.getLayer().getName() == "met1"]
    best = None
    for rw in rows:
        rb = rw.getBBox(); cy = rb.yMin() + RH // 2
        if abs(cy - py) > 3 * RH or rb.xMax() < px - RAD or rb.xMin() > px + RAD: continue
        sw = rw.getSite().getWidth(); k = (rb.yMin() - Y0) // RH
        cur, gaps = rb.xMin(), []
        for a, e in sorted(occ.get(k, [])):
            if a > cur: gaps.append((cur, a))
            cur = max(cur, e)
        gaps.append((cur, rb.xMax()))
        for a, e in gaps:
            lo = rb.xMin() + -(-(a - rb.xMin()) // sw) * sw
            hi = rb.xMin() + ((e - DW - rb.xMin()) // sw) * sw
            if lo > hi: continue
            x = rb.xMin() + round((px - DW // 2 - rb.xMin()) / sw) * sw
            x = min(max(x, lo), hi)
            cx = x + DW // 2
            cost = (0 if any(inside(r, cx, cy) for r in m1) else 1, abs(cx - px) + abs(cy - py))
            if best is None or cost < best[0]: best = (cost, x, rb.yMin(), rw.getOrient(), k)
    if best is None:
        print("DIODA: tidak ada situs kosong untuk", nname, pname); continue
    (out, dist), x, y, orient, k = best
    n += 1
    di = odb.dbInst.create(b, DIODE, f"ANT5_DIODE_{n}")
    di.setOrient(orient); di.setLocation(x, y); di.setPlacementStatus("PLACED")
    di.findITerm("DIODE").connect(net)
    occ.setdefault(k, []).append((x, x + DW))
    note = "di dalam guide met1"
    if out:
        g = min(m1, key=lambda r: 0 if inside(r, px, py) else abs((r.xMin() + r.xMax()) // 2 - px) + abs((r.yMin() + r.yMax()) // 2 - py))
        odb.dbGuide.create(net, M1, M1, odb.Rect(min(g.xMin(), x), min(g.yMin(), y), max(g.xMax(), x + DW), max(g.yMax(), y + RH)))
        note = "guide met1 ditambah"
    print(f"DIODA: {nname} {pname} -> ANT5_DIODE_{n} ({x/1000:.2f}, {y/1000:.2f}) jarak {dist/1000:.1f} um, {note}")
print(f"DIODA: {n} dioda dipasang; guide sesudah {nguides()} (sebelum {g0})")
d.writeDb(dst)
print("DIODA: tulis selesai")
