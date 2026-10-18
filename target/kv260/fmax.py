"""Cari Fmax suaratb_top di XCK26 (OOC, setelah route). Dari ROOT repo: python target/kv260/fmax.py [P ...]   (default: 16 32)

Metode (satu run Vivado per titik, satu seed, TANPA seed sweep):
  1. Mulai dari periode T0 (default 4,0 ns). Selama WNS >= 0, percepat 10% (T x 0,90) sampai gagal ("lompat").
     Bila T0 gagal, perlambat 10% sampai terpenuhi.
  2. Bagi dua antara periode terkecil yang terpenuhi dan periode terbesar yang gagal sampai selisihnya <= TOL (0,03 ns).
  3. Fmax terkonfirmasi = 1 / (periode terkecil dengan WNS >= 0). WNS tidak monoton terhadap periode, jadi angka ini batas untuk satu seed.
Hasil: CSV P,T_ns,WNS_ns,terpenuhi,MHz di $SUARATB_DATA/build/kv260/fmax/fmax.csv; titik yang sudah ada di CSV tidak dijalankan lagi.
MODE=full: build sistem penuh (MMCM dari PS, I/O, XDC); MMCM tidak persis di 1000/T, WNS dibaca dari laporan. OOC: tanpa I/O dan MMCM.
Env: MODE, T0, TOL, MODEL, VIVADO, MAX_RUNS (12 per P).
"""
from __future__ import annotations

import csv
import os
import pathlib
import subprocess
import sys

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
VIVADO = os.environ.get("VIVADO", "/data/tools/Xilinx/2026.1/Vivado/bin/vivado")
MODEL = os.environ.get("MODEL", str(D / "runs/model_v2/qmodel.npz"))
T0 = float(os.environ.get("T0", "4.0"))
TOL = float(os.environ.get("TOL", "0.03"))
MAX_RUNS = int(os.environ.get("MAX_RUNS", "12"))
MODE = os.environ.get("MODE", "ooc")        # ooc | full (full = BD + MMCM + I/O + XDC, periode = 1000/CORE_MHZ)
OUT = D / "build/kv260" / ("fmax" if MODE == "ooc" else "fmax_full")
CSV = OUT / "fmax.csv"
ROOT = pathlib.Path(__file__).resolve().parents[2]


def snap(t: float) -> float:
    """Mode full: bulatkan ke kelipatan 1,024 MHz (BCLK I2S = clk/N tepat 1,024 MHz); ooc: apa adanya."""
    if MODE != "full":
        return round(t, 3)
    return round(1000 / (round(1000 / t / 1.024) * 1.024), 3)


def cached(p: int) -> dict[float, float]:
    if not CSV.exists():
        return {}
    return {round(float(r["T_ns"]), 3): float(r["WNS_ns"]) for r in csv.DictReader(CSV.open()) if int(r["P"]) == p}


def run(p: int, t: float) -> float | None:
    t = snap(t)
    known = cached(p)
    if t in known:
        return known[t]
    pdir = D / "build/synth" / f"P{p}"
    if not (pdir / "cnn_cfg_pkg.sv").exists():
        subprocess.run([str(ROOT / ".venv/bin/python"), "target/artix7/prep_synth.py", "--p", str(p), "--out", str(pdir),
                        "--model", MODEL], cwd=ROOT, check=True)
    tag = f"P{p}_T{t:.3f}"
    env = dict(os.environ, P=str(p), PDIR=str(pdir), OUT=str(OUT / tag), MODE=MODE, CLK_NS=f"{t:.3f}", CORE_MHZ=f"{round(1000 / t / 1.024) * 1.024 if MODE == 'full' else 1000 / t:.3f}")
    subprocess.run([VIVADO, "-mode", "batch", "-source", "target/kv260/synth.tcl", "-log", str(OUT / f"{tag}.log"),
                    "-journal", str(OUT / f"{tag}.jou")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rpt = OUT / tag / "timing_impl.rpt"
    if not rpt.exists():
        return None
    lines = rpt.read_text().splitlines()
    for i, ln in enumerate(lines):
        if "WNS(ns)" in ln:
            wns = float(lines[i + 2].split()[0])
            break
    else:
        return None
    new = not CSV.exists()
    with CSV.open("a") as f:
        if new:
            f.write("P,T_ns,WNS_ns,terpenuhi,MHz\n")
        f.write(f"{p},{t:.3f},{wns:.3f},{'ya' if wns >= 0 else 'tidak'},{1000 / t:.2f}\n")
    print(f"P={p} T={t:.3f} ns ({1000 / t:.1f} MHz) WNS={wns:+.3f} {'terpenuhi' if wns >= 0 else 'GAGAL'}", flush=True)
    return wns


def search(p: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = 0
    if not cached(p):
        if run(p, snap(T0)) is None:
            print(f"P={p}: run gagal (lihat {OUT})"); return
        runs += 1
    k = cached(p)
    met = [t for t, w in k.items() if w >= 0]
    if not met:                                   # semua gagal: perlambat 10% sampai ada yang terpenuhi
        t = max(k)
        while runs < MAX_RUNS:
            t = snap(t * 1.10)
            w = run(p, t); runs += 1
            if w is None:
                return
            if w >= 0:
                break
        k = cached(p); met = [t for t, w in k.items() if w >= 0]
        if not met:
            print(f"P={p}: tidak ada periode terpenuhi"); return
    lo = min(met)                                 # periode terkecil yang terpenuhi
    fails = [t for t, w in k.items() if w < 0 and t < lo]
    hi = max(fails) if fails else None            # periode terbesar yang gagal di bawah lo
    while hi is None and runs < MAX_RUNS:         # lompat: percepat 10% sampai gagal
        t = snap(lo * 0.90)
        w = run(p, t); runs += 1
        if w is None:
            return
        if w >= 0:
            lo = t
        else:
            hi = t
    while hi is not None and lo - hi > TOL and runs < MAX_RUNS:   # bagi dua
        t = snap((lo + hi) / 2)
        w = run(p, t); runs += 1
        if w is None:
            return
        if w >= 0:
            lo = round(t, 3)
        else:
            hi = round(t, 3)
    print(f"P={p}: periode terkecil dengan WNS>=0 = {lo:.3f} ns -> Fmax terkonfirmasi {1000 / lo:.1f} MHz"
          + (f"; gagal pada {hi:.3f} ns ({1000 / hi:.1f} MHz)" if hi else "; batas gagal belum ditemukan"), flush=True)


if __name__ == "__main__":
    for p in [int(a) for a in sys.argv[1:]] or [16, 32]:
        search(p)
    print("SELESAI")
