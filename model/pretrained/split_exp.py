"""K-27: latih pada 327 peserta ACAK Zambia (+ 110 subjek ACAK TBscreen), uji pada sisanya; diulang untuk banyak pembagian acak.

    python -m model.pretrained.split_exp [--reps 500] [--null 20] [--null-splits 100]   # -> runs/reports/split-327-110.md

Aturan ditetapkan sebelum angka (docs/vault/keputusan.md K-27). Model: embedding HeAR + LR (wakil murid CNN yang didistilasi dari HeAR).
Lengan: Z = latih Zambia saja; G = Zambia + TBscreen (bobot sel dataset x label sama); T = TBscreen saja.
"""
from __future__ import annotations
import argparse
import pathlib
import warnings
import numpy as np
from sklearn.metrics import roc_auc_score
from golden import paths

warnings.filterwarnings("ignore")
ARMS = ("Z", "G", "T")


def draw(rng, nz, nt, yz, yt, ntz, ntt):
    """Satu pembagian acak sederhana; diundi ulang bila uji kehilangan salah satu kelas."""
    while True:
        iz, it = rng.permutation(nz), rng.permutation(nt)
        tz, ez, tt, et = iz[:ntz], iz[ntz:], it[:ntt], it[ntt:]
        if 0 < yz[ez].sum() < len(ez) and 0 < yt[et].sum() < len(et) and 0 < yz[tz].sum() < len(tz) and 0 < yt[tt].sum() < len(tt):
            return tz, ez, tt, et


def fit_arms(M, Fz, yz, Ft, yt, tz, ez, tt, et):
    """Skor uji tiap lengan: dict arm -> (skor Zambia uji, skor TBscreen uji)."""
    Xte = np.vstack([Fz[ez], Ft[et]]); n = len(ez)
    out = {}
    s = M.fit_score(Fz[tz], yz[tz], Xte); out["Z"] = (s[:n], s[n:])
    X = np.vstack([Fz[tz], Ft[tt]]); y = np.r_[yz[tz], yt[tt]]
    ds = np.r_[np.zeros(len(tz), int), np.ones(len(tt), int)]
    s = M.fit_score(X, y, Xte, M.weights(ds, y)); out["G"] = (s[:n], s[n:])
    s = M.fit_score(Ft[tt], yt[tt], Xte); out["T"] = (s[:n], s[n:])
    return out


