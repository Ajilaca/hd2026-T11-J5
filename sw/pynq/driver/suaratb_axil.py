"""Driver PYNQ untuk SuaraTB (host AXI4-Lite) di Kria KV260: memprogram bitstream, mengumpan klip batuk ke RTL, mengolah hasilnya.

Pemakaian di papan (Ubuntu Kria dengan PYNQ terpasang; berkas .bit dan .hwh bernama sama dalam satu folder):
  sudo -E python3 suaratb_axil.py --bit ~/suaratb_axil_P32.bit --clip batuk1.wav batuk2.wav batuk3.wav
  sudo -E python3 suaratb_axil.py --bit ~/suaratb_axil_P32.bit --clip a.wav --expect-model qmodel.npz --repo ~/suaratb
  sudo -E python3 suaratb_axil.py --bit ~/suaratb_axil_P32.bit --mic --listen 3        # mode mikrofon INMP441
  sudo -E python3 suaratb_axil.py --bit ~/suaratb_axil_P32.bit --info                  # VERSION, jumlah sampel, status
Alur satu klip: CTRL.mode=0 -> DS_CTRL=1 -> 8240 x DS_DATA -> tunggu STATUS.result_new -> RESULT.
Penahanan jarak sampel dilakukan perangkat keras (tulisan DS_DATA ditunda), jadi tidak ada penundaan di sisi perangkat lunak.
Keluaran adalah logit int16 mentah dan rata-ratanya; BELUM ADA kalibrasi ke probabilitas. Alat ini triase (prioritas rujukan ke tes
TCM/dahak), bukan diagnosis; --threshold hanya membandingkan rata-rata logit dengan ambang yang Anda berikan.
Peta register: target/kv260/axi/rtl/axil_ctrl.v. Alamat dasar bawaan 0xA000_0000 (M_AXI_HPM0_FPD, create_bd_axil.tcl).
"""
from __future__ import annotations

import argparse
import math
import pathlib
import struct
import sys
import time
import wave
from dataclasses import dataclass

import numpy as np

CTRL, STATUS, RESULT, VERSION, NSAT, FRAMES, DS_CTRL, DS_DATA, NSAMP = 0x000, 0x004, 0x008, 0x00C, 0x010, 0x014, 0x018, 0x01C, 0x020
ST_BUSY, ST_REC, ST_NEW, ST_READY = 0x1, 0x2, 0x4, 0x8
EXPECT_VERSION = 0xA1000001
BASE_ADDR = 0xA000_0000
FS = 16000


@dataclass
class Result:
    logit: int      # int16 dari RTL
    seq: int        # nomor hasil (modulo 256)


