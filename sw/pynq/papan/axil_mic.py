"""Uji mikrofon INMP441 di papan lewat AXI4-Lite, mode SESI (hanya pustaka standar; butuh root untuk /dev/mem).

    sudo python3 axil_mic.py [--n 10] [--ambang 35]      # Ctrl+C untuk berhenti
Bitstream suaratb_axil harus sudah dimuat (sudo xmutil loadapp suaratb_axil). FPGA mendeteksi tiap batuk, memotong 0,5 s, dan
menghitung satu logit per batuk. Skrip mengumpulkan --n batuk dalam satu sesi, lalu SATU keputusan dari rata-rata logit:
RUJUK bila rata-rata >= --ambang. Satu batuk hampir tidak informatif (AUROC 0,52); rata-rata 10 batuk 0,70 (klip ponsel Zambia,
optimistis). Ambang bawaan 35 = sensitivitas 80% / spesifisitas 41% untuk rata-rata 10 batuk pada klip ponsel; TIDAK dikalibrasi
untuk INMP441. Setiap sesi ditambahkan ke sesi_log.csv. Alat triase, bukan diagnosis.
"""
import os
import struct
import sys
import time

from axil_batch import table
from axil_smoke import Dev, VERSION, CTRL, STATUS, RESULT, FRAMES

ST_NEW = 0x4


def arg(argv: list[str], name: str, default: float) -> float:
    return float(argv[argv.index(name) + 1]) if name in argv else default


def restart(d: Dev) -> None:
    """Mode mikrofon + clear: membersihkan jalur DSP dan hasil yang tertunda."""
    d.wr(CTRL, 0x3)
    time.sleep(0.05)
    d.wr(CTRL, 0x1)
    if d.rd(STATUS) & ST_NEW:
        d.rd(RESULT)


def session(d: Dev, k: int, n: int, t0: float) -> list[int]:
    print(f"\nSilakan batuk {n} kali, jeda sekitar 1 detik.", flush=True)
    logits, last = [], time.time()
    while len(logits) < n:
        s = d.rd(STATUS)
        if s & ST_NEW:
            r = d.rd(RESULT)
            logit = struct.unpack("<h", struct.pack("<H", r & 0xFFFF))[0]
            logits.append(logit)
            last = time.time()
            print(f"  batuk {len(logits):2d}/{n}   logit {logit:6d}", flush=True)
        elif time.time() - last > 30:
            print("  belum terdengar batuk; coba lebih keras dan dekat ke mikrofon", flush=True)
            last = time.time()
        time.sleep(0.005)
    return logits


def check_mic(d: Dev) -> None:
    """Pastikan mikrofon mengirim data (FRAMES naik sekitar 100 per detik)."""
    f0 = d.rd(FRAMES) & 0xFFFF
    time.sleep(1.0)
    rate = ((d.rd(FRAMES) & 0xFFFF) - f0) & 0xFFFF
    if not 80 <= rate <= 120:
        print(f"Peringatan: mikrofon tidak mengirim data dengan benar ({rate} frame/detik, harusnya sekitar 100). Cek kabel.")


def main(argv: list[str]) -> int:
    n = int(arg(argv, "--n", 10))
    ambang = arg(argv, "--ambang", 35.0)
    d = Dev()
    if d.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_axil")
        return 1
    restart(d)
    check_mic(d)
    t0 = time.time()
    print(f"Mikrofon siap. Satu sesi = {n} batuk, lalu satu hasil. Hasilnya untuk triase, bukan diagnosis.")
    new = not os.path.exists("sesi_log.csv")
    k = done = 0
    try:
        while True:
            k += 1
            print(f"\n=== Sesi {k} ===")
            restart(d)
            lg = session(d, k, n, t0)
            mean = sum(lg) / len(lg)
            rk = mean >= ambang
            print(table([["Rata-rata logit", f"{mean:.1f}"], ["Batas", f"{ambang:g}"],
                         ["Hasil", "RUJUK, prioritaskan tes TCM/dahak" if rk else "risiko rendah"]], [f"Sesi {k}", ""], (0, 1)))
            with open("sesi_log.csv", "a") as fo:
                if new:
                    fo.write("sesi,waktu,n,rata_logit,ambang,keputusan,logit\n")
                    new = False
                fo.write(f"{k},{time.strftime('%Y-%m-%d %H:%M:%S')},{len(lg)},{mean:.1f},{ambang:g},"
                         f"{'RUJUK' if rk else 'rendah'},{' '.join(map(str, lg))}\n")
            done = k
            input("\nTekan Enter untuk sesi berikutnya, Ctrl+C untuk berhenti. ")
    except (KeyboardInterrupt, EOFError):
        print(f"\nSelesai: {done} sesi tersimpan di sesi_log.csv")
        d.wr(CTRL, 0x2)                   # mode dataset + clear: jangan tinggalkan hasil yang belum dibaca
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
