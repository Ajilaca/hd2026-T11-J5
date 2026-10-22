"""Proses peserta dataset di papan lewat AXI4-Lite, beberapa klip per peserta (hanya pustaka standar; butuh root untuk /dev/mem).

    sudo python3 axil_batch.py clips hasil manifest.csv [--n 20] [--ambang N]
Bitstream harus sudah dimuat (sudo xmutil loadapp suaratb_axil). manifest.csv berisi satu baris per peserta (barcode,y,n_klip,
golden_logits,wav); klipnya clips/<barcode>_c<i>.raw (int16, 8240 sampel). Tiap klip dikirim ke FPGA, logit peserta = rata-rata
logit semua klipnya. --n N memakai N/2 peserta positif + N/2 negatif (urut nama, tetap); tanpa --n semua peserta.
Risiko RUJUK bila rata-rata logit >= ambang (--ambang atau ambang.txt; dipilih untuk sensitivitas ~90% pada data yang sama: optimistis).
Layar: tabel ringkas. hasil.txt: tabel + rincian per klip dan jalur WAV. hasil.csv: semua kolom, termasuk logit golden dan cek SAMA/BEDA.
Alat triase, bukan diagnosis.
"""
import csv
import os
import statistics
import sys
import time

from axil_smoke import Dev, NSAMP, VERSION, infer


def table(rows: list, head: list, left: tuple) -> str:
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) if i in left else c.rjust(w[i]) for i, c in enumerate(r)) + " |"  # noqa: E731
    return "\n".join([line, fmt(head), line, *(fmt(r) for r in rows), line])


def opt(argv: list, name: str):
    """Ambil dan buang opsi '--name nilai' dari argv."""
    if name not in argv:
        return None, argv
    i = argv.index(name)
    return argv[i + 1], argv[:i] + argv[i + 2:]


def load_manifest(path: str, nsub) -> tuple[dict, list]:
    with open(path) as f:
        man = {r["barcode"]: r for r in csv.DictReader(f)}
    names = sorted(man)
    if nsub:
        pos = [x for x in names if man[x]["y"] == "1"][:nsub // 2]
        neg = [x for x in names if man[x]["y"] == "0"][:nsub - nsub // 2]
        if len(pos) + len(neg) < nsub:
            raise SystemExit(f"peserta tidak cukup untuk --n {nsub} (positif {len(pos)}, negatif {len(neg)})")
        names = sorted(pos + neg)
    return man, names


def run_participant(dev: Dev, d: str, r: dict, n: int) -> tuple[list, list, list]:
    """Kirim semua klip satu peserta; kembalikan (logit FPGA, logit golden, latensi ms)."""
    gold = [int(v) for v in r["golden_logits"].split()]
    lg, lat = [], []
    for i in range(len(gold)):
        logit, _, _, tw = infer(dev, open(os.path.join(d, f"{r['barcode']}_c{i}.raw"), "rb").read(), n)
        lg.append(logit)
        lat.append(tw * 1000)
    return lg, gold, lat


def outcome(pos: bool, rujuk: bool) -> str:
    return ("TP" if pos else "FP") if rujuk else ("FN" if pos else "TN")


def rate_table(items: list) -> str:
    """items: [(label, {TP,FP,FN,TN})] -> tabel TP/FP/FN/TN dengan sensitivitas dan spesifisitas."""
    rows = [[lab, str(c["TP"]), str(c["FP"]), str(c["FN"]), str(c["TN"]),
             f"{c['TP'] / max(c['TP'] + c['FN'], 1):.0%}", f"{c['TN'] / max(c['TN'] + c['FP'], 1):.0%}"] for lab, c in items]
    return table(rows, ["", "TP", "FP", "FN", "TN", "Sens", "Spes"], (0,))


def miss_table(c: dict) -> str:
    return table([["TB tapi tidak dirujuk", str(c["FN"])], ["Bukan TB tapi dirujuk", str(c["FP"])]], ["Keputusan akhir", "Peserta"], (0,))


def main(argv: list[str]) -> int:
    amb, argv = opt(argv, "--ambang")
    nsub, argv = opt(argv, "--n")
    if len(argv) != 3:
        print(__doc__)
        return 1
    d, base, mpath = argv
    ambang = float(amb) if amb else float(open("ambang.txt").read().split()[0])
    man, names = load_manifest(mpath, int(nsub) if nsub else None)
    dev = Dev()
    if dev.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_axil")
        return 1
    n = dev.rd(NSAMP)
    rows, csvrows, detail, lat = [], [], [], []
    cm = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    same = total = 0
    t0 = time.time()
    for k, b in enumerate(names, 1):
        r = man[b]
        lg, gold, lt = run_participant(dev, d, r, n)
        lat += lt
        same += sum(a == g for a, g in zip(lg, gold))
        total += len(gold)
        mean = sum(lg) / len(lg)
        pos = r["y"] == "1"
        hs = outcome(pos, mean >= ambang)
        cm[hs] += 1
        rows.append([str(k), b, str(len(lg)), f"{mean:.0f}", "RUJUK" if mean >= ambang else "rendah",
                     "TB" if pos else "bukan TB", hs])
        csvrows.append([b, str(len(lg)), f"{mean:.1f}", " ".join(map(str, lg)), " ".join(map(str, gold)),
                        "SAMA" if lg == gold else "BEDA", "RUJUK" if mean >= ambang else "rendah",
                        "positif" if pos else "negatif", hs])
        detail.append(f"{hs}: {b}  logit {lg}  {r.get('wav', '')}")
        print(f"\r  memproses peserta {k}/{len(names)}", end="", flush=True)
    print()
    dt = time.time() - t0
    screen = "\n\n".join([table(rows, ["No", "Peserta", "Klip", "Logit", "Risiko", "Label", "Hasil"], (1, 4, 5, 6)), miss_table(cm)])
    print(screen)
    note = ("\n\n" + rate_table([("audio saja", cm)]) + f"\n\nLogit = rata-rata logit semua klip peserta. RUJUK bila logit >= {ambang:g}.\n"
            f"{len(names)} peserta, {total} klip | {dt:.1f} s | latensi median {statistics.median(lat):.1f} ms per klip\n"
            f"bit-exact terhadap golden: {same}/{total} klip\nAlat triase, bukan diagnosis.\n\nRincian per peserta:\n")
    open(base + ".txt", "w").write(screen + note + "\n".join(detail) + "\n")
    with open(base + ".csv", "w") as fo:
        fo.write("peserta,n_klip,logit_rata,logit_klip,golden_klip,cek,risiko,label,hasil\n")
        for r in csvrows:
            fo.write(",".join(r) + "\n")
    print(f"Tersimpan: {base}.txt dan {base}.csv")
    return 0 if same == total else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
