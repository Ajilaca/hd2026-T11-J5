"""Uji mikrofon INMP441 di papan lewat AXI4-Lite (hanya pustaka standar; butuh root untuk /dev/mem).

    sudo python3 axil_mic.py            # mode mikrofon; batuk/tepuk di dekat mikrofon; Ctrl+C untuk berhenti
Bitstream suaratb_axil harus sudah dimuat (sudo xmutil loadapp suaratb_axil). Skrip menyalakan mode mikrofon (CTRL bit0), membersihkan status,
lalu mencetak tiap hasil: waktu, logit, urutan, dan penanda 'recording' (detektor batuk menangkap onset). Tiap batuk yang terdeteksi
menghasilkan satu logit setelah +-0,5 s. FRAMES bertambah ~100 per detik selama BCLK/WS berjalan (bukti jam I2S hidup; BUKAN bukti data mikrofon).
Logit belum dikalibrasi; ambang.txt (bila ada) berasal dari klip ponsel dan TIDAK berlaku untuk INMP441: penanda risiko hanya informatif.
Alat triase, bukan diagnosis.
"""
import os
import sys
import time

from axil_smoke import Dev, VERSION, CTRL, STATUS, RESULT, FRAMES, NSAT
import struct

ST_REC, ST_NEW = 0x2, 0x4


def main() -> int:
    d = Dev()
    if d.rd(VERSION) != 0xA1000001:
        print("VERSION salah: bitstream belum dimuat")
        return 1
    ambang = float(open("ambang.txt").read().split()[0]) if os.path.exists("ambang.txt") else None
    d.wr(CTRL, 0x3)                                   # mode mikrofon + clear
    time.sleep(0.05)
    d.wr(CTRL, 0x1)
    f0, t0 = d.rd(FRAMES) & 0xFFFF, time.time()
    time.sleep(1.0)
    f1, t1 = d.rd(FRAMES) & 0xFFFF, time.time()
    print(f"mode mikrofon aktif; FRAMES +{(f1 - f0) & 0xFFFF} dalam {t1 - t0:.2f} s (harap ~100/s bila BCLK/WS berjalan)")
    print("BCLK/WS aktif: ukur dengan multimeter pada pin 3 dan 4 (harap ~1,6 V DC). Batuk atau tepuk di dekat mikrofon. Ctrl+C untuk berhenti.")
    rec_prev, n = False, 0
    try:
        while True:
            s = d.rd(STATUS)
            rec = bool(s & ST_REC)
            if rec and not rec_prev:
                print(f"[{time.time() - t0:7.2f} s] onset terdeteksi (recording)", flush=True)
            rec_prev = rec
            if s & ST_NEW:
                r = d.rd(RESULT)
                logit = struct.unpack("<h", struct.pack("<H", r & 0xFFFF))[0]
                n += 1
                risk = "" if ambang is None else ("  RUJUK*" if logit >= ambang else "  rendah*")
                print(f"[{time.time() - t0:7.2f} s] hasil {n}: logit={logit} seq={(r >> 16) & 0xFF} nsat={d.rd(NSAT) & 0xFFFF}{risk}", flush=True)
            time.sleep(0.005)
    except KeyboardInterrupt:
        print(f"\nberhenti; {n} hasil. (* ambang dari klip ponsel; tidak berlaku untuk INMP441)")
        d.wr(CTRL, 0x0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
