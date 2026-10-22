"""K-26 (2) dan (3): guru pralatih lain dan gabungan guru, dengan klip dan jendela yang sama dengan HeAR.

    python -m model.pretrained.teachers windows                  # -> features/hear_windows.npz (klip 2 s Zambia, urutan = emb_hear.npz)
    python -m model.pretrained.teachers embed --model wavlm      # -> features/emb_wavlm.npz (ast, clap, wavlm, whisper)
    python -m model.pretrained.teachers eval [--perm 40]         # -> runs/reports/guru-lain.md

Aturan ditetapkan sebelum angka (docs/vault/keputusan.md K-26): protokol E0 (5 x 10, nol 40); kandidat lebih baik dari HeAR hanya bila
batas bawah CI 95% bootstrap berpasangan Δ (kandidat - HeAR, AUROC strat.) > 0. Gabungan = rata-rata skor OOF terstandar per ulangan.
Seleksi klip sama dengan embed_pretrained.extract_hear (tanpa label): per peserta satu perangkat (phonec, phoneb, phonea, recorder),
maks. 6 klip paling keras, jendela 2 s mulai 0,25 s sebelum onset detektor golden.
"""
from __future__ import annotations
import argparse
import os
import pathlib
import warnings
import numpy as np
import pandas as pd
from golden import paths

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HOME", str(paths.data_root() / "hf"))   # sebelum import transformers
FD = paths.features_dir()
REPOS = {"ast": "MIT/ast-finetuned-audioset-10-10-0.4593", "clap": "laion/clap-htsat-unfused",
         "wavlm": "microsoft/wavlm-base-plus", "whisper": "openai/whisper-base"}


def windows(max_clips: int = 6, pref=("phonec", "phoneb", "phonea", "recorder")):
    """Ulang seleksi klip extract_hear apa adanya; simpan jendela 2 s float32 (16 kHz)."""
    from golden import params
    from golden.blocks.cough_det import hop_energy, cough_det
    from golden.blocks.preemph import preemph
    from model.data.audio_io import load_16k
    fx = pd.read_csv(paths.processed_dir() / "barcode_fix.csv")
    fx = fx[fx.tier.isin(["asli", "pola", "tengah"]) & fx.path.str.lower().str.endswith(".wav")]
    rows, W = [], []
    for n, (b, g) in enumerate(fx.groupby("barcode_fix")):
        for d in pref:
            gd = g[g.device == d]
            if len(gd):
                break
        cands = []
        for pth in gd.path.tolist():
            x = load_16k(str(paths.raw_dir() / pth)).astype(np.int64)
            E = hop_energy(preemph(x))
            for e in cough_det(E):
                lo = e.onset * params.HOP - 4000
                cands.append((float(E[e.onset:e.onset + 12].max()), pth, x, max(lo, 0)))
        cands.sort(key=lambda t: -t[0])
        for _, pth, x, s0 in cands[:max_clips]:
            w = x[s0:s0 + 32000].astype(np.float32) / 32768.0
            W.append(np.pad(w, (0, 32000 - len(w)))); rows.append((pth, b, d))
        if n % 50 == 0:
            print("jendela", n, len(W), flush=True)
    r = pd.DataFrame(rows, columns=["path", "barcode", "device"])
    ref = np.load(FD / "emb_hear.npz", allow_pickle=True)
    same = len(r) == len(ref["path"]) and (r.path.values == ref["path"]).all() and (r.barcode.values == ref["barcode"]).all()
    print("urutan klip sama dengan emb_hear.npz:", same, len(r), flush=True)
    assert same, "seleksi klip berbeda dari HeAR"
    np.savez(FD / "hear_windows.npz", w=np.stack(W), path=r.path.values, barcode=r.barcode.values, device=r.device.values)


