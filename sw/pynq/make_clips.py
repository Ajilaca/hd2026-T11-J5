"""Siapkan klip dataset untuk papan (jalankan di laptop, dari ROOT repo, dengan .venv).

    python -m sw.pynq.make_clips --n-per-class 50 --device phonec --out $SUARATB_DATA/work/board_test/dataset
Keluaran: <out>/clips/<barcode>.raw (int16 little-endian, 8240 sampel), <out>/manifest.csv
(barcode,y,device,clip_idx,golden_logit) dan <out>/paket/ (salin folder ini ke papan: skrip + klip).
Klip berasal dari processed/clips (detektor golden, sama dengan hardware); satu klip pertama per peserta.
Logit golden dihitung dari qmodel yang sama dengan ROM di bitstream (--qmodel).
"""
import argparse
import pathlib
import shutil

import numpy as np
import pandas as pd

from golden import paths
from golden.blocks import cnn as C
from golden.blocks import frontend as F

HERE = pathlib.Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-per-class", type=int, default=50)
    ap.add_argument("--device", default="phonec", choices=["phonea", "phoneb", "phonec", "recorder"])
    ap.add_argument("--qmodel", default=str(paths.runs_dir() / "model_distill" / "qmodel.npz"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(paths.data_root() / "work" / "board_test" / "dataset"))
    a = ap.parse_args()

    sp = pd.read_csv(paths.processed_dir() / "splits_v2.csv")[["barcode", "y"]].drop_duplicates("barcode")
    have = {p.stem for p in (paths.processed_dir() / "clips" / a.device).glob("*.npz")}
    sp = sp[sp.barcode.isin(have)]
    rng = np.random.default_rng(a.seed)
    pick = pd.concat([g.sample(min(a.n_per_class, len(g)), random_state=int(rng.integers(1 << 31))) for _, g in sp.groupby("y")])
    ci = pd.read_csv(paths.processed_dir() / "clip_index.csv")
    wav = {(r.barcode, r.device): r.path for r in ci.itertuples()}   # barcode+perangkat -> WAV asli (relatif ke data/raw)
    out = pathlib.Path(a.out)
    (out / "clips").mkdir(parents=True, exist_ok=True)
    q = C.load_qmodel(a.qmodel)
    rows = []
    for b, y in zip(pick.barcode, pick.y):
        x = np.load(paths.processed_dir() / "clips" / a.device / f"{b}.npz", allow_pickle=True)["clips"][0].astype(np.int16)
        assert x.size == 8240, (b, x.size)
        x.astype("<i2").tofile(out / "clips" / f"{b}.raw")
        g = int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), q)[0])
        rows.append((b, int(y), a.device, 0, g, wav.get((b, a.device), "")))
    pd.DataFrame(rows, columns=["barcode", "y", "device", "clip_idx", "golden_logit", "wav"]).to_csv(out / "manifest.csv", index=False)
    pk = out / "paket"
    if pk.exists():
        shutil.rmtree(pk)
    (pk).mkdir()
    shutil.copy(HERE / "axil_batch.py", pk)
    shutil.copy(HERE / "axil_smoke.py", pk)
    shutil.copy(out / "manifest.csv", pk)
    amb = out.parent / "ambang.json"                  # dari sw.pynq.calibrate_ambang; dipakai axil_batch.py bila ada
    if amb.exists():
        import json
        (pk / "ambang.txt").write_text(f"{json.load(open(amb))['ambang']}\n")
    shutil.copytree(out / "clips", pk / "clips")
    print(f"{len(rows)} klip ({int(pick.y.sum())} positif) -> {out}; salin {pk} ke papan")


if __name__ == "__main__":
    main()
