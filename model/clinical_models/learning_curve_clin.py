"""K-30: kurva belajar model gejala klinis (apakah lebih banyak peserta menaikkan AUROC?).

    python -m model.clinical_models.learning_curve_clin [--reps 50]   # -> runs/reports/kurva-belajar-gejala.md
Aturan ditetapkan sebelum angka (docs/vault/keputusan.md K-30). UJI tetap 400 peserta per ulangan, latih pada subset kolam sisa.
"""
from __future__ import annotations
import argparse
import warnings
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from golden import paths
from model.clinical_models import fusion
from model.data import dataset

warnings.filterwarnings("ignore")
SIZES = (200, 400, 800, 1200, 1428)
N_TEST = 400
COLS5 = [1, 2, 8, 9, 14]      # sex, coughdur, ngtsweats, weightloss, bmi (indeks kolom clin_matrix)


def fit_auc(Xtr, ytr, Xte, yte):
    m = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                      LogisticRegression(C=0.3, class_weight="balanced", max_iter=1000)).fit(Xtr, ytr)
    return roc_auc_score(yte, m.decision_function(Xte))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=50)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "kurva-belajar-gejala.md"))
    a = ap.parse_args()
    gm = dataset.load_meta().drop_duplicates("barcode").reset_index(drop=True)
    gm = gm[gm.ground_truth_tb.isin(["pos", "neg"])].reset_index(drop=True)
    y = gm.y.values.astype(int); F = fusion.clin_matrix(gm, gm.barcode.values)
    strat = np.array([f"{a_}_{b}" for a_, b in zip(y, gm.facility_code.astype(str))])
    n = len(y)
    res = {k: {m: [] for m in SIZES} for k in ("14", "5")}
    npos = {m: [] for m in SIZES}
    for r in range(a.reps):
        tr_pool, te = next(StratifiedShuffleSplit(1, test_size=N_TEST, random_state=r).split(F, strat))
        for m in SIZES:
            if m == len(tr_pool):
                sub = tr_pool
            else:
                s2, _ = next(StratifiedShuffleSplit(1, train_size=m, test_size=len(tr_pool) - m, random_state=1000 + r).split(F[tr_pool], strat[tr_pool]))
                sub = tr_pool[s2]
            npos[m].append(int(y[sub].sum()))
            for k, cols in (("14", slice(None)), ("5", COLS5)):
                res[k][m].append(fit_auc(F[sub][:, cols], y[sub], F[te][:, cols], y[te]))
        if (r + 1) % 10 == 0:
            print(f"ulangan {r + 1}/{a.reps}", flush=True)
    A = {k: {m: np.array(v) for m, v in d.items()} for k, d in res.items()}
    def pct(v): return f"{v.mean():.3f} ± {v.std():.3f} [{np.percentile(v, 2.5):.3f}, {np.percentile(v, 97.5):.3f}]"
    o = ["# K-30: kurva belajar model gejala klinis", "",
         f"Zambia {n} peserta berlabel ({int(y.sum())} positif, prevalensi {y.mean():.1%}). {a.reps} ulangan; tiap ulangan UJI tetap {N_TEST} peserta "
         f"(sekitar {N_TEST * y.mean():.0f} positif), latih pada subset acak berstrata dari sisa {n - N_TEST}. Aturan: K-30. "
         "Format: rata-rata ± simpangan [persentil 2,5; 97,5] atas ulangan.", "",
         "| ukuran latih | rata-rata positif latih | 14 kolom: AUROC UJI | 5 gejala (optimistis): AUROC UJI |", "|---|---|---|---|"]
    for m in SIZES:
        o.append(f"| {m} | {np.mean(npos[m]):.0f} | {pct(A['14'][m])} | {pct(A['5'][m])} |")
    o += ["", "## Selisih berpasangan (1.428 - 400)", ""]
    ok_any = False
    for k, nm in (("14", "14 kolom"), ("5", "5 gejala")):
        d = A[k][1428] - A[k][400]
        lo, hi = np.percentile(d, [2.5, 97.5])
        naik = lo > 0 and d.mean() >= 0.01
        ok_any |= (k == "14" and naik)
        o.append(f"- {nm}: Δ = {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}] -> {'MASIH NAIK' if naik else 'DATAR'} menurut kriteria K-30")
    d2 = A["14"][1428] - A["14"][200]
    o += [f"- Pembanding 14 kolom, 1.428 - 200: Δ = {d2.mean():+.3f} [{np.percentile(d2, 2.5):+.3f}, {np.percentile(d2, 97.5):+.3f}]", "",
          f"**Kesimpulan (14 kolom, ukuran utama): kurva {'masih naik' if ok_any else 'datar'} pada rentang 400-1.428 peserta.**", "",
          "Catatan: hasil dalam satu dataset (Zambia); 5 gejala dipilih pada data yang sama (optimistis); bukan kinerja klinis."]
    import pathlib
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    main()