def embed(name: str, threads: int = 4, batch: int = 8):
    import torch
    import transformers as T
    torch.set_num_threads(threads)
    z = np.load(FD / "hear_windows.npz", allow_pickle=True)
    W = z["w"]; repo = REPOS[name]
    if name == "ast":
        fe = T.ASTFeatureExtractor.from_pretrained(repo); m = T.ASTModel.from_pretrained(repo).eval()
        f = lambda b: m(**fe(list(b), sampling_rate=16000, return_tensors="pt")).pooler_output
    elif name == "clap":
        from scipy.signal import resample_poly
        pr = T.ClapProcessor.from_pretrained(repo); m = T.ClapModel.from_pretrained(repo).eval()
        def f(b):   # transformers baru mengembalikan objek keluaran; embedding audio ada di pooler_output
            o = m.get_audio_features(**pr(audio=[resample_poly(x, 3, 1) for x in b], sampling_rate=48000, return_tensors="pt"))
            return getattr(o, "pooler_output", o)
    elif name == "wavlm":
        fe = T.Wav2Vec2FeatureExtractor.from_pretrained(repo); m = T.WavLMModel.from_pretrained(repo).eval()
        f = lambda b: m(**fe(list(b), sampling_rate=16000, return_tensors="pt")).last_hidden_state.mean(1)
    else:   # whisper: masukan dipad ke 30 s; rata-rata 100 frame encoder pertama (= 2 s, 50 frame/s)
        fe = T.WhisperFeatureExtractor.from_pretrained(repo); m = T.WhisperModel.from_pretrained(repo).get_encoder().eval()
        f = lambda b: m(fe(list(b), sampling_rate=16000, return_tensors="pt").input_features).last_hidden_state[:, :100].mean(1)
    out = []
    with torch.no_grad():
        for i in range(0, len(W), batch):
            out.append(f(W[i:i + batch]).float().numpy())
            if (i // batch) % 25 == 0:
                print(name, i, len(W), flush=True)
    np.savez(FD / f"emb_{name}.npz", emb=np.concatenate(out), path=z["path"], barcode=z["barcode"], device=z["device"])
    print("selesai", name, flush=True)


def evaluate(names, n_perm: int, out: str, reps: int = 10):
    from sklearn.metrics import roc_auc_score
    from model.evaluation import protocol as P
    from model.pretrained.embed_pretrained import participant_matrix
    from model.pretrained.merge_tbs import boot_delta
    u = P.universe()
    allnames = ["hear", "operaCT"] + [n for n in names if (FD / f"emb_{n}.npz").exists()]
    Fs = {n: participant_matrix(n, u) for n in allnames}
    ok = np.all([~np.isnan(F).any(1) for F in Fs.values()], axis=0)
    u = u[ok].reset_index(drop=True); Fs = {n: F[ok] for n, F in Fs.items()}
    y = u.y.values.astype(int); sx = u.sex_m.values; folds = P.make_folds(u, reps)
    cov = np.column_stack([sx, u.age.astype(float).fillna(u.age.astype(float).median()).values])
    S = {n: P.oof_scores(F, y, u.strat.values, folds, cov)[0] for n, F in Fs.items()}
    zs = lambda A: (A - A.mean(1, keepdims=True)) / A.std(1, keepdims=True)
    st = lambda A: float(np.mean([P.auc_strat(y, A[r], sx) for r in range(len(A))]))
    raw = lambda A: float(np.mean([roc_auc_score(y, A[r]) for r in range(len(A))]))
    best = max([n for n in allnames if n not in ("hear", "operaCT")], key=lambda n: st(S[n]), default=None)
    combos = {"HeAR + OPERA-CT": ["hear", "operaCT"]}
    if best:
        combos[f"HeAR + {best}"] = ["hear", best]
    combos["semua guru (rata-rata)"] = list(allnames)          # ditambahkan sebelum angka (K-26, catatan 2026-10-21)
    for c, mem in combos.items():
        S[c] = sum(zs(S[m]) for m in mem) / len(mem)

    def null(members):
        rng = np.random.default_rng(7); v = []
        g = (u.fac + u.sex_m.astype(str)).values
        for _ in range(n_perm):
            yp = y.copy()
            for k in np.unique(g):
                j = np.where(g == k)[0]; yp[j] = rng.permutation(y[j])
            stp = np.array([f"{a}_{b}_{c}" for a, b, c in zip(yp, u.fac, u.sex_m)])
            A = sum(zs(P.oof_scores(Fs[m], yp, stp, folds[:1])[0]) for m in members) / len(members)
            v.append(P.auc_strat(yp, A[0], sx))
        return np.array(v)

    o = ["# K-26 (2)(3): guru pralatih lain dan gabungan guru (protokol E0)", "",
         f"Semesta {len(u)} peserta, {int(y.sum())} positif; klip dan jendela sama dengan HeAR; 5 x {reps} lipatan; nol {n_perm}. Aturan: K-26.",
         "", "| guru | AUROC mentah | AUROC strat. | nol p95 / maks | Δ vs HeAR [CI 95%] | lebih baik dari HeAR? |", "|---|---|---|---|---|---|"]
    for n in list(Fs) + list(combos):
        nul = null(combos.get(n, [n]))
        lo, hi = boot_delta(y, S[n], S["hear"], sx) if n != "hear" else (np.nan, np.nan)
        d = st(S[n]) - st(S["hear"])
        better = "-" if n == "hear" else ("YA" if lo > 0 else "tidak")
        o.append(f"| {n} | {raw(S[n]):.3f} | **{st(S[n]):.3f}** | {np.percentile(nul, 95):.3f} / {nul.max():.3f} | "
                 f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}] | {better} |")
        print(o[-1], flush=True)
    path = pathlib.Path(out); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(o) + "\n")
    print("\n".join(o))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["windows", "embed", "eval"])
    ap.add_argument("--model", choices=list(REPOS))
    ap.add_argument("--models", nargs="+", default=list(REPOS))
    ap.add_argument("--perm", type=int, default=40)
    ap.add_argument("--out", default=str(paths.runs_dir() / "reports" / "guru-lain.md"))
    a = ap.parse_args()
    if a.cmd == "windows":
        windows()
    elif a.cmd == "embed":
        embed(a.model)
    else:
        evaluate(a.models, a.perm, a.out)
