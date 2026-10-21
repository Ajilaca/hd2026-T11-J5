"""Ambang SEMENTARA untuk kolom risiko (jalankan di laptop, dari ROOT repo, dengan .venv).

    python -m sw.pynq.calibrate_ambang --device phonec --sens 0.90
Logit golden (qmodel yang sama dengan ROM bitstream) dihitung untuk klip pertama tiap peserta; ambang = logit terendah yang masih
meloloskan --sens dari peserta positif (persentil ke-(1-sens) logit positif). Keluaran: all_logits.csv dan ambang.json.
BATAS KLAIM: ambang dipilih pada data yang sama dengan evaluasi dan model akhir mungkin pernah melihat peserta ini, jadi
sensitivitas/spesifisitas yang tercetak OPTIMISTIS. Model audio lemah (AUROC ~0,65); ini bukan diagnosis dan bukan estimasi akurasi.
"""
import argparse
import json
import pathlib

import numpy as np
import pandas as pd

from golden import paths
from golden.blocks import cnn as C
from golden.blocks import frontend as F


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="phonec", choices=["phonea", "phoneb", "phonec", "recorder"])
    ap.add_argument("--sens", type=float, default=0.90)
    ap.add_argument("--qmodel", default=str(paths.runs_dir() / "model_distill" / "qmodel.npz"))
    ap.add_argument("--out", default=str(paths.data_root() / "work" / "board_test"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sp = pd.read_csv(paths.processed_dir() / "splits_v2.csv")[["barcode", "y"]].drop_duplicates("barcode")
    clipdir = paths.processed_dir() / "clips" / a.device
    have = {p.stem for p in clipdir.glob("*.npz")}
    sp = sp[sp.barcode.isin(have)].reset_index(drop=True)
    q = C.load_qmodel(a.qmodel)
    cache = out / f"all_logits_{a.device}.csv"
    done = pd.read_csv(cache) if cache.exists() else pd.DataFrame(columns=["barcode", "y", "logit"])
    got = set(done.barcode)
    rows = done.values.tolist()
    for i, (b, y) in enumerate(zip(sp.barcode, sp.y)):
        if b in got:
            continue
        x = np.load(clipdir / f"{b}.npz", allow_pickle=True)["clips"][0].astype(np.int64)
        rows.append([b, int(y), int(C.cnn_forward(F.to_cnn_input(F.features_q(x)), q)[0])])
        if len(rows) % 25 == 0:
            pd.DataFrame(rows, columns=["barcode", "y", "logit"]).to_csv(cache, index=False)
            print(f"{len(rows)}/{len(sp)}", flush=True)
    df = pd.DataFrame(rows, columns=["barcode", "y", "logit"])
    df.to_csv(cache, index=False)
    pos, neg = df[df.y == 1].logit.values, df[df.y == 0].logit.values
    thr = int(np.floor(np.percentile(pos, 100 * (1 - a.sens))))
    sens = float((pos >= thr).mean())
    spec = float((neg < thr).mean())
    res = dict(device=a.device, n=len(df), n_pos=int(len(pos)), n_neg=int(len(neg)), target_sens=a.sens, ambang=thr,
               sens=round(sens, 3), spes=round(spec, 3), catatan="optimistis; model lemah; bukan diagnosis")
    (out / "ambang.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