def _resample(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == FS:
        return x
    try:
        from scipy.signal import resample_poly
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(f"WAV {sr} Hz perlu scipy untuk resample ke 16 kHz (atau berikan WAV 16 kHz)") from e
    g = math.gcd(FS, sr)
    return resample_poly(x.astype(np.float64), FS // g, sr // g)


def load_wav(path: str) -> np.ndarray:
    """WAV 16 bit (mono atau stereo, laju apa pun) -> int16 mono 16 kHz."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: wajib 16 bit (dapat {8 * w.getsampwidth()} bit)")
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    x = _resample(x, sr)
    return np.clip(np.round(x), -32768, 32767).astype(np.int16)


def to_clip(x: np.ndarray, n: int, window: str = "first") -> np.ndarray:
    """Potong atau isi nol ke n sampel. window='first' atau 'loudest' (jendela n sampel berenergi terbesar)."""
    x = np.asarray(x).astype(np.int64).ravel()
    if x.size > n and window == "loudest":
        c = np.concatenate([[0], np.cumsum(x * x)])
        e = c[n:] - c[:-n]
        s = int(np.argmax(e))
        x = x[s:s + n]
    out = np.zeros(n, dtype=np.int64)
    m = min(n, x.size)
    out[:m] = x[:m]
    return np.clip(out, -32768, 32767).astype(np.int16)


class SuaraTB:
    """Satu perangkat SuaraTB di PL. `mmio` boleh diganti objek tiruan (read/write) untuk uji tanpa papan."""

    def __init__(self, bitfile: str | None = None, base: int = BASE_ADDR, mmio=None, download: bool = True):
        self.overlay = None
        if mmio is None:
            from pynq import MMIO, Overlay          # hanya ada di papan
            self.overlay = Overlay(str(bitfile), download=download)      # 1) memprogram bitstream (butuh .hwh sebelah .bit)
            for name, d in getattr(self.overlay, "ip_dict", {}).items():
                if "suaratb_axil_ip" in str(d.get("type", "")) or name == "u_ip":
                    base = int(d["phys_addr"])
                    break
            mmio = MMIO(base, 0x1000)
        self.mmio = mmio
        v = self.mmio.read(VERSION)
        if v != EXPECT_VERSION:
            raise RuntimeError(f"VERSION 0x{v:08X} != 0x{EXPECT_VERSION:08X}: bitstream salah, belum diprogram, atau alamat dasar 0x{base:X} salah")
        self.n_samples = self.mmio.read(NSAMP)

    # ---- register -------------------------------------------------------------------------------------------
    def status(self) -> dict:
        s = self.mmio.read(STATUS)
        return dict(cnn_busy=bool(s & ST_BUSY), recording=bool(s & ST_REC), result_new=bool(s & ST_NEW), ds_ready=bool(s & ST_READY))

    def info(self) -> dict:
        return dict(version=f"0x{self.mmio.read(VERSION):08X}", n_samples=self.n_samples, frames=self.mmio.read(FRAMES) & 0xFFFF,
                    nsat=self.mmio.read(NSAT) & 0xFFFF, **self.status())

    def clear(self) -> None:
        self.mmio.write(CTRL, 0x2 | (self.mmio.read(CTRL) & 1))

    def _read_result(self) -> Result:
        r = self.mmio.read(RESULT)
        return Result(struct.unpack("<h", struct.pack("<H", r & 0xFFFF))[0], (r >> 16) & 0xFF)

    def wait_result(self, timeout: float) -> Result:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.mmio.read(STATUS) & ST_NEW:
                return self._read_result()
        raise TimeoutError(f"tidak ada hasil dalam {timeout} s (STATUS={self.status()})")

    # ---- 2) umpan input ke RTL -----------------------------------------------------------------------------
    def infer(self, x: np.ndarray, timeout: float = 10.0) -> Result:
        """Satu klip (n_samples int16) -> logit. Klip dikirim sampel demi sampel; perangkat keras menahan tulisan sesuai jarak minimum."""
        x = np.asarray(x, dtype=np.int16)
        if x.size != self.n_samples:
            raise ValueError(f"klip harus {self.n_samples} sampel, dapat {x.size}")
        self.mmio.write(CTRL, 0x0)                    # mode dataset
        self.mmio.write(DS_CTRL, 1)                   # klip baru (membersihkan jalur DSP)
        for s in x.astype("<i2").view("<u2"):
            self.mmio.write(DS_DATA, int(s))
        return self.wait_result(timeout)

    def listen(self, n: int, timeout: float = 30.0) -> list[Result]:
        """Mode mikrofon: tunggu n hasil dari detektor batuk."""
        self.mmio.write(CTRL, 0x1)
        return [self.wait_result(timeout) for _ in range(n)]

    # ---- 3) olah keluaran -------------------------------------------------------------------------------------
    @staticmethod
    def summarize(logits: list[int], threshold: float | None = None) -> dict:
        m = float(np.mean(logits))
        out = dict(n=len(logits), logits=[int(v) for v in logits], mean_logit=round(m, 2),
                   std_logit=round(float(np.std(logits)), 2))
        if threshold is not None:
            out["above_threshold"] = m >= threshold
            out["threshold"] = threshold
        return out


def golden_logit(x: np.ndarray, qmodel: str, repo: str | None) -> int:
    if repo:
        sys.path.insert(0, str(pathlib.Path(repo).expanduser()))
    from golden.blocks import cnn as C
    from golden.blocks import frontend as F
    return int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), C.load_qmodel(qmodel))[0])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bit", required=True, help="berkas .bit (.hwh bernama sama harus ada di folder yang sama)")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=BASE_ADDR, help="alamat dasar bila IP tidak ditemukan di .hwh")
    ap.add_argument("--no-download", action="store_true", help="jangan memprogram ulang (bitstream sudah dimuat)")
    ap.add_argument("--clip", nargs="+", metavar="WAV", help="1-5 klip batuk (.wav); logit dirata-rata")
    ap.add_argument("--window", choices=["first", "loudest"], default="first", help="klip lebih panjang dari 8240 sampel: ambil awal atau jendela terkeras")
    ap.add_argument("--mic", action="store_true", help="mode mikrofon INMP441")
    ap.add_argument("--listen", type=int, default=1, help="jumlah hasil mikrofon yang ditunggu")
    ap.add_argument("--info", action="store_true", help="tampilkan VERSION dan status lalu keluar")
    ap.add_argument("--expect-model", metavar="QMODEL.npz", help="bandingkan dengan golden (butuh --repo)")
    ap.add_argument("--repo", help="folder repo SuaraTB di papan (untuk modul golden)")
    ap.add_argument("--threshold", type=float, help="ambang rata-rata logit (belum dikalibrasi; dari Anda)")
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args(argv)

    dev = SuaraTB(a.bit, base=a.base, download=not a.no_download)
    if a.info:
        print(dev.info())
        return 0
    logits: list[int] = []
    if a.mic:
        for r in dev.listen(a.listen, a.timeout):
            print(f"mikrofon: logit={r.logit} seq={r.seq}")
            logits.append(r.logit)
    else:
        if not a.clip or len(a.clip) > 5:
            ap.error("beri --clip 1 sampai 5 berkas, atau --mic, atau --info")
        mism = 0
        for i, f in enumerate(a.clip, 1):
            x = to_clip(load_wav(f), dev.n_samples, a.window)
            r = dev.infer(x, a.timeout)
            line = f"klip {i}/{len(a.clip)} {pathlib.Path(f).name}: logit={r.logit} seq={r.seq}"
            if a.expect_model:
                exp = golden_logit(x, a.expect_model, a.repo)
                line += f" golden={exp} {'SAMA' if exp == r.logit else 'BEDA'}"
                mism += exp != r.logit
            print(line)
            logits.append(r.logit)
        if a.expect_model and mism:
            print(f"{mism} klip BEDA dari golden")
            return 2
    s = dev.summarize(logits, a.threshold)
    print(f"rata-rata logit ({s['n']} batuk) = {s['mean_logit']}  (simpangan {s['std_logit']})")
    if a.threshold is not None:
        print("rata-rata di atas ambang: prioritaskan rujukan ke tes TCM/dahak" if s["above_threshold"]
              else "rata-rata di bawah ambang; ambang belum dikalibrasi dan ini bukan diagnosis")
    else:
        print("catatan: logit belum dikalibrasi ke probabilitas; alat ini untuk triase, bukan diagnosis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
