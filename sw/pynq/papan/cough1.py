"""Model demonstrasi batuk vs bukan batuk (K-29): klip dataset lewat AXI4-Lite (hanya pustaka standar; butuh root).

    sudo python3 cough1.py clips hasil [--n 20]
Bitstream suaratb_cough harus dimuat (sudo xmutil loadapp suaratb_cough). manifest.csv: nama,y,jenis,golden_logit.
BATUK bila logit >= 0. Klip pertama dibandingkan dengan logit golden sebelum mulai; bila beda, bitstream yang dimuat bukan model batuk.
Layar: tabel + ringkasan. hasil.csv: semua kolom, termasuk logit golden dan cek. Ini tugas demonstrasi, bukan skrining TBC.
"""
import csv
import math
import statistics
import sys
import time

from axil_smoke import Dev, NSAMP, VERSION, infer


def table(rows: list, head: list, left: tuple) -> str:
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) if i in left else c.rjust(w[i]) for i, c in enumerate(r)) + " |"  # noqa: E731
    return "\n".join([line, fmt(head), line, *(fmt(r) for r in rows), line])


def main(argv: list[str]) -> int:
    nsub = None
    if "--n" in argv:
        i = argv.index("--n")
        nsub = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2:
        print(__doc__)
        return 1
    d, base = argv
    with open("manifest.csv") as f:
        man = {r["nama"]: r for r in csv.DictReader(f)}
    names = sorted(man)
    if nsub:
        pos = [x for x in names if man[x]["y"] == "1"][:nsub // 2]
        neg = [x for x in names if man[x]["y"] == "0"][:nsub - nsub // 2]
        names = sorted(pos + neg)
    dev = Dev(app="suaratb_cough")
    if dev.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_cough")
        return 1
    n = dev.rd(NSAMP)
    first = names[0]
    logit0 = infer(dev, open(f"{d}/{first}.raw", "rb").read(), n)[0]
    if logit0 != int(man[first]["golden_logit"]):
        print("Bitstream yang dimuat bukan model batuk (logit klip uji tidak cocok).")
        print("Jalankan: sudo xmutil unloadapp && sudo xmutil loadapp suaratb_cough")
        return 1
    rows, csvrows, lat = [], [], []
    same = ok_pos = ok_neg = n_pos = n_neg = 0
    t0 = time.time()
    for k, nm in enumerate(names, 1):
        r = man[nm]
        logit, _, _, tw = infer(dev, open(f"{d}/{nm}.raw", "rb").read(), n)
        lat.append(tw * 1000)
        g = int(r["golden_logit"])
        same += logit == g
        pos, pred = r["y"] == "1", logit >= 0
        if pos:
            n_pos += 1
            ok_pos += pred
        else:
            n_neg += 1
            ok_neg += not pred
        p = 1.0 / (1.0 + math.exp(-max(min(logit / 256.0, 50.0), -50.0)))
        rows.append([str(k), nm, r["jenis"], str(logit), f"{p:.0%}", "BATUK" if pred else "bukan batuk",
                     "ya" if pred == pos else "SALAH"])
        csvrows.append([nm, r["jenis"], str(logit), str(g), "SAMA" if logit == g else "BEDA", f"{p:.4f}",
                        "batuk" if pred else "bukan", "benar" if pred == pos else "salah"])
        print(f"\r  memproses {k}/{len(names)}", end="", flush=True)
    print()
    dt = time.time() - t0
    total = n_pos + n_neg
    acc = [[f"{(ok_pos + ok_neg) / max(total, 1):.0%}", f"{ok_pos}/{n_pos}", f"{ok_neg}/{n_neg}"]]
    screen = "\n\n".join([table(rows, ["No", "Klip", "Isi sebenarnya", "Logit", "Skor", "Prediksi", "Benar"], (1, 2, 5, 6)),
                           table(acc, ["Akurasi", "Batuk terdeteksi", "Bukan batuk ditolak"], ())])
    print(screen)
    note = ("\n\nSkor = sigmoid(logit/256), keyakinan model bahwa suara itu batuk.\n"
            f"{total} klip | {dt:.1f} s | latensi median {statistics.median(lat):.1f} ms per klip\n"
            f"bit-exact terhadap golden: {same}/{total} klip\nTugas demonstrasi akselerator, bukan skrining TBC.\n")
    open(base + ".txt", "w").write(screen + note)
    with open(base + ".csv", "w") as fo:
        fo.write("klip,jenis,logit,golden,cek,skor,prediksi,hasil\n")
        for r in csvrows:
            fo.write(",".join(r) + "\n")
    print(f"Tersimpan: {base}.txt dan {base}.csv")
    return 0 if same == total else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
