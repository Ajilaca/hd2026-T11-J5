"""Uji asap SuaraTB AXI4-Lite di papan tanpa PYNQ/numpy (hanya pustaka standar; butuh root untuk /dev/mem).

Bitstream harus sudah dimuat (xmutil loadapp). Klip berupa berkas mentah int16 little-endian 8240 sampel.
    sudo python3 axil_smoke.py cough.raw [noise3.raw ...] [--expect cough=-72 noise3=-2785]
Keluaran: VERSION, logit per klip dan, bila ada --expect, SAMA/BEDA terhadap logit golden.
"""
import mmap
import os
import struct
import sys
import time

BASE = 0xA0000000
CTRL, STATUS, RESULT, VERSION, NSAT, FRAMES, DS_CTRL, DS_DATA, NSAMP = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20
ST_NEW = 0x4


class Dev:
    def __init__(self, base: int = BASE):
        self.m = mmap.mmap(os.open("/dev/mem", os.O_RDWR | os.O_SYNC), 4096, offset=base)
        self.w = memoryview(self.m).cast("I")   # akses 32 bit murni (satu transaksi AXI, wstrb=1111); slice mmap bisa terpecah per byte

    def rd(self, o: int) -> int:
        return self.w[o >> 2]

    def wr(self, o: int, v: int) -> None:
        self.w[o >> 2] = v & 0xFFFFFFFF


def infer(d: Dev, raw: bytes, n: int, timeout: float = 10.0) -> tuple[int, int, float, float]:
    if len(raw) != 2 * n:
        raise SystemExit(f"klip harus {n} sampel ({2 * n} byte), dapat {len(raw)} byte")
    d.wr(CTRL, 0)
    d.wr(DS_CTRL, 1)
    t0 = time.time()
    for (s,) in struct.iter_unpack("<H", raw):
        d.wr(DS_DATA, s)
    t_feed = time.time() - t0
    t1 = time.time()
    while time.time() - t1 < timeout:
        if d.rd(STATUS) & ST_NEW:
            r = d.rd(RESULT)
            return struct.unpack("<h", struct.pack("<H", r & 0xFFFF))[0], (r >> 16) & 0xFF, t_feed, time.time() - t1
    raise SystemExit(f"tidak ada hasil dalam {timeout} s, STATUS=0x{d.rd(STATUS):X}")


def main(argv: list[str]) -> int:
    exp: dict[str, int] = {}
    files = []
    it = iter(argv)
    for a in it:
        if a == "--expect":
            for kv in it:
                k, v = kv.split("=")
                exp[k] = int(v)
        else:
            files.append(a)
    d = Dev()
    v = d.rd(VERSION)
    n = d.rd(NSAMP)
    print(f"VERSION 0x{v:08X} (harap 0xA1000001)  NSAMP {n}  STATUS 0x{d.rd(STATUS):X}")
    if v != 0xA1000001:
        return 1
    bad = 0
    for f in files:
        name = os.path.basename(f).rsplit(".", 1)[0]
        logit, seq, tf, _ = infer(d, open(f, "rb").read(), n)
        line = f"{name}: logit={logit} seq={seq} frames={d.rd(FRAMES) & 0xFFFF} nsat={d.rd(NSAT) & 0xFFFF} (kirim {tf:.2f} s)"
        if name in exp:
            ok = exp[name] == logit
            bad += not ok
            line += f" golden={exp[name]} {'SAMA' if ok else 'BEDA'}"
        print(line)
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
