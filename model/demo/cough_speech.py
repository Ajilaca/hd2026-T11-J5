"""K-29: model demonstrasi batuk vs bukan batuk (bicara, derau) dengan arsitektur hardware yang sama. BUKAN model TBC.

    python -m model.demo.cough_speech build    # fitur + klip mentah negatif Speech Commands -> features/speech_neg.npz
    python -m model.demo.cough_speech train    # latih float, PTQ int8 golden, evaluasi UJI, ekspor runs/model_cough (+ laporan)
    python -m model.demo.cough_speech paket    # paket papan: klip UJI (batuk + bukan batuk) + logit golden -> work/board_test/cough/paket

Aturan (pembagian, ukuran, batas klaim) di docs/vault/keputusan.md K-29, ditetapkan sebelum angka.
"""
from __future__ import annotations
import argparse
import multiprocessing as mp
import pathlib
import shutil
import warnings
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from golden import params, paths
from golden.blocks import cnn as C
from golden.blocks import frontend as F
from golden.blocks.cough_det import cough_det, hop_energy
from golden.blocks.preemph import preemph
from golden.gen.io_mem import write_mem
from model.data.audio_io import load_16k
from model.scratch import export as EX
from model.scratch import mil_train as M

warnings.filterwarnings("ignore")
torch.set_num_threads(8)
SC_DIR = paths.raw_dir() / "speech_commands_test"
NEG = paths.features_dir() / "speech_neg.npz"
OUT = paths.runs_dir() / "model_cough"
EPOCHS, BS, SEED, TEST_FRAC = 20, 64, 0, 0.2


def _neg_job(p: str):
    x = load_16k(p).astype(np.int64)
    E = hop_energy(preemph(x))
    ev = cough_det(E)
    trig = bool(ev)
    start = ev[0].start if ev else max(int(np.argmax(E)) - params.PRE_ROLL - 5, 0)
    raw = F.pad_clip(x[start * params.HOP: start * params.HOP + params.CLIP_SAMPLES_PADDED])
    return raw.astype(np.int16), F.features_q(raw).astype(np.int8), trig


def build():
    files = sorted(p for p in SC_DIR.glob("*/*.wav"))
    with mp.Pool(4) as pool:
        res = pool.map(_neg_job, [str(p) for p in files], chunksize=32)
    word = np.array([p.parent.name for p in files])
    spk = np.array([p.name.split("_nohash_")[0] if "_nohash_" in p.name else p.stem for p in files])
    np.savez_compressed(NEG, raw=np.stack([r[0] for r in res]), X=np.stack([r[1] for r in res]),
                        trig=np.array([r[2] for r in res]), word=word, spk=spk, path=np.array([str(p.relative_to(SC_DIR)) for p in files]))
    print(f"{len(files)} klip negatif, detektor memicu pada {np.mean([r[2] for r in res]):.1%} -> {NEG}")


def split():
    zp = np.load(paths.features_dir() / "distill_clips.npz", allow_pickle=True)
    zn = np.load(NEG, allow_pickle=True)
    rng = np.random.default_rng(SEED)
    bp = np.unique(zp["barcode"]); tp = set(rng.permutation(bp)[:int(round(TEST_FRAC * len(bp)))])
    sp = np.unique(zn["spk"]); ts = set(rng.permutation(sp)[:int(round(TEST_FRAC * len(sp)))])
    te_p = np.array([b in tp for b in zp["barcode"]]); te_n = np.array([s in ts for s in zn["spk"]])
    return zp, zn, te_p, te_n, tp


