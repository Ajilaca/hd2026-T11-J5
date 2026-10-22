"""Fusi gejala klinis + logit audio di papan (hanya pustaka standar). Koefisien dari fusi.json (dibuat sw/pynq/laptop/fit_fusi.py di laptop).

Gejala: lama batuk (0 tidak batuk, 1 <1 mgg, 2 1-2 mgg, 3 3-4 mgg, 4 >4 mgg), BMI dari berat/tinggi, jenis kelamin (L=1),
penurunan berat badan (y/t), keringat malam (y/t). Skor fusi = c0 + c1*skor_klinis + c2*logit/1000 (regresi logistik).
Skor bukan probabilitas terkalibrasi; RUJUK bila skor >= ambang. Alat triase, bukan diagnosis.
"""
import json
import math

LAMA = ["tidak batuk", "< 1 minggu", "1-2 minggu", "3-4 minggu", "> 4 minggu"]


def load(path: str = "fusi.json") -> dict:
    return json.load(open(path))


def clin_score(fz: dict, g: dict) -> float:
    x = [g["coughdur"], g["bmi"], g["sex"], g["weightloss"], g["ngtsweats"]]
    return fz["klinis"]["b"] + sum(w * v for w, v in zip(fz["klinis"]["w"], x))


def fuse(coef: list, clin: float, logit: float) -> float:
    return coef[0] + coef[1] * clin + coef[2] * logit / 1000.0


def prob(s: float) -> float:
    return 1.0 / (1.0 + math.exp(-s))


def short(g: dict) -> str:
    """Ringkasan gejala satu kolom: B<lama> BMI<x> L/P BB+/- KM+/-."""
    return (f"B{g['coughdur']} BMI{g['bmi']:.0f} {'L' if g['sex'] else 'P'} "
            f"BB{'+' if g['weightloss'] else '-'} KM{'+' if g['ngtsweats'] else '-'}")


def long(g: dict) -> str:
    """Gejala dalam kalimat biasa."""
    return (f"batuk {LAMA[g['coughdur']]}, BMI {g['bmi']:.1f}, {'laki-laki' if g['sex'] else 'perempuan'}, "
            f"{'berat badan turun' if g['weightloss'] else 'berat badan tidak turun'}, "
            f"{'keringat malam' if g['ngtsweats'] else 'tanpa keringat malam'}")


def _yn(q: str) -> int:
    while True:
        a = input(q + " (y/t): ").strip().lower()
        if a in ("y", "ya"):
            return 1
        if a in ("t", "tidak", "n"):
            return 0
        print("  jawab y atau t")


def _num(q: str, lo: float, hi: float) -> float:
    while True:
        try:
            v = float(input(q + ": ").strip().replace(",", "."))
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  masukkan angka {lo:g}-{hi:g}")


def ask() -> dict:
    """Tanya 5 gejala lewat terminal (6 pertanyaan: berat dan tinggi untuk BMI)."""
    print("\nPertanyaan gejala")
    print("  Lama batuk: " + ",  ".join(f"{i} = {s}" for i, s in enumerate(LAMA)))
    cd = int(_num("1. Sudah berapa lama batuk? (0-4)", 0, 4))
    sex = _yn("2. Jenis kelamin laki-laki?")
    bw = _num("3. Berat badan (kg)", 20, 200)
    ht = _num("4. Tinggi badan (cm)", 100, 220)
    wl = _yn("5. Berat badan turun tanpa disengaja akhir-akhir ini?")
    ns = _yn("6. Sering berkeringat di malam hari?")
    g = dict(coughdur=cd, bmi=bw / (ht / 100) ** 2, sex=sex, weightloss=wl, ngtsweats=ns)
    print(f"  Tercatat: {long(g)}")
    return g


def table(rows: list, head: list, left: tuple) -> str:
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(head)]
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) if i in left else c.rjust(w[i]) for i, c in enumerate(r)) + " |"  # noqa: E731
    return "\n".join([line, fmt(head), line, *(fmt(r) for r in rows), line])
