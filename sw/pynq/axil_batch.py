"""Proses banyak klip di papan lewat AXI4-Lite (hanya pustaka standar; butuh root untuk /dev/mem).

    sudo python3 axil_batch.py clips hasil [manifest.csv] [--ambang N]
Bitstream harus sudah dimuat (sudo xmutil loadapp suaratb_axil). Tiap clips/<nama>.raw (int16, 8240 sampel) dikirim.
Keluaran: tabel di layar dan hasil.txt (tabel + ringkasan), hasil.csv.
  logit      skor mentah CNN di FPGA (belum dikalibrasi ke probabilitas)
  golden/cek logit golden dari manifest.csv (kolom barcode,y,golden_logit,wav) dan SAMA/BEDA
  latensi_ms waktu dari sampel terakhir terkirim sampai result_new (diukur Python, resolusi ~ms; bukan latensi murni hardware)
  peringkat  persentil logit di antara klip pada kumpulan ini (0-100); relatif, bukan probabilitas
  risiko     RUJUK bila logit >= ambang, selain itu rendah. Ambang dari --ambang atau ambang.txt (sementara, DIPAKSA, optimistis)
  label,hasil label dataset (positif/negatif) dan TP/FP/FN/TN terhadap ambang (hanya bila manifest ada)
Model audio lemah (AUROC ~0,65): banyak negatif akan ditandai RUJUK dan sebagian positif terlewat. Alat triase, bukan diagnosis.
"""
import csv
import os
import statistics
import sys
import time

from axil_smoke import Dev, NSAMP, VERSION, FRAMES, NSAT, infer

STR_COLS = (1, 4, 7, 8, 9)


def table(rows: list[list[str]], head: list[str]) -> str:
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) if i in STR_COLS else c.rjust(w[i]) for i, c in enumerate(r)) + " |"
    return "\n".join([line, fmt(head), line, *(fmt(r) for r in rows), line])


def main(argv: list[str]) -> int:
    ambang = None
    if "--ambang" in argv:
        i = argv.index("--ambang")
        ambang = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) not in (2, 3):
        print(__doc__)
        return 1
    if ambang is None and os.path.exists("ambang.txt"):
        ambang = float(open("ambang.txt").read().split()[0])
    d, base = argv[:2]
    gold = {}
    if len(argv) == 3:
        with open(argv[2]) as f:
            gold = {r["barcode"]: r for r in csv.DictReader(f)}
    dev = Dev()
    if dev.rd(VERSION) != 0xA1000001:
        print("VERSION salah: bitstream belum dimuat")
        return 1
    n = dev.rd(NSAMP)
    names = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".raw"))
    res = []
    t0 = time.time()
    for k, nm in enumerate(names, 1):
        logit, seq, _, tw = infer(dev, open(os.path.join(d, nm + ".raw"), "rb").read(), n)
        res.append((nm, logit, seq, dev.rd(FRAMES) & 0xFFFF, dev.rd(NSAT) & 0xFFFF, tw * 1000))
        if k % 10 == 0 or k == len(names):
            print(f"  diproses {k}/{len(names)}", flush=True)
    dt = time.time() - t0
    srt = sorted(r[1] for r in res)
    rows, csvrows, same, cmp_n = [], [], 0, 0
    cm = {"TP": [], "FP": [], "FN": [], "TN": []}
    for i, (nm, logit, seq, fr, ns, ms) in enumerate(res, 1):
        pr = 100.0 * sum(v < logit for v in srt) / max(len(srt) - 1, 1)
        risk = "-" if ambang is None else ("RUJUK" if logit >= ambang else "rendah")
        g, cek, lab, hs = "-", "-", "-", "-"
        if nm in gold:
            cmp_n += 1
            ok = int(gold[nm]["golden_logit"]) == logit
            same += ok
            g, cek = gold[nm]["golden_logit"], "SAMA" if ok else "BEDA"
            if "y" in gold[nm] and ambang is not None:
                pos = gold[nm]["y"] == "1"
                lab = "positif" if pos else "negatif"
                hs = ("TP" if pos else "FP") if logit >= ambang else ("FN" if pos else "TN")
                cm[hs].append(nm)
        rows.append([str(i), nm, str(logit), g, cek, f"{ms:.1f}", f"{pr:.0f}", risk, lab, hs])
        csvrows.append((nm, logit, seq, fr, ns, f"{ms:.2f}", f"{pr:.1f}", risk, lab, hs))
    head = ["No", "Klip", "Logit", "Golden", "Cek", "Latensi(ms)", "Peringkat", "Risiko", "Label", "Hasil"]
    tb = table(rows, head)
    lat = [r[5] for r in res]
    summ = [f"{len(names)} klip diproses dalam {dt:.1f} s",
            (f"bit-exact terhadap golden: {same}/{cmp_n}" + ("" if same == cmp_n else "  <-- ADA YANG BEDA")) if cmp_n else "golden: tidak ada manifest",
            f"latensi sampel terakhir -> hasil: median {statistics.median(lat):.1f} ms, maks {max(lat):.1f} ms (diukur Python)",
            f"logit: rata-rata {statistics.mean(r[1] for r in res):.1f}, min {srt[0]}, maks {srt[-1]}"]
    if ambang is None:
        summ.append("risiko: tidak ada ambang (kolom '-'); peringkat hanya urutan relatif pada kumpulan ini")
    else:
        summ.append(f"risiko: RUJUK = logit >= {ambang:g} (ambang SEMENTARA dan dipaksa; dipilih pada data yang optimistis)")
    tp, fp, fn, tn = (len(cm[k]) for k in ("TP", "FP", "FN", "TN"))
    if tp + fp + fn + tn:
        summ += [f"terhadap label dataset: TP {tp}, FP {fp}, FN {fn}, TN {tn}; "
                 f"sensitivitas {tp / max(tp + fn, 1):.0%}, spesifisitas {tn / max(tn + fp, 1):.0%} (sampel kecil, bukan estimasi akurasi)",
                 "MODEL LEMAH: banyak negatif tetap ditandai RUJUK dan sebagian positif terlewat."]
        for key, ttl in (("FP", "BUKAN TB menurut label tetapi ditandai RUJUK (false positive)"),
                         ("FN", "TB menurut label tetapi ditandai rendah (false negative, terlewat)"),
                         ("TP", "TB menurut label dan ditandai RUJUK (true positive)")):
            if cm[key]:
                summ.append(f"{ttl}: {len(cm[key])} klip")
                summ += [f"   {nm}  {gold[nm].get('wav', '')}  logit={next(r[1] for r in res if r[0] == nm)}" for nm in cm[key]]
    summ.append("alat triase, bukan diagnosis")
    text = tb + "\n" + "\n".join(summ) + "\n"
    print(text)
    open(base + ".txt", "w").write(text)
    with open(base + ".csv", "w") as fo:
        fo.write("nama,logit,seq,frames,nsat,latensi_ms,peringkat,risiko,label,hasil\n")
        for r in csvrows:
            fo.write(",".join(str(x) for x in r) + "\n")
    print(f"disimpan: {base}.txt dan {base}.csv")
    return 0 if cmp_n == same else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
