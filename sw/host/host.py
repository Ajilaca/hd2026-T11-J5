"""Host UART untuk suaratb_top di KV260 (atau simulasi): kirim klip mode dataset 'D', baca logit 'L', akses CSR, pilih mode.

Protokol (rtl/sys/uart_bridge.sv, rtl/sys/csr.sv):
  'W' addr data   tulis CSR            'R' addr   baca CSR (balas 1 byte)
  'D' + 8240 x int16 LE   klip dataset (mode dataset, CSR 0x00 bit0 = 0)
  hasil: 'L' lo hi seq (4 byte) tiap inferensi selesai; logit = int16 (lo | hi << 8)
Baud default 115200 = 147,456 MHz / 1280 (CLK_PER_BIT di kv260_top). Jarak sampel dataset 2 byte UART >> 404 siklus, jadi
baud lebih tinggi (mis. 921600 dengan UART_BAUD=921600 di build) aman.

Contoh:
  python sw/host/host.py --port /dev/ttyUSB0 --clip batuk1.wav batuk2.wav batuk3.wav     # rata-rata logit 3-5 batuk
  python sw/host/host.py --port /dev/ttyUSB0 --vector cough --expect-model model_v2      # klip uji repo + bandingkan golden
  python sw/host/host.py --port /dev/ttyUSB0 --mic --listen 3                           # mode mikrofon INMP441
  python sw/host/host.py --port /dev/ttyUSB0 --csr-read 0x07                            # VERSION
Dependensi: pyserial, numpy (golden hanya untuk --expect-model).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import struct
import sys
import time
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
N_SAMPLES = 8240          # suaratb_pkg::CLIP_SAMPLES_PADDED
CSR_CTRL, CSR_STATUS, CSR_VERSION = 0x00, 0x01, 0x07


class Device:
    """Pembungkus protokol di atas objek serial (read/write/timeout); mudah diganti tiruan untuk uji."""

    def __init__(self, ser):
        self.ser = ser

    def write_csr(self, addr: int, data: int) -> None:
        self.ser.write(bytes([ord("W"), addr & 0xFF, data & 0xFF]))

    def read_csr(self, addr: int) -> int:
        self.ser.write(bytes([ord("R"), addr & 0xFF]))
        b = self.ser.read(1)
        if len(b) != 1:
            raise TimeoutError(f"CSR 0x{addr:02X}: tidak ada balasan")
        return b[0]

    def set_mode(self, mic: bool) -> None:
        self.write_csr(CSR_CTRL, 1 if mic else 0)

    def send_clip(self, x: np.ndarray) -> None:
        x = np.asarray(x, dtype="<i2")
        if x.size != N_SAMPLES:
            raise ValueError(f"klip harus {N_SAMPLES} sampel, dapat {x.size}")
        self.ser.write(b"D" + x.tobytes())

    def read_result(self, timeout: float = 10.0) -> tuple[int, int]:
        """Baca satu bingkai 'L' lo hi seq. Mengembalikan (logit int16, seq)."""
        t0, buf = time.time(), b""
        while time.time() - t0 < timeout:
            b = self.ser.read(1)
            if not b:
                continue
            buf = (buf + b)[-4:]
            if len(buf) == 4 and buf[0] == ord("L"):
                return struct.unpack("<h", buf[1:3])[0], buf[3]
        raise TimeoutError("tidak ada hasil 'L' dari perangkat")

    def infer(self, x: np.ndarray, timeout: float = 10.0) -> tuple[int, int]:
        self.set_mode(False)
        self.send_clip(x)
        return self.read_result(timeout)


def pad_clip(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x).astype(np.int64).ravel()
    out = np.zeros(N_SAMPLES, dtype=np.int64)
    n = min(N_SAMPLES, x.size)
    out[:n] = x[:n]
    return np.clip(out, -32768, 32767).astype(np.int16)


def load_clip(path: str) -> np.ndarray:
    """Baca .wav (16 kHz, 16 bit, mono), .npy, .mem (hex 16 bit per baris), atau .bin/.raw (int16 LE). Dipotong/diisi nol ke 8240."""
    p = pathlib.Path(path)
    suf = p.suffix.lower()
    if suf == ".wav":
        with wave.open(str(p), "rb") as w:
            if w.getframerate() != 16000 or w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError(f"{p.name}: wajib 16 kHz, 16 bit, mono (dapat {w.getframerate()} Hz, "
                                 f"{8 * w.getsampwidth()} bit, {w.getnchannels()} kanal)")
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    elif suf == ".npy":
        x = np.load(p)
    elif suf == ".mem":
        x = np.array([int(v, 16) for v in p.read_text().split()], dtype=np.int64)
        x = np.where(x >= 0x8000, x - 0x10000, x)
    else:
        x = np.fromfile(p, dtype="<i2")
    return pad_clip(x)


def golden_logit(x: np.ndarray, model: str) -> int:
    sys.path.insert(0, str(ROOT))
    from golden.blocks import cnn as C
    from golden.blocks import frontend as F
    path = pathlib.Path(model)
    if not path.suffix:
        path = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb")) / "runs" / model / "qmodel.npz"
    qm = C.load_qmodel(path)
    return int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), qm)[0])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="mis. /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200, help="harus sama dengan UART_BAUD saat build (default 115200)")
    ap.add_argument("--clip", nargs="+", metavar="BERKAS", help="1-5 klip batuk (.wav/.npy/.mem/.bin); logit dirata-rata")
    ap.add_argument("--vector", choices=["cough", "noise3", "noise100", "impulse", "sine1k"], help="pakai klip uji sintetis dari tb/vectors")
    ap.add_argument("--expect-model", metavar="NAMA|JALUR", help="hitung logit golden dari qmodel.npz (mis. model_v2) dan bandingkan")
    ap.add_argument("--mic", action="store_true", help="mode mikrofon: pilih CSR mode=1 lalu tunggu hasil")
    ap.add_argument("--listen", type=int, default=1, help="jumlah hasil yang ditunggu pada mode mikrofon")
    ap.add_argument("--csr-read", metavar="ADDR", help="baca satu CSR (mis. 0x07) lalu keluar")
    ap.add_argument("--csr-write", nargs=2, metavar=("ADDR", "DATA"), help="tulis satu CSR lalu keluar")
    ap.add_argument("--timeout", type=float, default=10.0, help="detik menunggu hasil")
    a = ap.parse_args(argv)

    import serial  # pyserial
    dev = Device(serial.Serial(a.port, a.baud, timeout=0.2))
    if a.csr_write:
        dev.write_csr(int(a.csr_write[0], 0), int(a.csr_write[1], 0))
        return 0
    if a.csr_read:
        print(f"CSR[{a.csr_read}] = 0x{dev.read_csr(int(a.csr_read, 0)):02X}")
        return 0
    if a.mic:
        dev.set_mode(True)
        logits = []
        for _ in range(a.listen):
            lg, seq = dev.read_result(a.timeout)
            logits.append(lg)
            print(f"mikrofon: logit={lg} seq={seq}")
        print(f"rata-rata logit ({len(logits)} batuk) = {np.mean(logits):.2f}")
        return 0

    clips = []
    if a.vector:
        clips.append(load_clip(str(ROOT / "tb" / "vectors" / "frontend" / f"{a.vector}_in.mem")))
    for f in a.clip or []:
        clips.append(load_clip(f))
    if not clips:
        ap.error("beri --clip, --vector, --mic, atau --csr-read/--csr-write")
    if len(clips) > 5:
        ap.error("maksimum 5 klip")
    logits = []
    for i, x in enumerate(clips):
        lg, seq = dev.infer(x, a.timeout)
        line = f"klip {i + 1}/{len(clips)}: logit={lg} seq={seq}"
        if a.expect_model:
            exp = golden_logit(x, a.expect_model)
            line += f" golden={exp} {'SAMA' if exp == lg else 'BEDA'}"
        print(line)
        logits.append(lg)
    if len(logits) > 1:
        print(f"rata-rata logit ({len(logits)} batuk) = {np.mean(logits):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
