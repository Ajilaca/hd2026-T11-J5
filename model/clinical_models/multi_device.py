"""K-32: lebih banyak batuk per peserta (lintas perangkat, semua klip) dan titik kerja sensitivitas/spesifisitas.

    python -m model.clinical_models.multi_device    # -> runs/reports/lintas-perangkat.md (cache logit: work/board_test/logits_all_devices.csv)
Aturan ditetapkan sebelum angka: docs/vault/keputusan.md K-32.
"""
from __future__ import annotations
import multiprocessing as mp
import pathlib
import warnings
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from golden import paths
from golden.blocks import cnn as C
from golden.blocks import frontend as F
from model.data import dataset
from sw.pynq.laptop.fit_fusi import clin_x, lr_raw

warnings.filterwarnings("ignore")
BT = paths.data_root() / "work" / "board_test"
CACHE = BT / "logits_all_devices.csv"
DEVS = ("phonea", "phoneb", "phonec", "recorder")
_Q = None


def _job(a):
    global _Q
    if _Q is None:
        _Q = C.load_qmodel(paths.runs_dir() / "model_distill" / "qmodel.npz")
    b, d = a
    p = paths.processed_dir() / "clips" / d / f"{b}.npz"
    if not p.exists():
        return []
    cl = np.load(p, allow_pickle=True)["clips"]
    return [(b, d, i, int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), _Q)[0])) for i, x in enumerate(cl)]


def logits(aud):
    if CACHE.exists():
        return pd.read_csv(CACHE)
    with mp.Pool(6) as pool:
        res = pool.map(_job, [(b, d) for b in aud for d in DEVS], chunksize=8)
    df = pd.DataFrame([r for rr in res for r in rr], columns=["barcode", "device", "clip", "logit"])
    df.to_csv(CACHE, index=False)
    return df


def boot_delta(y, s, s0, n=2000, seed=0):
    rng = np.random.default_rng(seed); d = []
    for _ in range(n):
        j = rng.integers(0, len(y), len(y))
        if y[j].min() == y[j].max():
            continue
        d.append(roc_auc_score(y[j], s[j]) - roc_auc_score(y[j], s0[j]))
    return np.percentile(d, [2.5, 97.5])


def fuse_oof(clin, a, y):
    s = np.zeros(len(y))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(a, y):
        w, b = lr_raw(np.column_stack([clin[tr], a[tr]]), y[tr], C=1.0)
        s[te] = b + w[0] * clin[te] + w[1] * a[te]
    return s


def oppoints(s, y, prev):
    rows = []
    for se in (0.95, 0.90, 0.85, 0.80, 0.70):
        t = np.percentile(s[y == 1], 100 * (1 - se))
        sens = (s[y == 1] >= t).mean(); spes = (s[y == 0] < t).mean()
        rows.append((se, sens, spes, 100 * (sens * prev + (1 - spes) * (1 - prev)), 100 * sens * prev))
    return rows


def main():
    gm = dataset.load_meta().drop_duplicates("barcode")
    gm = gm[gm.ground_truth_tb.isin(["pos", "neg"])].set_index("barcode")
    gm["bmi"] = gm.bmi.astype(float).fillna(gm.bmi.astype(float).median())
    prev = float(gm.y.mean())
    aud = [b for b in pd.read_csv(BT / "all_logits_phonec.csv").barcode if b in gm.index]
    df = logits(aud)
    y = gm.loc[aud].y.values.astype(int)
    rest = gm.drop(index=aud); wc, bc = lr_raw(clin_x(rest), rest.y.values.astype(int))
    clin = clin_x(gm.loc[aud]) @ np.array(wc) + bc
    var = {"A: ponsel C, 10 klip": (["phonec"], 10), "B: ponsel C, semua klip": (["phonec"], None),
           "C: ponsel A+B+C, 10 klip/ponsel": (["phonea", "phoneb", "phonec"], 10),
           "D: ponsel A+B+C, semua klip": (["phonea", "phoneb", "phonec"], None),
           "E: D + perekam": (list(DEVS), None)}
    S, NCL = {}, {}
    for k, (devs, cap) in var.items():
        d = df[df.device.isin(devs)]
        if cap:
            d = d[d["clip"] < cap]
        g = d.groupby("barcode").logit
        S[k] = g.mean().reindex(aud).values / 1000.0; NCL[k] = g.size().reindex(aud).values
    ka = list(var)[0]
    o = ["# K-32: lebih banyak batuk per peserta dan titik kerja", "",
         f"349 peserta berlaudio ponsel C ({int(y.sum())} positif). Murid CNN int8 (ROM `suaratb_axil`), logit golden {len(df)} klip. Aturan: K-32.", "",
         "## (1) Varian jumlah batuk", "",
         "| varian | klip per peserta (median) | AUROC audio | Δ vs A [CI 95%] | AUROC fusi (OOF) |", "|---|---|---|---|---|"]
    best, bestd = ka, -1.0
    for k in var:
        a = S[k]; au = roc_auc_score(y, a); fu = roc_auc_score(y, fuse_oof(clin, a, y))
        if k == ka:
            dl = "acuan"
        else:
            lo, hi = boot_delta(y, a, S[ka]); dd = au - roc_auc_score(y, S[ka])
            dl = f"{dd:+.3f} [{lo:+.3f}, {hi:+.3f}]" + (" LEBIH BAIK" if lo > 0 else "")
            if lo > 0 and dd > bestd:
                best, bestd = k, dd
        o.append(f"| {k} | {int(np.median(NCL[k]))} | {au:.3f} | {dl} | {fu:.3f} |")
    o += ["", f"AUROC gejala saja (model dari peserta tanpa audio): {roc_auc_score(y, clin):.3f}.",
          f"Varian terbaik menurut kriteria: {best if best != ka else 'tidak ada (tidak ada CI di atas 0)'}.", "",
          f"## (3) Titik kerja (ambang dipilih pada data yang sama: optimistis; dirujuk per 100 orang pada prevalensi {prev:.1%})", ""]
    sets = [("audio A", S[ka]), ("gejala saja", clin), ("gejala + audio A", fuse_oof(clin, S[ka], y))]
    if best != ka:
        sets += [(f"gejala + audio {best[:1]}", fuse_oof(clin, S[best], y))]
    for nm, s in sets:
        o += [f"**{nm}** (AUROC {roc_auc_score(y, s):.3f})", "", "| target sens | sens | spes | dirujuk /100 | TB terjaring /100 |", "|---|---|---|---|---|"]
        o += [f"| {se:.0%} | {a_:.0%} | {b_:.0%} | {c_:.0f} | {d_:.1f} |" for se, a_, b_, c_, d_ in oppoints(s, y, prev)] + [""]
    o += ["Catatan: lintas perangkat hanya untuk mode dataset; alat satu mikrofon tidak bisa memakainya. Lima varian dibandingkan. Bukan kinerja klinis."]
    p = paths.runs_dir() / "reports" / "lintas-perangkat.md"; p.write_text("\n".join(o) + "\n"); print("\n".join(o))


if __name__ == "__main__":
    main()
