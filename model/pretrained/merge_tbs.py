"""K-25: gabungan Zambia + TBscreen (batuk pasif) dengan embedding HeAR + LR; ukuran utama pada peserta Zambia yang ditahan.

    python -m model.pretrained.merge_tbs hear                      # -> features/emb_hear_tbs.npz
    python -m model.pretrained.merge_tbs eval [--perm 40] [--reps 10]   # -> runs/reports/gabungan-tbscreen.md
    python -m model.pretrained.merge_tbs xfer [--perm 200]            # K-26 (4) -> runs/reports/tbscreen-ke-zambia.md

Aturan ditetapkan sebelum angka (docs/vault/keputusan.md K-25):
  - Lengan Z = latih Zambia saja; lengan G = latih Zambia + TBscreen, bobot sampel membuat tiap sel dataset x label berbobot
    total sama. Lipatan Zambia = protokol E0; TBscreen 5 lipatan per ulangan (stratifikasi label x cohort).
  - Ukuran utama: AUROC strat. jenis kelamin pada peserta Zambia yang ditahan. Berhasil bila batas bawah CI 95% bootstrap
    berpasangan untuk Δ = G - Z > 0 DAN AUROC G > p95 nol permutasi.
  - AUROC gabungan selalu disandingkan dengan AUROC "asal dataset saja" pada peserta yang sama.
TBscreen: satu perangkat per subjek (pixel, codec, yeti), maks. 6 klip paling keras (tanpa label), resep HeAR sama dengan Zambia
(jendela 2 s mulai 0,25 s sebelum onset; klip 1 s diberi nol). Kolom cohort/class/lab/CXR tidak dipakai sebagai fitur.
"""
from __future__ import annotations
import argparse
import os
import pathlib
import warnings
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from golden import paths

warnings.filterwarnings("ignore")
TBS = paths.data_root() / "raw_tbscreen" / "TBscreen_Dataset" / "Passive_coughs"
PREF = ("pixel", "codec", "yeti")


def tbs_meta() -> pd.DataFrame:
    """Klip pasif TBscreen berlabel TB/NTB yang punya WAV."""
    d = pd.read_csv(TBS / "Passive_coughs.csv", low_memory=False)
    have = set(os.listdir(TBS / "Audio_files"))
    d = d[d.path.map(lambda p: p + ".wav" in have) & d.Label.isin(["TB", "NTB"])].copy()
    d["y"] = (d.Label == "TB").astype(int)
    d["sex_m"] = (d.gndr_a == 0).astype(int)          # konvensi model/data/tbscreen.py
    return d


def extract_hear(max_clips: int = 6, threads: int = 6):
    os.environ.setdefault("HF_HOME", str(paths.data_root() / "hf"))   # sebelum import: huggingface_hub membacanya saat import
    import importlib.util
    import torch
    from transformers import AutoModel
    from golden import params
    from golden.blocks.cough_det import hop_energy
    from golden.blocks.preemph import preemph
    from model.data.audio_io import load_16k
    spec = importlib.util.spec_from_file_location("au", str(paths.data_root() / "ext/hear/python/data_processing/audio_utils.py"))
    au = importlib.util.module_from_spec(spec); spec.loader.exec_module(au)
    # HF_HOME sudah diset di awal fungsi
    torch.set_num_threads(threads)
    m = AutoModel.from_pretrained("google/hear-pytorch").eval()
    d = tbs_meta()
    rows, embs = [], []
    subs = sorted(d.subject.unique())
    for n, s in enumerate(subs):
        g = d[d.subject == s]
        dev = next(v for v in PREF if (g.device == v).any())
        cands = []
        for p in g[g.device == dev].path:
            x = load_16k(str(TBS / "Audio_files" / (p + ".wav"))).astype(np.int64)
            E = hop_energy(preemph(np.pad(x, (0, max(0, params.FRAME_LEN - len(x))))))
            if E.max() <= 0:
                continue
            on = int(np.argmax(E > E.max() / 16))           # onset seperti model/data/tbscreen.py
            cands.append((float(E[on:on + 12].max()), p, x, max(on * params.HOP - 4000, 0)))
        cands.sort(key=lambda t: -t[0])
        for _, p, x, s0 in cands[:max_clips]:
            w = x[s0:s0 + 32000].astype(np.float32) / 32768.0
            w = np.pad(w, (0, 32000 - len(w)))
            with torch.no_grad():
                o = m(au.preprocess_audio(torch.tensor(w)[None]), return_dict=True).pooler_output[0].numpy()
            embs.append(o); rows.append((p, s, dev))
        if n % 20 == 0:
            print("hear tbs", n, len(subs), len(embs), flush=True)
    r = pd.DataFrame(rows, columns=["path", "barcode", "device"])
    np.savez(paths.features_dir() / "emb_hear_tbs.npz", emb=np.stack(embs), path=r.path.values,
             barcode=r.barcode.values, device=r.device.values)
    print("selesai:", len(embs), "klip,", r.barcode.nunique(), "subjek", flush=True)