def to_t(X: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(X.astype(np.float32) / M.SCALE).permute(0, 2, 1).unsqueeze(1).contiguous()


def train():
    zp, zn, te_p, te_n, _ = split()
    X = np.concatenate([zp["X"], zn["X"]]); y = np.r_[np.ones(len(zp["X"])), np.zeros(len(zn["X"]))].astype(np.float32)
    te = np.r_[te_p, te_n]; tr = np.where(~te)[0]
    word = np.r_[np.array(["batuk"] * len(zp["X"])), zn["word"]]
    Xt = to_t(X); yt = torch.from_numpy(y)
    torch.manual_seed(SEED); rng = np.random.default_rng(SEED)
    net = M.Net(c=(16, 32, 32), h=16)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-2)
    steps = EPOCHS * int(np.ceil(len(tr) / BS))
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-3, total_steps=steps)
    pw = torch.tensor((y[tr] == 0).sum() / max((y[tr] == 1).sum(), 1))
    lossf = nn.BCEWithLogitsLoss(pos_weight=pw)
    for ep in range(EPOCHS):
        net.train(); order = tr[rng.permutation(len(tr))]; tot = 0.0
        for i in range(0, len(order), BS):
            b = order[i:i + BS]
            opt.zero_grad(); loss = lossf(net(M.augment(Xt[b])), yt[b]); loss.backward(); opt.step(); sch.step()
            tot += float(loss) * len(b)
        print(f"epoch {ep + 1}/{EPOCHS} loss {tot / len(tr):.4f}", flush=True)
    net.eval()
    with torch.no_grad():
        zf = np.concatenate([net(Xt[i:i + 512]).numpy() for i in range(0, len(Xt), 512)])
    qm = EX.ptq(net, Xt[tr[::4]])
    stats = {}
    idx = np.where(te)[0]
    zi = EX.int_logits(qm, X[idx], stats)
    yte = y[idx]
    auf, aui = roc_auc_score(yte, zf[idx]), roc_auc_score(yte, zi)
    pred = zi >= 0
    acc = float((pred == (yte == 1)).mean()); sens = float(pred[yte == 1].mean()); spes = float((~pred[yte == 0]).mean())
    accf = float(((zf[idx] >= 0) == (yte == 1)).mean())
    OUT.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), OUT / "float.pt"); C.save_qmodel(qm, OUT / "qmodel.npz")
    for L in qm.layers:
        write_mem(OUT / f"{L.name}_w.mem", L.w.ravel(), 8, f"{L.name} bobot int8 (cout,cin[,3,3]) row-major")
        write_mem(OUT / f"{L.name}_b.mem", L.b, params.BIAS_BITS, f"{L.name} bias int24")
    write_mem(OUT / "requant.mem", [v for L in qm.layers for v in (L.m0, L.shift)], 16, "per layer: M0(Q15), shift")
    wte = word[idx]
    o = ["# K-29: batuk vs bukan batuk (model demonstrasi, BUKAN TBC)", "",
         f"Positif: {len(zp['X'])} klip batuk Zambia ({len(np.unique(zp['barcode']))} peserta). Negatif: {len(zn['X'])} klip Speech Commands "
         f"v0.02 test set (detektor memicu pada {zn['trig'].mean():.1%}). UJI = 20% peserta dan 20% pembicara (seed {SEED}): "
         f"{int(yte.sum())} batuk, {int((yte == 0).sum())} bukan batuk. Latih {len(tr)} klip, {EPOCHS} epoch, hiperparameter tetap.", "",
         "| | AUROC | akurasi (ambang 0) |", "|---|---|---|",
         f"| float | {auf:.4f} | {accf:.1%} |", f"| int8 golden | {aui:.4f} | {acc:.1%} |", "",
         f"int8: sensitivitas (batuk terdeteksi) {sens:.1%}, spesifisitas (bukan batuk ditolak) {spes:.1%}. "
         f"Penurunan AUROC float -> int8 {auf - aui:+.4f} (kriteria <= 0,02: {'LULUS' if auf - aui <= 0.02 else 'GAGAL'}).", "",
         "| kelas UJI | n | benar |", "|---|---|---|"]
    for w in ["batuk"] + sorted(set(wte) - {"batuk"}):
        m = wte == w
        o.append(f"| {w} | {int(m.sum())} | {(pred[m] == (yte[m] == 1)).mean():.1%} |")
    o += ["", f"Puncak akumulator golden: {stats}", "",
          "Batas klaim: tugas demonstrasi; batuk dan bicara berasal dari sumber berbeda (perangkat, ruang, bahasa), jadi sebagian pemisahan bisa "
          "berasal dari perbedaan sumber. Bukan kinerja skrining TBC. INMP441 belum dikalibrasi."]
    rp = paths.runs_dir() / "reports" / "batuk-vs-bicara.md"; rp.write_text("\n".join(o) + "\n")
    print("\n".join(o)); print("tersimpan", OUT, rp)


def paket(n_per_class: int = 50):
    zp, zn, te_p, te_n, tp = split()
    qm = C.load_qmodel(OUT / "qmodel.npz")
    out = paths.data_root() / "work" / "board_test" / "cough"
    pk = out / "paket"
    if pk.exists():
        shutil.rmtree(pk)
    (pk / "clips").mkdir(parents=True)
    rng = np.random.default_rng(SEED)
    rows = []
    cl = paths.processed_dir() / "clips" / "phonec"
    pos = [b for b in sorted(tp) if (cl / f"{b}.npz").exists()]
    for b in rng.permutation(pos)[:n_per_class]:
        rows.append((f"batuk_{len(rows):03d}", 1, "batuk", np.load(cl / f"{b}.npz", allow_pickle=True)["clips"][0].astype(np.int16)))
    idx = np.where(te_n)[0]
    words = sorted(set(zn["word"][idx]))
    per = int(np.ceil(n_per_class / len(words)))
    sel = []
    for w in words:
        j = idx[zn["word"][idx] == w]
        sel += list(rng.permutation(j)[:per])
    for i in rng.permutation(sel)[:n_per_class]:
        rows.append((f"bukan_{len(rows) - n_per_class:03d}", 0, str(zn["word"][i]), zn["raw"][i]))
    man = ["nama,y,jenis,golden_logit"]
    for nm, y, jenis, x in rows:
        x.astype("<i2").tofile(pk / "clips" / f"{nm}.raw")
        g = int(C.cnn_forward(F.to_cnn_input(F.features_q(x.astype(np.int64))), qm)[0])
        man.append(f"{nm},{y},{jenis},{g}")
    (pk / "manifest.csv").write_text("\n".join(man) + "\n")
    here = pathlib.Path(__file__).resolve().parents[2] / "sw" / "pynq" / "papan"
    for f in ("axil_smoke.py", "axil_mic.py", "cough1.py", "cough_mic.py", "setup_papan.sh"):
        if (here / f).exists():
            shutil.copy(here / f, pk)
    print(f"{len(rows)} klip -> {pk}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "train", "paket"])
    a = ap.parse_args()
    {"build": build, "train": train, "paket": paket}[a.cmd]()
