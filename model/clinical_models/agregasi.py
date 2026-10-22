"""K-33: cara agregasi logit klip menjadi skor peserta (median, terpangkas, top-50%, buang klip buruk).

    python -m model.clinical_models.agregasi    # -> runs/reports/agregasi-logit.md (butuh cache K-32 logits_all_devices.csv)
Aturan ditetapkan sebelum angka: docs/vault/keputusan.md K-33.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from golden import paths
from model.data import dataset
from model.clinical_models.multi_device import BT, CACHE, boot_delta, fuse_oof
from sw.pynq.laptop.fit_fusi import clin_x, lr_raw

warnings.filterwarnings("ignore")
K = 10


def quality(aud):
    rows = []
    for b in aud:
        cl = np.load(paths.processed_dir() / "clips" / "phonec" / f"{b}.npz", allow_pickle=True)["clips"][:K]
        for i, x in enumerate(cl):
            x = x.astype(np.int64)
            rows.append((b, i, float(np.mean(np.abs(x) >= 32000)), float(np.sqrt(np.mean(x * x)))))
    return pd.DataFrame(rows, columns=["barcode", "clip", "clipfrac", "rms"])


def agg_all(g: pd.DataFrame) -> dict:
    v = np.sort(g.logit.values.astype(float)); n = len(v); t = int(np.floor(0.2 * n))
    good = g[(g.clipfrac <= 0.001) & (g.rms > g.rms.quantile(0.2))]
    if len(good) == 0:
        good = g
    return {"rata-rata (acuan)": v.mean(), "median": np.median(v), "terpangkas 20%": v[t:n - t].mean() if n - 2 * t > 0 else v.mean(),
            "50% tertinggi": v[n - max(1, n // 2):].mean(), "buang klip buruk": good.logit.mean()}


def main():
    gm = dataset.load_meta().drop_duplicates("barcode")
    gm = gm[gm.ground_truth_tb.isin(["pos", "neg"])].set_index("barcode")
    gm["bmi"] = gm.bmi.astype(float).fillna(gm.bmi.astype(float).median())
    aud = [b for b in pd.read_csv(BT / "all_logits_phonec.csv").barcode if b in gm.index]
    y = gm.loc[aud].y.values.astype(int)
    rest = gm.drop(index=aud); wc, bc = lr_raw(clin_x(rest), rest.y.values.astype(int))
    clin = clin_x(gm.loc[aud]) @ np.array(wc) + bc
    df = pd.read_csv(CACHE)
    df = df[(df.device == "phonec") & (df["clip"] < K)]
    df = df.merge(quality(aud), on=["barcode", "clip"])
    per = {b: agg_all(g) for b, g in df.groupby("barcode")}
    names = list(next(iter(per.values())))
    S = {k: np.array([per[b][k] for b in aud]) / 1000.0 for k in names}
    ref = names[0]
    dropped = 1 - df[(df.clipfrac <= 0.001)].shape[0] / len(df)
    o = ["# K-33: cara agregasi logit per peserta", "",
         f"349 peserta ({int(y.sum())} positif), ponsel C, 10 klip pertama ({len(df)} klip; {dropped:.1%} klip terpotong). Aturan: K-33.", "",
         "| agregasi | AUROC audio | Δ vs rata-rata [CI 95%] | AUROC fusi (OOF) |", "|---|---|---|---|"]
    for k in names:
        au = roc_auc_score(y, S[k]); fu = roc_auc_score(y, fuse_oof(clin, S[k], y))
        if k == ref:
            dl = "acuan"
        else:
            lo, hi = boot_delta(y, S[k], S[ref]); dl = f"{au - roc_auc_score(y, S[ref]):+.3f} [{lo:+.3f}, {hi:+.3f}]" + (" LEBIH BAIK" if lo > 0 else "")
        o.append(f"| {k} | {au:.3f} | {dl} | {fu:.3f} |")
    o += ["", "Catatan: empat varian dibandingkan dengan acuan; hasil tipis dibaca hati-hati. Bukan kinerja klinis."]
    p = paths.runs_dir() / "reports" / "agregasi-logit.md"; p.write_text("\n".join(o) + "\n"); print("\n".join(o))


if __name__ == "__main__":
    main()