def tbs_participants():
    z = np.load(paths.features_dir() / "emb_hear_tbs.npz", allow_pickle=True)
    e = pd.DataFrame(z["emb"]); e["b"] = z["barcode"]
    F = e.groupby("b").mean()
    m = tbs_meta().drop_duplicates("subject").set_index("subject").loc[F.index]
    t = pd.DataFrame(dict(barcode=F.index.values, y=m.y.values, sex_m=m.sex_m.values, cohort=m.cohort.astype(str).values,
                          age=m.age.astype(float).values))
    t["strat"] = t.y.astype(str) + "_" + t.cohort
    return F.values, t


def weights(ds: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Tiap sel dataset x label berbobot total sama."""
    w = np.zeros(len(y))
    cells = [(a, b) for a in np.unique(ds) for b in (0, 1) if ((ds == a) & (y == b)).any()]
    for a, b in cells:
        i = (ds == a) & (y == b); w[i] = len(y) / (len(cells) * i.sum())
    return w


def fit_score(Xtr, ytr, Xte, w=None):
    from model.clinical_models.clinical import lr
    m = lr()
    if w is None:
        m.fit(Xtr, ytr)
    else:
        m.fit(Xtr, ytr, logisticregressioncv__sample_weight=w)
    return m.decision_function(Xte)


def run_arms(Fz, yz, fz, Ft, yt, ft, reps):
    """Skor OOF: Z (Zambia saja) pada Zambia; G (gabungan berbobot) pada Zambia dan TBscreen."""
    nz, nt = len(yz), len(yt)
    Z = np.zeros((reps, nz)); Gz = np.zeros((reps, nz)); Gt = np.zeros((reps, nt))
    for r in range(reps):
        for k in range(5):
            tz, ez = fz[r] != k, fz[r] == k
            tt, et = ft[r] != k, ft[r] == k
            Z[r, ez] = fit_score(Fz[tz], yz[tz], Fz[ez])
            X = np.vstack([Fz[tz], Ft[tt]]); y = np.r_[yz[tz], yt[tt]]
            ds = np.r_[np.zeros(tz.sum(), int), np.ones(tt.sum(), int)]
            s = fit_score(X, y, np.vstack([Fz[ez], Ft[et]]), weights(ds, y))
            Gz[r, ez] = s[:ez.sum()]; Gt[r, et] = s[ez.sum():]
        print("ulangan", r, flush=True)
    return Z, Gz, Gt


def tbs_folds(t: pd.DataFrame, reps: int) -> np.ndarray:
    f = np.zeros((reps, len(t)), int)
    for r in range(reps):
        for k, (_, te) in enumerate(StratifiedKFold(5, shuffle=True, random_state=r).split(t, t.strat)):
            f[r, te] = k
    return f


def boot_delta(y, A, B, g, n=1000, seed=0):
    """CI 95% Δ = mean_r auc_strat(A_r) - mean_r auc_strat(B_r), bootstrap atas peserta (berpasangan)."""
    from model.evaluation.protocol import auc_strat
    rng = np.random.default_rng(seed); v = []
    for _ in range(n):
        j = rng.integers(0, len(y), len(y))
        try:
            v.append(np.mean([auc_strat(y[j], A[r][j], g[j]) - auc_strat(y[j], B[r][j], g[j]) for r in range(len(A))]))
        except ZeroDivisionError:
            continue
    return np.percentile(v, 2.5), np.percentile(v, 97.5)


def perm_null(Fz, yz, uz, fz, Ft, yt, t, ft, n_perm, seed=7):
    """Nol untuk lengan G (ukuran utama pada Zambia): label diacak di dalam dataset x klinik/cohort x jenis kelamin."""
    from model.evaluation.protocol import auc_strat
    rng = np.random.default_rng(seed); out = []
    gz = (uz.fac + uz.sex_m.astype(str)).values; gt = (t.cohort + t.sex_m.astype(str)).values
    for i in range(n_perm):
        pz, pt = yz.copy(), yt.copy()
        for g in np.unique(gz):
            j = np.where(gz == g)[0]; pz[j] = rng.permutation(yz[j])
        for g in np.unique(gt):
            j = np.where(gt == g)[0]; pt[j] = rng.permutation(yt[j])
        _, Gz, _ = run_arms(Fz, pz, fz[:1], Ft, pt, ft[:1], 1)
        out.append(auc_strat(pz, Gz[0], uz.sex_m.values))
        print("nol", i, round(out[-1], 3), flush=True)
    return np.array(out)


def evaluate(n_perm: int, reps: int, out: str):
    from model.evaluation import protocol as P
    from model.pretrained.embed_pretrained import participant_matrix
    u = P.universe()
    Fz = participant_matrix("hear", u)
    ok = ~np.isnan(Fz).any(1)
    uz = u[ok].reset_index(drop=True); Fz = Fz[ok]
    yz = uz.y.values.astype(int); sz = uz.sex_m.values
    fz = P.make_folds(uz, reps)
    Ft, t = tbs_participants()
    yt = t.y.values.astype(int); ft = tbs_folds(t, reps)
    Z, Gz, Gt = run_arms(Fz, yz, fz, Ft, yt, ft, reps)

    st = lambda S, y, g: float(np.mean([P.auc_strat(y, S[r], g) for r in range(len(S))]))
    raw = lambda S, y: float(np.mean([roc_auc_score(y, S[r]) for r in range(len(S))]))
    z_st, g_st = st(Z, yz, sz), st(Gz, yz, sz)
    d_lo, d_hi = boot_delta(yz, Gz, Z, sz)
    nul = perm_null(Fz, yz, uz, fz, Ft, yt, t, ft, n_perm) if n_perm else np.array([np.nan])
    p95 = float(np.nanpercentile(nul, 95))
    ok_main = (d_lo > 0) and (g_st > p95)

    # gabungan dan pembanding asal dataset (peserta yang sama)
    yall = np.r_[yz, yt]; ds = np.r_[np.zeros(len(yz)), np.ones(len(yt))]
    pooled = float(np.mean([roc_auc_score(yall, np.r_[Gz[r], Gt[r]]) for r in range(reps)]))
    pooled_within = float(np.mean([P.auc_strat(yall, np.r_[Gz[r], Gt[r]], ds) for r in range(reps)]))
    ds_only = roc_auc_score(yall, ds)
    cohort_only = roc_auc_score(yt, (t.cohort == "A").astype(int))
    tbs_in = raw(Gt, yt)
    # lintas arah dan jalan pintas
    t2z = roc_auc_score(yz, fit_score(Ft, yt, Fz)); t2z_st = P.auc_strat(yz, fit_score(Ft, yt, Fz), sz)
    z2t = roc_auc_score(yt, fit_score(Fz, yz, Ft))
    X = np.vstack([Fz, Ft]); sd = np.zeros(len(ds))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(X, ds):
        sd[te] = fit_score(X[tr], ds[tr].astype(int), X[te])
    probe_ds = roc_auc_score(ds, sd)

    o = ["# K-25: gabungan Zambia + TBscreen (HeAR + LR)", "",
         f"Zambia: {len(uz)} peserta ({int(yz.sum())} positif), lipatan E0 5 x {reps}. TBscreen pasif: {len(t)} subjek "
         f"({int(yt.sum())} TB; cohort A {int((t.cohort == 'A').sum())}, C {int((t.cohort == 'C').sum())}). Aturan: K-25.", "",
         "## Ukuran utama (peserta Zambia yang ditahan)", "",
         "| lengan | AUROC mentah | AUROC strat. jenis kelamin |", "|---|---|---|",
         f"| Z: latih Zambia saja | {raw(Z, yz):.3f} | {z_st:.3f} |",
         f"| G: latih Zambia + TBscreen (berbobot) | {raw(Gz, yz):.3f} | {g_st:.3f} |", "",
         f"- Δ (G - Z) strat. = {g_st - z_st:+.3f}, CI 95% bootstrap berpasangan [{d_lo:+.3f}, {d_hi:+.3f}]",
         f"- Nol permutasi lengan G: mean {np.nanmean(nul):.3f}, p95 {p95:.3f}, maks {np.nanmax(nul):.3f} (n={len(nul)})",
         f"- **Kriteria K-25: {'BERHASIL' if ok_main else 'TIDAK BERHASIL'}** (butuh batas bawah CI Δ > 0 dan G > p95 nol)", "",
         "## Pelaporan wajib", "",
         "| ukuran | AUROC | catatan |", "|---|---|---|",
         f"| gabungan (Zambia + TBscreen, lengan G) | {pooled:.3f} | harus dibaca berdampingan dengan baris berikut |",
         f"| asal dataset saja (tanpa audio), peserta sama | {ds_only:.3f} | jalan pintas |",
         f"| gabungan, rata-rata di dalam tiap dataset | {pooled_within:.3f} | tanpa efek prevalensi antar-dataset |",
         f"| dalam TBscreen (lengan G) | {tbs_in:.3f} | cohort saja {cohort_only:.3f}: tercampur cohort |",
         f"| TBscreen -> Zambia (mentah / strat.) | {t2z:.3f} / {t2z_st:.3f} | latih TBscreen, uji Zambia |",
         f"| Zambia -> TBscreen | {z2t:.3f} | tercampur cohort |",
         f"| embedding -> asal dataset (CV) | {probe_ds:.3f} | seberapa mudah dataset dikenali |", ""]
    path = pathlib.Path(out); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(o) + "\n")
    print("\n".join(o))


def xfer(n_perm: int, out: str):
    """K-26 (4): latih TBscreen, uji Zambia. Nol: label TBscreen diacak dalam jenis kelamin (utama) dan dalam cohort x jenis kelamin."""
    from sklearn.linear_model import LinearRegression
    from model.evaluation import protocol as P
    from model.pretrained.embed_pretrained import participant_matrix
    u = P.universe()
    Fz = participant_matrix("hear", u); ok = ~np.isnan(Fz).any(1)
    uz = u[ok].reset_index(drop=True); Fz = Fz[ok]
    yz = uz.y.values.astype(int); sz = uz.sex_m.values
    az = uz.age.astype(float).fillna(uz.age.astype(float).median()).values
    Ft, t = tbs_participants()
    yt = t.y.values.astype(int); st = t.sex_m.values; at = t.age.fillna(t.age.median()).values

    def resid(F, s, a):
        c = np.column_stack([s, a]); return F - LinearRegression().fit(c, F).predict(c)

    Fz_r, Ft_r = resid(Fz, sz, az), resid(Ft, st, at)
    w_sex = weights(st, yt)                       # sel jenis kelamin x label berbobot sama
    variants = {"utama": (Ft, Fz, None), "(a) berbobot jenis kelamin x label": (Ft, Fz, w_sex),
                "(b) residu jenis kelamin + usia": (Ft_r, Fz_r, None)}

    def score(Xt, y, Xz, w):
        return fit_score(Xt, y, Xz, None if w is None else w)

    rng = np.random.default_rng(11)
    o = ["# K-26 (4): TBscreen -> Zambia (HeAR + LR)", "",
         f"Latih: TBscreen pasif {len(t)} subjek ({int(yt.sum())} TB). Uji: Zambia {len(uz)} peserta ({int(yz.sum())} positif). "
         f"Nol: {n_perm} permutasi label TBscreen, pelatihan diulang. Aturan: K-26.", "",
         "| varian | AUROC mentah | AUROC strat. | nol dalam jenis kelamin: mean / p95 / maks | p | nol dalam cohort x jenis kelamin: p95 | skor -> jenis kelamin |",
         "|---|---|---|---|---|---|---|"]
    verdict = []
    for nm, (Xt, Xz, w) in variants.items():
        s = score(Xt, yt, Xz, w)
        raw, stv = roc_auc_score(yz, s), P.auc_strat(yz, s, sz)
        nul1, nul2 = [], []
        for i in range(n_perm):
            yp = yt.copy()
            for g in np.unique(st):
                j = np.where(st == g)[0]; yp[j] = rng.permutation(yt[j])
            wp = None if w is None else weights(st, yp)
            nul1.append(P.auc_strat(yz, score(Xt, yp, Xz, wp), sz))
            if i < n_perm // 4:                     # nol kedua lebih sedikit: diperkirakan tidak informatif
                yq = yt.copy(); g2 = t.cohort.values + st.astype(str)
                for g in np.unique(g2):
                    j = np.where(g2 == g)[0]; yq[j] = rng.permutation(yt[j])
                wq = None if w is None else weights(st, yq)
                nul2.append(P.auc_strat(yz, score(Xt, yq, Xz, wq), sz))
        nul1 = np.array(nul1); p95 = np.percentile(nul1, 95)
        p = (np.sum(nul1 >= stv) + 1) / (len(nul1) + 1)
        verdict.append(stv > p95)
        o.append(f"| {nm} | {raw:.3f} | **{stv:.3f}** | {nul1.mean():.3f} / {p95:.3f} / {nul1.max():.3f} | {p:.3f} | "
                 f"{np.percentile(nul2, 95):.3f} | {roc_auc_score(sz, s):.3f} |")
        print(o[-1], flush=True)
    o += ["", f"- **Kriteria K-26 (4): {'SINYAL' if all(verdict) else 'BUKAN SINYAL'}** "
          "(utama dan kontrol (a), (b) harus di atas p95 nol dalam jenis kelamin)"]
    path = pathlib.Path(out); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hear", "eval", "xfer"])
    ap.add_argument("--perm", type=int, default=40)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "gabungan-tbscreen.md"))
    a = ap.parse_args()
    if a.cmd == "hear":
        extract_hear()
    elif a.cmd == "xfer":
        xfer(a.perm, a.out if a.out != ap.get_default("out") else str(paths.runs_dir() / "reports" / "tbscreen-ke-zambia.md"))
    else:
        evaluate(a.perm, a.reps, a.out)
