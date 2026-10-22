"""Latih fusi gejala klinis + logit audio untuk papan (jalankan di laptop, dari ROOT repo, dengan .venv).

    python -m sw.pynq.laptop.fit_fusi [--paket $SUARATB_DATA/work/board_test/dataset6/paket] [--klip 6] [--sens 0.90]
Gejala (5, dipilih dari analisis 1.828 peserta Zambia): lama batuk (0-4), BMI, jenis kelamin (L=1), penurunan berat badan (y/t),
keringat malam (y/t). Tahap 1: skor klinis = regresi logistik pada peserta TANPA audio (tidak tumpang tindih dengan klip uji).
Tahap 2: fusi = regresi logistik [skor klinis, logit audio/1000] pada peserta berlaudio (klip ponsel C):
  axil: rata-rata logit --klip klip pertama (sama dengan klip di paket); koefisien out-of-fold 5 lipatan, lipatan tiap peserta
        ditulis di manifest. ambang.txt = ambang audio saja untuk rata-rata --klip klip (sensitivitas --sens).
  mic : rata-rata logit 10 klip (seperti mode sesi); koefisien dari semua peserta berlaudio (untuk orang baru).
Ambang = sensitivitas --sens pada skor out-of-fold (dipilih pada data yang sama: OPTIMISTIS). Keluaran ke --paket:
fusi.json dan manifest.csv ditambah kolom fold,coughdur,bmi,sex,weightloss,ngtsweats. Alat triase, bukan diagnosis.
"""
import argparse
import json
import pathlib

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from golden import paths
from model.clinical_models.fusion import DUR
from model.data import dataset

FEAT = ["coughdur", "bmi", "sex", "weightloss", "ngtsweats"]
BT = paths.data_root() / "work" / "board_test"


def clin_x(d: pd.DataFrame) -> np.ndarray:
    yes = lambda c: (d[c].astype(str).str.lower() == "yes").astype(float).values  # noqa: E731
    return np.column_stack([d.coughdur.map(DUR).astype(float).values, d.bmi.astype(float).values,
                            (d.sex.astype(str).str.lower() == "m").astype(float).values, yes("weightloss"), yes("ngtsweats")])


def lr_raw(X: np.ndarray, y: np.ndarray, C: float = 0.3) -> tuple[list[float], float]:
    """LR pada fitur terstandar, dikembalikan sebagai bobot pada satuan mentah (w.x + b)."""
    mu, sd = X.mean(0), X.std(0) + 1e-9
    m = LogisticRegression(C=C, max_iter=2000).fit((X - mu) / sd, y)
    w = m.coef_[0] / sd
    return w.tolist(), float(m.intercept_[0] - (w * mu).sum())