def run(M, P, Fz, yz, sx, Ft, yt, reps, ntz, ntt, seed0, arms=ARMS):
    nz, nt = len(yz), len(yt)
    acc = {a: np.zeros(nz) for a in arms}; cnt = np.zeros(nz)
    per = {a: {"zam": [], "zam_st": [], "tbs": []} for a in arms}
    for r in range(reps):
        rng = np.random.default_rng(seed0 + r)
        tz, ez, tt, et = draw(rng, nz, nt, yz, yt, ntz, ntt)
        sc = fit_arms(M, Fz, yz, Ft, yt, tz, ez, tt, et)
        cnt[ez] += 1
        for a in arms:
            sz, st = sc[a]
            acc[a][ez] += sz
            per[a]["zam"].append(roc_auc_score(yz[ez], sz))
            per[a]["tbs"].append(roc_auc_score(yt[et], st))
            try:
                per[a]["zam_st"].append(P.auc_strat(yz[ez], sz, sx[ez]))
            except ZeroDivisionError:
                per[a]["zam_st"].append(np.nan)
    seen = cnt > 0
    avg = {a: np.where(seen, acc[a] / np.maximum(cnt, 1), np.nan) for a in arms}
    return avg, cnt, per


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--ntrain-z", type=int, default=327)
    ap.add_argument("--ntrain-t", type=int, default=110)
    ap.add_argument("--null", type=int, default=20)
    ap.add_argument("--null-splits", type=int, default=100)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "split-327-110.md"))
    a = ap.parse_args()
    from model.evaluation import protocol as P
    from model.pretrained import merge_tbs as M
    from model.pretrained.embed_pretrained import participant_matrix
    u = P.universe(); Fz = participant_matrix("hear", u); ok = ~np.isnan(Fz).any(1)
    uz = u[ok].reset_index(drop=True); Fz = Fz[ok]; yz = uz.y.values.astype(int); sx = uz.sex_m.values
    Ft, t = M.tbs_participants(); yt = t.y.values.astype(int)
    nz, nt = len(yz), len(yt)
    ntz, ntt = a.ntrain_z, a.ntrain_t
    print(f"Zambia {nz} ({yz.sum()} +), TBscreen {nt} ({yt.sum()} TB); latih {ntz}+{ntt}, uji {nz - ntz}+{nt - ntt}", flush=True)

    avg, cnt, per = run(M, P, Fz, yz, sx, Ft, yt, a.reps, ntz, ntt, 1000)
    print("utama selesai; peserta tak pernah diuji:", int((cnt == 0).sum()), flush=True)
    m = cnt > 0
    st = {k: P.auc_strat(yz[m], avg[k][m], sx[m]) for k in ARMS}
    raw = {k: roc_auc_score(yz[m], avg[k][m]) for k in ARMS}
    d_lo, d_hi = M.boot_delta(yz[m], [avg["G"][m]], [avg["Z"][m]], sx[m])

    # nol: label latih diacak dalam klinik x jenis kelamin (Zambia) dan cohort x jenis kelamin (TBscreen)
    nulz = {k: [] for k in ("Z", "G")}
    gz = (uz.fac + uz.sex_m.astype(str)).values; gt = (t.cohort + t.sex_m.astype(str)).values
    for i in range(a.null):
        rng = np.random.default_rng(7000 + i)
        pz, pt = yz.copy(), yt.copy()
        for g in np.unique(gz):
            j = np.where(gz == g)[0]; pz[j] = rng.permutation(yz[j])
        for g in np.unique(gt):
            j = np.where(gt == g)[0]; pt[j] = rng.permutation(yt[j])
        av, ct, _ = run(M, P, Fz, pz, sx, Ft, pt, a.null_splits, ntz, ntt, 9000 + 1000 * i, arms=("Z", "G"))
        mm = ct > 0
        for k in ("Z", "G"):
            nulz[k].append(P.auc_strat(pz[mm], av[k][mm], sx[mm]))
        print(f"nol {i}: Z {nulz['Z'][-1]:.3f} G {nulz['G'][-1]:.3f}", flush=True)
    p95 = {k: float(np.percentile(nulz[k], 95)) for k in nulz}
    ok_main = (d_lo > 0) and (st["G"] > p95["G"])

    def dist(v):
        v = np.array(v, float); v = v[~np.isnan(v)]
        return f"{v.mean():.3f} ± {v.std():.3f} [{np.percentile(v, 2.5):.2f}, {np.percentile(v, 97.5):.2f}]"
    nuj = nz - ntz
    o = ["# K-27: pembagian acak 327 Zambia + 110 TBscreen, uji pada sisanya (HeAR + LR)", "",
         f"Zambia {nz} peserta ({int(yz.sum())} positif), TBscreen {nt} subjek ({int(yt.sum())} TB; cohort A {int((t.cohort == 'A').sum())}, "
         f"C {int((t.cohort == 'C').sum())}). Latih {ntz} Zambia + {ntt} TBscreen, uji {nuj} Zambia + {nt - ntt} TBscreen. "
         f"{a.reps} pembagian acak (seed 1000+r); tiap peserta Zambia diuji rata-rata {cnt[m].mean():.0f} kali. Aturan: K-27.", "",
         "Lengan: **Z** = latih Zambia saja (baseline model sekarang pada pembagian yang sama); **G** = Zambia + TBscreen (berbobot); "
         "**T** = TBscreen saja.", "",
         "## Ukuran utama: peserta Zambia yang diuji (skor dirata-rata atas pembagian)", "",
         "| lengan | AUROC mentah | AUROC strat. jenis kelamin |", "|---|---|---|"]
    for k, nm in (("Z", "Z: 327 Zambia"), ("G", "G: 327 Zambia + 110 TBscreen"), ("T", "T: 110 TBscreen saja")):
        o.append(f"| {nm} | {raw[k]:.3f} | {st[k]:.3f} |")
    o += ["", f"- Δ strat. (G - Z) = {st['G'] - st['Z']:+.3f}, CI 95% bootstrap berpasangan [{d_lo:+.3f}, {d_hi:+.3f}]",
          f"- Nol permutasi ({a.null} x {a.null_splits} pembagian): lengan Z p95 {p95['Z']:.3f} (maks {max(nulz['Z']):.3f}), "
          f"lengan G p95 {p95['G']:.3f} (maks {max(nulz['G']):.3f})",
          f"- **Kriteria K-27: {'BERHASIL' if ok_main else 'TIDAK BERHASIL'}** (butuh batas bawah CI Δ > 0 dan G > p95 nol G)", "",
          "## Sebaran per pembagian (satu pembagian saja sangat derau)", "",
          f"Uji Zambia: {nuj} peserta; uji TBscreen: {nt - ntt} subjek. Format: rata-rata ± simpangan [persentil 2,5, 97,5] atas {a.reps} pembagian.", "",
          "| lengan | Zambia mentah | Zambia strat. | TBscreen mentah (tercampur cohort) |", "|---|---|---|---|"]
    for k in ARMS:
        o.append(f"| {k} | {dist(per[k]['zam'])} | {dist(per[k]['zam_st'])} | {dist(per[k]['tbs'])} |")
    o += ["", "## Pembanding yang sudah ada (bukan dari percobaan ini)", "",
          "| model | AUROC strat. | sumber |", "|---|---|---|",
          "| HeAR guru, CV E0 (364 peserta, tanpa TBscreen) | 0,672 | distill_run2.log |",
          "| Murid CNN int8 di FPGA (distilasi), CV | 0,654 | distill_run2.log |",
          "| Gabungan Zambia + TBscreen, CV E0 (K-25) | lihat gabungan-tbscreen.md | K-25 |", "",
          "Catatan: AUROC mentah tercampur jenis kelamin; TBscreen tercampur cohort (cohort C seluruhnya NTB). Murid CNN tidak dilatih ulang per "
          "pembagian. Bukan kinerja klinis dan bukan diagnosis.", ""]
    path = pathlib.Path(a.out); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    main()
