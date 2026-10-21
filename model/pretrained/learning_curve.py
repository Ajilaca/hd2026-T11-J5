"""K-28: kurva belajar HeAR + LR (Zambia saja): AUROC pada 37 peserta uji yang sama untuk ukuran latih berbeda.

    python -m model.pretrained.learning_curve [--reps 500]     # -> runs/reports/kurva-belajar.md
Aturan: docs/vault/keputusan.md K-28 (ditetapkan sebelum angka).
"""
from __future__ import annotations
import argparse
import pathlib
import warnings
import numpy as np
from sklearn.metrics import roc_auc_score
from golden import paths

warnings.filterwarnings("ignore")
SIZES = (100, 150, 220, 291, 327)
NTEST = 37


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "kurva-belajar.md"))
    a = ap.parse_args()
    from model.evaluation import protocol as P
    from model.pretrained import merge_tbs as M
    from model.pretrained.embed_pretrained import participant_matrix
    u = P.universe(); F = participant_matrix("hear", u); ok = ~np.isnan(F).any(1)
    u = u[ok].reset_index(drop=True); F = F[ok]; y = u.y.values.astype(int); sx = u.sex_m.values; n = len(y)
    acc = {s: np.zeros(n) for s in SIZES}; cnt = np.zeros(n)
    per = {s: [] for s in SIZES}
    for r in range(a.reps):
        rng = np.random.default_rng(1000 + r)
        while True:
            p = rng.permutation(n); te = p[-NTEST:]
            if 0 < y[te].sum() < NTEST and all(0 < y[p[:s]].sum() < s for s in SIZES):
                break
        cnt[te] += 1
        for s in SIZES:
            sc = M.fit_score(F[p[:s]], y[p[:s]], F[te])
            acc[s][te] += sc
            per[s].append(roc_auc_score(y[te], sc))
        if r % 50 == 0:
            print("pembagian", r, flush=True)
    m = cnt > 0
    avg = {s: acc[s][m] / cnt[m] for s in SIZES}
    st = {s: P.auc_strat(y[m], avg[s], sx[m]) for s in SIZES}
    raw = {s: roc_auc_score(y[m], avg[s]) for s in SIZES}
    lo, hi = M.boot_delta(y[m], [avg[327]], [avg[291]], sx[m])
    o = ["# K-28: kurva belajar HeAR + LR (Zambia saja), uji pada peserta yang sama", "",
         f"{n} peserta ({int(y.sum())} positif); {a.reps} pembagian acak; uji = {NTEST} peserta terakhir tiap pembagian (sama untuk semua ukuran); "
         f"tiap peserta diuji rata-rata {cnt[m].mean():.0f} kali. Aturan: K-28.", "",
         "| peserta latih | AUROC mentah | AUROC strat. jenis kelamin | per pembagian: rata-rata ± simpangan [2,5; 97,5] |", "|---|---|---|---|"]
    for s in SIZES:
        v = np.array(per[s])
        o.append(f"| {s} | {raw[s]:.3f} | **{st[s]:.3f}** | {v.mean():.3f} ± {v.std():.3f} [{np.percentile(v, 2.5):.2f}, {np.percentile(v, 97.5):.2f}] |")
    d = st[327] - st[291]
    o += ["", f"- Δ strat. (327 - 291) = {d:+.3f}, CI 95% bootstrap berpasangan [{lo:+.3f}, {hi:+.3f}]",
          f"- **Kriteria K-28: 327 {'LEBIH BAIK' if lo > 0 else 'TIDAK terbukti lebih baik'} dari 291** (butuh batas bawah CI > 0)", "",
          "Catatan: HeAR + LR (bukan murid CNN di FPGA); data kecil (60 positif). Bukan kinerja klinis dan bukan diagnosis.", ""]
    path = pathlib.Path(a.out); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    main()
