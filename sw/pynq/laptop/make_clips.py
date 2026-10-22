"""Siapkan klip dataset untuk papan (jalankan di laptop, dari ROOT repo, dengan .venv).

    python -m sw.pynq.laptop.make_clips --n-per-class 50 --klip 6 --device phonec --out $SUARATB_DATA/work/board_test/dataset6
Keluaran: <out>/clips/<barcode>_c<i>.raw (int16 little-endian, 8240 sampel), <out>/manifest.csv (satu baris per peserta:
barcode,y,device,n_klip,golden_logit,golden_logits,wav) dan <out>/paket/ (salin folder ini ke papan: skrip + klip).
Klip berasal dari processed/clips (detektor golden, sama dengan hardware); --klip klip pertama per peserta (urutan rekaman).
Setelah ini jalankan sw.pynq.laptop.fit_fusi --paket <out>/paket (fusi.json, ambang.txt, kolom gejala).
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

HERE = pathlib.Path(__file__).resolve().parent.parent / "papan"   # skrip papan yang disalin ke paket


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-per-class", type=int, default=50)
    ap.add_argument("--klip", type=int, default=6, help="klip per peserta")
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
    for j, (b, y) in enumerate(zip(pick.barcode, pick.y), 1):
        cl = np.load(paths.processed_dir() / "clips" / a.device / f"{b}.npz", allow_pickle=True)["clips"][:a.klip]
        gs = []
        for i, x in enumerate(cl):
            x = x.astype(np.int16)
            assert x.size == 8240, (b, x.size)
            x.astype("<i2").tofile(out / "clips" / f"{b}_c{i}.raw")
            gs.append(int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), q)[0]))
        rows.append((b, int(y), a.device, len(gs), gs[0], " ".join(map(str, gs)), wav.get((b, a.device), "")))
        if j % 10 == 0:
            print(f"{j}/{len(pick)} peserta", flush=True)
    pd.DataFrame(rows, columns=["barcode", "y", "device", "n_klip", "golden_logit", "golden_logits", "wav"]).to_csv(
        out / "manifest.csv", index=False)
    pk = out / "paket"
    if pk.exists():
        shutil.rmtree(pk)
    (pk).mkdir()
    for f in ("axil_smoke", "axil_batch", "axil_mic", "axil1", "axil2", "mic1", "mic2", "fusi"):
        shutil.copy(HERE / f"{f}.py", pk)
    shutil.copy(HERE / "setup_papan.sh", pk)
    shutil.copy(out / "manifest.csv", pk)
    amb = out.parent / "ambang.json"                  # dari sw.pynq.laptop.calibrate_ambang; dipakai axil_batch.py bila ada
    if amb.exists():
        import json
        (pk / "ambang.txt").write_text(f"{json.load(open(amb))['ambang']}\n")
    shutil.copytree(out / "clips", pk / "clips")
    print(f"{len(rows)} peserta x {a.klip} klip ({int(pick.y.sum())} positif) -> {out}; salin {pk} ke papan")


if __name__ == "__main__":
    main()
