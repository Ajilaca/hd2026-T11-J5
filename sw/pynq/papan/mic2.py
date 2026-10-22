"""Mode mic2: tanya gejala dulu, lalu rekam --n batuk lewat INMP441, satu keputusan dari fusi (hanya pustaka standar; butuh root).

    sudo python3 mic2.py [--n 10]      # Ctrl+C untuk berhenti
Butuh fusi.json. Skor fusi = gejala (5) + rata-rata logit --n batuk; koefisien dilatih pada rata-rata 10 klip ponsel Zambia.
Ambang optimistis dan BELUM dikalibrasi untuk INMP441. Setiap sesi ditambahkan ke sesi_log2.csv. Alat triase, bukan diagnosis.
"""
import os
import sys
import time

import fusi
from axil_batch import table
from axil_mic import arg, check_mic, restart, session
from axil_smoke import CTRL, VERSION, Dev


def main(argv: list[str]) -> int:
    n = int(arg(argv, "--n", 10))
    fz = fusi.load()
    coef, amb = fz["mic"]["coef"], fz["mic"]["ambang"]
    d = Dev()
    if d.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_axil")
        return 1
    restart(d)
    check_mic(d)
    t0 = time.time()
    print(f"Mikrofon siap. Tiap pasien: jawab 6 pertanyaan, lalu batuk {n} kali. Hasilnya untuk triase, bukan diagnosis.")
    new = not os.path.exists("sesi_log2.csv")
    k = done = 0
    try:
        while True:
            k += 1
            print(f"\n=== Pasien {k} ===")
            g = fusi.ask()
            cs = fusi.clin_score(fz, g)
            restart(d)
            lg = session(d, k, n, t0)
            mean = sum(lg) / len(lg)
            s = fusi.fuse(coef, cs, mean)
            rk = s >= amb
            print(table([["Rata-rata logit", f"{mean:.1f}"], ["Skor gabungan", f"{s:+.2f}"], ["Batas", f"{amb:+.2f}"],
                         ["Hasil", "RUJUK, prioritaskan tes TCM/dahak" if rk else "risiko rendah"]], [f"Pasien {k}", ""], (0, 1)))
            with open("sesi_log2.csv", "a") as fo:
                if new:
                    fo.write("sesi,waktu,n,coughdur,bmi,sex,weightloss,ngtsweats,skor_klinis,rata_logit,skor_fusi,ambang,keputusan,logit\n")
                    new = False
                fo.write(f"{k},{time.strftime('%Y-%m-%d %H:%M:%S')},{len(lg)},{g['coughdur']},{g['bmi']:.1f},{g['sex']},"
                         f"{g['weightloss']},{g['ngtsweats']},{cs:.3f},{mean:.1f},{s:.3f},{amb:.3f},"
                         f"{'RUJUK' if rk else 'rendah'},{' '.join(map(str, lg))}\n")
            done = k
            input("\nTekan Enter untuk pasien berikutnya, Ctrl+C untuk berhenti. ")
    except (KeyboardInterrupt, EOFError):
        print(f"\nSelesai: {done} pasien tersimpan di sesi_log2.csv")
        d.wr(CTRL, 0x2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
