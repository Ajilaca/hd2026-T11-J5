"""Mode axil2: peserta dataset lewat AXI4-Lite + gejala klinis dari manifest (hanya pustaka standar; butuh root).

    sudo python3 axil2.py clips hasil [--n 20]
Butuh manifest.csv (kolom gejala dan fold dari fit_fusi.py), fusi.json, dan ambang.txt di folder yang sama. Tiap peserta mengirim
semua klipnya; logit peserta = rata-rata logit FPGA. Skor gabungan = regresi logistik [skor gejala, rata-rata logit] dihitung di ARM.
Koefisien per peserta memakai lipatan yang tidak memuat peserta itu, dan model gejala dilatih pada peserta tanpa audio, jadi tidak
ada kebocoran label. Layar: tabel + ringkasan audio saja vs audio+gejala. CSV: semua kolom, termasuk logit golden dan cek.
Ambang optimistis. Alat triase, bukan diagnosis.
"""
import statistics
import sys
import time

import fusi
from axil_batch import load_manifest, miss_table, opt, outcome, rate_table, run_participant, table
from axil_smoke import Dev, NSAMP, VERSION


def main(argv: list[str]) -> int:
    nsub, argv = opt(argv, "--n")
    if len(argv) != 2:
        print(__doc__)
        return 1
    d, base = argv
    fz = fusi.load()
    amb_a = float(open("ambang.txt").read().split()[0])
    amb_f = fz["axil"]["ambang"]
    man, names = load_manifest("manifest.csv", int(nsub) if nsub else None)
    dev = Dev()
    if dev.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_axil")
        return 1
    n = dev.rd(NSAMP)
    rows, csvrows, lat = [], [], []
    cm = {"audio": {"TP": 0, "FP": 0, "FN": 0, "TN": 0}, "fusi": {"TP": 0, "FP": 0, "FN": 0, "TN": 0}}
    same = total = 0
    t0 = time.time()
    for k, b in enumerate(names, 1):
        r = man[b]
        lg, gold, lt = run_participant(dev, d, r, n)
        lat += lt
        same += sum(a == g for a, g in zip(lg, gold))
        total += len(gold)
        mean = sum(lg) / len(lg)
        g = dict(coughdur=int(r["coughdur"]), bmi=float(r["bmi"]), sex=int(r["sex"]),
                 weightloss=int(r["weightloss"]), ngtsweats=int(r["ngtsweats"]))
        cs = fusi.clin_score(fz, g)
        s = fusi.fuse(fz["axil"]["folds"][r["fold"]], cs, mean)
        pos = r["y"] == "1"
        ha, hf = outcome(pos, mean >= amb_a), outcome(pos, s >= amb_f)
        cm["audio"][ha] += 1
        cm["fusi"][hf] += 1
        rows.append([str(k), b, fusi.short(g), f"{mean:.0f}", f"{s:+.2f}", "RUJUK" if s >= amb_f else "rendah",
                     "TB" if pos else "bukan TB", hf])
        csvrows.append([b, str(len(lg)), f"{mean:.1f}", " ".join(map(str, lg)), " ".join(map(str, gold)),
                        "SAMA" if lg == gold else "BEDA", fusi.short(g), f"{cs:.3f}", f"{s:.3f}",
                        "RUJUK" if mean >= amb_a else "rendah", "RUJUK" if s >= amb_f else "rendah",
                        "positif" if pos else "negatif", ha, hf])
        print(f"\r  memproses peserta {k}/{len(names)}", end="", flush=True)
    print()
    dt = time.time() - t0
    screen = "\n\n".join([table(rows, ["No", "Peserta", "Gejala", "Logit", "Skor", "Risiko", "Label", "Hasil"], (1, 2, 5, 6, 7)),
                           miss_table(cm["fusi"])])
    print(screen)
    note = ("\n\n" + rate_table([("audio saja", cm["audio"]), ("audio+gejala", cm["fusi"])]) + "\n\nGejala: B = lama batuk (0 tidak, 1 <1 mgg, 2 1-2 mgg, 3 3-4 mgg, 4 >4 mgg), L/P = jenis kelamin, "
            "BB+ = berat badan turun, KM+ = keringat malam.\nLogit = rata-rata logit semua klip peserta. Skor = gabungan suara batuk dan gejala.\n"
            f"{len(names)} peserta, {total} klip | {dt:.1f} s | latensi median {statistics.median(lat):.1f} ms per klip\n"
            f"bit-exact terhadap golden: {same}/{total} klip\nAlat triase, bukan diagnosis.\n")
    open(base + ".txt", "w").write(screen + note)
    with open(base + ".csv", "w") as fo:
        fo.write("peserta,n_klip,logit_rata,logit_klip,golden_klip,cek,gejala,skor_klinis,skor_fusi,"
                 "risiko_audio,risiko_fusi,label,hasil_audio,hasil_fusi\n")
        for r in csvrows:
            fo.write(",".join(r) + "\n")
    print(f"Tersimpan: {base}.txt dan {base}.csv")
    return 0 if same == total else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
