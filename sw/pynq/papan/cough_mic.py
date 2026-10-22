"""Model demonstrasi batuk vs bukan batuk (K-29): mikrofon INMP441 live (hanya pustaka standar; butuh root).

    sudo python3 cough_mic.py          # Ctrl+C untuk berhenti
Bitstream suaratb_cough harus dimuat (sudo xmutil loadapp suaratb_cough). FPGA mendeteksi tiap suara keras, memotong 0,5 s, dan
menghitung satu logit. Skrip mencetak BATUK bila logit >= 0. Setiap suara ditambahkan ke suara_log.csv.
Ambang belum dikalibrasi untuk INMP441. Tugas demonstrasi akselerator, bukan skrining TBC.
"""
import math
import os
import struct
import sys
import time

from axil_mic import check_mic, restart
from axil_smoke import CTRL, RESULT, STATUS, VERSION, Dev

ST_NEW = 0x4


def main(argv: list[str]) -> int:
    d = Dev(app="suaratb_cough")
    if d.rd(VERSION) != 0xA1000001:
        print("Bitstream belum dimuat. Jalankan: sudo xmutil loadapp suaratb_cough")
        return 1
    restart(d)
    check_mic(d)
    print("Mikrofon siap. Batuk atau bicara di dekat mikrofon; tiap suara diberi satu hasil. Ctrl+C untuk berhenti.")
    print()
    new = not os.path.exists("suara_log.csv")
    k = n_b = 0
    try:
        with open("suara_log.csv", "a") as fo:
            if new:
                fo.write("no,waktu,logit,skor,prediksi\n")
            while True:
                if d.rd(STATUS) & ST_NEW:
                    r = d.rd(RESULT)
                    logit = struct.unpack("<h", struct.pack("<H", r & 0xFFFF))[0]
                    p = 1.0 / (1.0 + math.exp(-max(min(logit / 256.0, 50.0), -50.0)))
                    k += 1
                    is_b = logit >= 0
                    n_b += is_b
                    lab = "BATUK" if is_b else "bukan batuk"
                    print(f"  suara {k:3d}   logit {logit:6d}   skor {p:4.0%}   ->  {lab}", flush=True)
                    fo.write(f"{k},{time.strftime('%H:%M:%S')},{logit},{p:.4f},{'batuk' if is_b else 'bukan'}\n")
                    fo.flush()
                time.sleep(0.005)
    except KeyboardInterrupt:
        print(f"\nSelesai: {k} suara, {n_b} di antaranya dinilai batuk. Log di suara_log.csv")
        d.wr(CTRL, 0x2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
