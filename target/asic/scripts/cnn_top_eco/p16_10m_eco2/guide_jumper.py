# Jumper lewat route guide: untuk net pelanggar antena, guide met1 panjang (lebih dari 2 gcell) diganti met3
# (horizontal) atau met2 (vertikal); di kedua ujungnya dibuat tumpukan via met1->met2->met3, sehingga met1
# yang tersambung ke gate tinggal 1 gcell dan sisanya naik ke lapisan atas (jumper).
# Pakai: openroad -python guide_jumper.py in.odb out.odb out.def targets.txt
import odb, sys, functools
from openroad import Tech, Design
print = functools.partial(print, flush=True)

src, dst, dst_def, tgt = sys.argv[1:5]
ortech = Tech(); design = Design(ortech); design.readDb(src)
db = ortech.getDB(); tech = db.getTech(); b = design.getBlock()
L = {ly.getName(): ly for ly in tech.getLayers()}

def find_net(name):
    n = b.findNet(name)
    if n: return n
    key = name.replace("\\", "")
    for n in b.getNets():
        if n.getName().replace("\\", "") == key: return n
    return None

def make(net, layer, via, x0, y0, x1, y1):
    odb.dbGuide.create(net, L[layer], L[via], odb.Rect(x0, y0, x1, y1))

names = [l.split()[0] for l in open(tgt) if l.strip()]
done = 0
for name in dict.fromkeys(names):
    net = find_net(name)
    if not net: print("JUMPER: net", name, "tidak ditemukan"); continue
    old = [(gd.getLayer().getName(), gd.getViaLayer().getName(), gd.getBox()) for gd in net.getGuides()]
    g = min(min(r.dx(), r.dy()) for _, _, r in old)  # ukuran gcell
    new, moved = [], 0
    for ly, via, r in old:
        x0, y0, x1, y1 = r.xMin(), r.yMin(), r.xMax(), r.yMax()
        horiz = r.dx() >= r.dy()
        span = r.dx() if horiz else r.dy()
        if ly != "met1" or via != "met1" or span <= 2 * g:
            new.append((ly, via, x0, y0, x1, y1)); continue
        up = "met3" if horiz else "met2"
        ends = [(x0, y0, x0 + g, y1), (x1 - g, y0, x1, y1)] if horiz else [(x0, y0, x1, y0 + g), (x0, y1 - g, x1, y1)]
        for t in ends:  # ujung: met1 1 gcell + tumpukan via ke lapisan atas
            new.append(("met1", "met1", *t))
            new.append(("met1", "met2", *t))
            if up == "met3":
                new.append(("met2", "met3", *t))
                new.append(("met3", "met2", *t))
            else:
                new.append(("met2", "met1", *t))
        new.append((up, up, x0, y0, x1, y1))
        moved += span
    net.clearGuides()
    for t in new: make(net, *t)
    done += 1
    print(f"JUMPER: {name}: {moved/1000:.0f} um guide met1 dipindah ke lapisan atas")
print(f"JUMPER: {done} net diubah")
design.writeDb(dst)
try: odb.write_def(b, dst_def)
except Exception as e: print("JUMPER: write_def gagal", e)
print("JUMPER: tulis selesai")
