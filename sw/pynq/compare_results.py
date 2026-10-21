"""Bandingkan hasil papan dengan golden (jalankan di laptop, dengan .venv).

    python -m sw.pynq.compare_results <out>/manifest.csv hasil.csv
Mencetak: jumlah klip, kecocokan bit-exact dengan golden, dan AUROC logit papan (identik dengan golden bila semua cocok).
"""
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def main(man: str, res: str) -> int:
    m = pd.read_csv(man).merge(pd.read_csv(res), left_on="barcode", right_on="nama", how="left")
    miss = int(m.logit.isna().sum())
    m = m.dropna(subset=["logit"])
    same = (m.logit.astype(int) == m.golden_logit)
    print(f"klip dikirim {len(m) + miss}, ada hasil {len(m)}, tanpa hasil {miss}")
    print(f"logit papan = golden: {int(same.sum())}/{len(m)}" + ("" if same.all() else "  <-- ADA YANG BEDA"))
    if not same.all():
        print(m.loc[~same, ["barcode", "y", "logit", "golden_logit"]].head(10).to_string(index=False))
    print(f"frames != 50: {int((m.frames != 50).sum())}; nsat > 0: {int((m.nsat > 0).sum())}")
    if m.y.nunique() == 2:
        print(f"AUROC logit papan {roc_auc_score(m.y, m.logit):.3f} (n={len(m)}, {int(m.y.sum())} positif); "
              f"golden {roc_auc_score(m.y, m.golden_logit):.3f}. Sampel kecil dan satu klip per peserta: bukan estimasi akurasi.")
    return 0 if same.all() and not miss else 2


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