def thr_at(s: np.ndarray, y: np.ndarray, sens: float) -> tuple[float, float, float]:
    t = float(np.percentile(s[y == 1], 100 * (1 - sens)))
    return t, float((s[y == 1] >= t).mean()), float((s[y == 0] < t).mean())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paket", default=str(BT / "dataset6" / "paket"))
    ap.add_argument("--klip", type=int, default=6)
    ap.add_argument("--sens", type=float, default=0.90)
    a = ap.parse_args()
    pk = pathlib.Path(a.paket)

    gm = dataset.load_meta().drop_duplicates("barcode")
    gm = gm[gm.ground_truth_tb.isin(["pos", "neg"])].set_index("barcode")
    gm["bmi"] = gm.bmi.astype(float).fillna(gm.bmi.astype(float).median())
    l1 = pd.read_csv(BT / "all_logits_phonec.csv").set_index("barcode")
    lc = pd.read_csv(BT / "logits_10clip_phonec.csv")
    l10 = lc.groupby("barcode").logit.mean()
    lk = lc[lc["clip"] < a.klip].groupby("barcode").logit.mean()
    aud = [b for b in l1.index if b in gm.index]
    rest = gm.drop(index=aud)

    wc, bc = lr_raw(clin_x(rest), rest.y.values.astype(int))
    A = gm.loc[aud]; y = A.y.values.astype(int)
    clin = clin_x(A) @ np.array(wc) + bc
    a1 = lk.reindex(aud).values / 1000.0
    a10 = l10.reindex(aud).values / 1000.0
    rep = {"n_klinis_latih": int(len(rest)), "n_audio": int(len(aud)), "n_audio_pos": int(y.sum())}

    # axil: OOF per lipatan
    fold = np.zeros(len(aud), int); s_ax = np.zeros(len(aud)); folds = {}
    for k, (tr, te) in enumerate(StratifiedKFold(5, shuffle=True, random_state=0).split(a1, y)):
        w, b = lr_raw(np.column_stack([clin[tr], a1[tr]]), y[tr], C=1.0)
        folds[str(k)] = [b, *w]; fold[te] = k
        s_ax[te] = b + w[0] * clin[te] + w[1] * a1[te]
    t_ax = thr_at(s_ax, y, a.sens)
    # mic: OOF untuk ambang, koefisien akhir dari semua
    ok = ~np.isnan(a10); s_mic = np.full(len(aud), np.nan)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(a10[ok], y[ok]):
        idx_tr, idx_te = np.where(ok)[0][tr], np.where(ok)[0][te]
        w, b = lr_raw(np.column_stack([clin[idx_tr], a10[idx_tr]]), y[idx_tr], C=1.0)
        s_mic[idx_te] = b + w[0] * clin[idx_te] + w[1] * a10[idx_te]
    w, b = lr_raw(np.column_stack([clin[ok], a10[ok]]), y[ok], C=1.0)
    t_mic = thr_at(s_mic[ok], y[ok], a.sens)
    t_cl = thr_at(clin, y, a.sens)
    t_au = thr_at(a1 * 1000.0, y, a.sens)

    auc = lambda s, m=slice(None): round(float(roc_auc_score(y[m], s[m])), 3)  # noqa: E731
    rep.update(klip_axil=a.klip, auroc_audio_axil=auc(a1), auroc_audio_10klip=auc(a10, ok), auroc_klinis=auc(clin),
               auroc_fusi_axil_oof=auc(s_ax), auroc_fusi_mic_oof=auc(s_mic, ok))
    out = {"fitur": FEAT, "lama_batuk": DUR, "klinis": {"w": wc, "b": bc, "ambang": t_cl[0], "sens": t_cl[1], "spes": t_cl[2]},
           "audio_axil": {"ambang": t_au[0], "sens": t_au[1], "spes": t_au[2]},
           "axil": {"folds": folds, "ambang": t_ax[0], "sens": t_ax[1], "spes": t_ax[2]},
           "mic": {"coef": [b, *w], "ambang": t_mic[0], "sens": t_mic[1], "spes": t_mic[2]},
           "laporan": rep, "catatan": "ambang pada data yang sama (optimistis); mic belum dikalibrasi untuk INMP441; bukan diagnosis"}
    (pk / "fusi.json").write_text(json.dumps(out, indent=1))
    (pk / "ambang.txt").write_text(f"{int(np.floor(t_au[0]))}\n")

    man = pd.read_csv(pk / "manifest.csv")
    man = man[[c for c in man.columns if c not in ["fold", *FEAT]]]
    fmap = dict(zip(aud, fold))
    d = gm.loc[man.barcode]
    man["fold"] = [fmap[b] for b in man.barcode]
    man["coughdur"] = d.coughdur.map(DUR).astype(int).values
    man["bmi"] = d.bmi.round(1).values
    man["sex"] = (d.sex.astype(str).str.lower() == "m").astype(int).values
    man["weightloss"] = (d.weightloss.astype(str).str.lower() == "yes").astype(int).values
    man["ngtsweats"] = (d.ngtsweats.astype(str).str.lower() == "yes").astype(int).values
    man.to_csv(pk / "manifest.csv", index=False)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
