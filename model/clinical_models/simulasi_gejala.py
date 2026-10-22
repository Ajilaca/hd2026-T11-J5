"""K-31: SIMULASI data gejala sintetis (5.000 dan 10.000) untuk ilustrasi. BUKAN bukti klinis.

    python -m model.clinical_models.simulasi_gejala [--reps 30]   # -> runs/reports/simulasi-gejala.md
Generator = LR 14 kolom pada data Zambia asli; label sintetis ~ Bernoulli(p generator), jadi batas atas AUROC = AUROC generator.
Aturan di docs/vault/keputusan.md K-31 (ditetapkan sebelum angka).
"""
from __future__ import annotations
import argparse
import pathlib
import warnings
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from golden import paths
from model.clinical_models import fusion
from model.data import dataset

warnings.filterwarnings("ignore")
SIZES = (400, 1428, 5000, 10000)
N_TEST, N_CEIL = 20000, 200000


def pipe(balanced: bool):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                         LogisticRegression(C=0.3, class_weight="balanced" if balanced else None, max_iter=2000))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "simulasi-gejala.md"))
    a = ap.parse_args()
    gm = dataset.load_meta().drop_duplicates("barcode").reset_index(drop=True)
    gm = gm[gm.ground_truth_tb.isin(["pos", "neg"])].reset_index(drop=True)
    y0 = gm.y.values.astype(int); F = fusion.clin_matrix(gm, gm.barcode.values); n = len(y0); prev = y0.mean()
    gen = pipe(False).fit(F, y0); p = gen.predict_proba(F)[:, 1]
    rng = np.random.default_rng(0)
    idx = rng.integers(0, n, N_CEIL); yc = rng.random(N_CEIL) < p[idx]
    ceil = roc_auc_score(yc, p[idx])
    def draw(N, rng, control=False):
        i = rng.integers(0, n, N)
        return F[i], (rng.random(N) < (prev if control else p[i])).astype(int)
    out = {c: {m: [] for m in SIZES} for c in ("sim", "kontrol")}
    for r in range(a.reps):
        rr = np.random.default_rng(100 + r)
        Xte, yte = draw(N_TEST, rr); Xtc, ytc = draw(N_TEST, rr, True)
        for m in SIZES:
            Xtr, ytr = draw(m, rr); out["sim"][m].append(roc_auc_score(yte, pipe(True).fit(Xtr, ytr).decision_function(Xte)))
            Xtr, ytr = draw(m, rr, True); out["kontrol"][m].append(roc_auc_score(ytc, pipe(True).fit(Xtr, ytr).decision_function(Xtc)))
        if (r + 1) % 10 == 0:
            print(f"ulangan {r + 1}/{a.reps}", flush=True)
    def pct(v): v = np.array(v); return f"{v.mean():.3f} ± {v.std():.3f} [{np.percentile(v, 2.5):.3f}, {np.percentile(v, 97.5):.3f}]"
    o = ["# K-31: SIMULASI data gejala sintetis (ilustrasi, BUKAN bukti klinis)", "",
         f"Generator: LR 14 kolom pada {n} peserta Zambia ({int(y0.sum())} positif). Peserta sintetis = baris fitur asli diambil acak dengan pengembalian; "
         f"label ~ Bernoulli(p generator). **Batas atas AUROC (generator, 200.000 baris) = {ceil:.3f}**: model tidak mungkin melampauinya. "
         f"{a.reps} ulangan; UJI sintetis {N_TEST} baris per ulangan. Aturan: K-31.", "",
         "| ukuran latih | SIMULASI: AUROC UJI | kontrol label acak |", "|---|---|---|"]
    o += [f"| {m} | {pct(out['sim'][m])} | {pct(out['kontrol'][m])} |" for m in SIZES]
    o += ["", f"Jarak ke batas atas ({ceil:.3f}): " + ", ".join(f"{m}: {ceil - np.mean(out['sim'][m]):+.3f}" for m in SIZES), "",
          "Tafsir: hasil melingkar karena label dibuat dari generator; hanya menunjukkan seberapa cepat penaksir mendekati batas atas yang ditentukan generator. "
          "Kontrol label acak mendekati 0,5. Semua angka SIMULASI, tidak boleh dikutip sebagai kinerja deteksi TBC."]
    pth = pathlib.Path(a.out); pth.parent.mkdir(parents=True, exist_ok=True); pth.write_text("\n".join(o) + "\n"); print("\n".join(o))


if __name__ == "__main__":
    main()
