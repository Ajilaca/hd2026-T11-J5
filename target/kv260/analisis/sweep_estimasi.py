"""Sapuan perhitungan (BUKAN build): clock inti 10-300 MHz x P = 8/16/32 pada KV260 (XCK26).

    python target/kv260/analisis/sweep_estimasi.py [--out $SUARATB_DATA/runs/reports/sweep-clock-P.md]
Semua keluaran diberi label: [T] terukur (laporan alat atau simulasi, sumber disebut), [E] estimasi (model di bawah, asumsi disebut).
Tidak ada angka di sini yang berasal dari papan kecuali yang tertulis "papan". Ketidakpastian estimasi daya besar (Vivado vectorless, confidence Low).
"""
import argparse
import math
import pathlib

FREQS = [10, 25, 50, 75, 100, 150, 200, 250, 300]          # MHz
PS = [8, 16, 32]

# ---- masukan terukur (sumber) -----------------------------------------------------------------------------------------------------
CNN_CYC = {8: 451_880, 16: 226_520, 32: 122_872}            # simulasi Icarus cnn_top start->done (docs/vault/sintesis.md, 2026-10-13)
# kv260_top post-route 300 MHz (target/kv260/README.md; laporan alat build/kv260/full_P16, full_P32)
UTIL_K26 = {16: dict(lut=5954, ff=7845, dsp=17, bram=12), 32: dict(lut=8147, ff=10292, dsp=17, bram=12)}
# XC7A35T 150 MHz OOC (docs/vault/sintesis.md): hanya dipakai sebagai RASIO untuk P=8
UTIL_A7 = {8: dict(lut=4807, ff=6736), 16: dict(lut=5926, ff=7799), 32: dict(lut=8120, ff=10071)}
AXI_DELTA = dict(lut=8541 - 8147, ff=11107 - 10292)         # sistem AXI P32 (laporan axil_P32) dikurangi kv260_top P32: SmartConnect, MMCM, reset
# jalur kritis terukur = T - WNS (ns), post-route sistem penuh pada 299,997 / 333,82 MHz
TPATH = {16: 3.333 - 0.065, 32: 3.333 - 0.219}             # P=8 diasumsikan = P16 (jalur BRAM -> PE tidak bergantung P; asumsi)
FMAX_OOC = {16: (333.67, 340.02), 32: (333.89, None)}      # (terpenuhi, gagal) dari fmax.csv; satu run, WNS tidak monoton
HOLD_WHS = (0.010, 0.016)                                   # WHS terukur sistem penuh; tidak bergantung clock
# daya (laporan alat vectorless, 300 MHz, confidence Low): build/kv260/axil_P32/power_impl.rpt
PW = dict(total=2.975, static=0.325, ps8=2.415, mmcm=0.098, dyn=2.650)
PL_SCAL_P32 = PW["dyn"] - PW["ps8"] - PW["mmcm"]            # bagian PL yang ikut skala frekuensi
DPW_32_16 = (2.471 - 2.413) - (2.459 - 2.413)               # selisih daya dinamis P32 vs P16 (full_P32 vs full_P16)
# ---- asumsi (E) -------------------------------------------------------------------------------------------------------------------
FE_CYC_FRAME = 7_000        # siklus front-end per frame (rentang 6-8 rb, docs/vault/keputusan.md K-18; belum diukur)
TAIL_CYC = FE_CYC_FRAME + 2_000   # frame terakhir + pembacaan feat_buf ke CNN (2000 elemen; asumsi)
DS_GAP_CYC = 417            # jarak sampel dataset terukur di simulasi (test_ds_pacing)
HOST_US_PER_WRITE = 20e-3 / 8240 * 1e6   # papan: 8240 tulisan /dev/mem dalam 0,02 s -> 2,4 us (terukur, resolusi 10 ms)
FRAME_MIN_GAP = 404         # FRAME_LEN + 4 (kontrak frame_buf)
N_SAMPLES, HOP, FS = 8240, 160, 16_000
BCLK_NOM = 1.024e6


def util(p: int) -> dict:
    if p in UTIL_K26:
        return dict(UTIL_K26[p], src="T")
    r_lut = UTIL_A7[8]["lut"] / UTIL_A7[16]["lut"]; r_ff = UTIL_A7[8]["ff"] / UTIL_A7[16]["ff"]
    b = UTIL_K26[16]
    return dict(lut=round(b["lut"] * r_lut), ff=round(b["ff"] * r_ff), dsp=17, bram=12, src="E")


def pl_scal(p: int) -> float:
    """Daya dinamis PL yang ikut skala f pada 300 MHz (W), sistem AXI. P16/P8 diperkirakan dari selisih terukur P32-P16."""
    return {32: PL_SCAL_P32, 16: PL_SCAL_P32 - DPW_32_16, 8: PL_SCAL_P32 - DPW_32_16 * 1.5}[p]


def power_total(p: int, f: float) -> float:
    return PW["static"] + PW["ps8"] + PW["mmcm"] + pl_scal(p) * f / 300.0


def tpath(p: int) -> float:
    return TPATH.get(p, TPATH[16])


def timing_cell(p: int, f: float) -> str:
    wns = 1000.0 / f - tpath(p)
    if f > 333:
        return "gagal"
    tag = "T" if (f == 300 and p in TPATH) else "E"
    return f"{wns:+.2f} [{tag}]"


def i2s(f_mhz: float):
    cpb = round(f_mhz * 1e6 / BCLK_NOM)
    eff = 2 * (cpb // 2)                       # i2s_rx: periode BCLK = 2*floor(CPB/2) siklus
    bclk = f_mhz * 1e6 / eff
    return cpb, eff, bclk, bclk / 64


def table(head, rows) -> str:
    w = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    ln = lambda r: "| " + " | ".join(str(c).rjust(w[i]) if i else str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
    return "\n".join([ln(head), "|" + "|".join("-" * (x + 2) for x in w) + "|", *(ln(r) for r in rows)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    a = ap.parse_args()
    o = ["# Sapuan clock 10-300 MHz x P = 8/16/32 (perhitungan, bukan build)", "",
         "[T] terukur (laporan alat/simulasi), [E] estimasi (asumsi disebut). Target XCK26-SFVC784-2LV-C, sistem AXI4-Lite.", ""]

    o += ["## 1. Latensi", "",
          "CNN = siklus simulasi / f [T siklus, E turunan]. Umpan dataset = 8240 sampel x max(2,4 us host [T papan], 417 siklus / f). "
          "Ekor = frame terakhir front-end + baca feat_buf (9.000 siklus, [E]).", ""]
    rows = []
    for f in FREQS:
        r = [f"{f}"]
        for p in PS:
            r.append(f"{CNN_CYC[p] / f / 1e3:.2f}")
        feed = max(N_SAMPLES * HOST_US_PER_WRITE / 1e3, N_SAMPLES * DS_GAP_CYC / f / 1e3)
        r.append(f"{feed:.1f}")
        for p in PS:
            r.append(f"{feed + (TAIL_CYC + CNN_CYC[p]) / f / 1e3:.1f}")
        r.append(f"{500 + (TAIL_CYC + CNN_CYC[32]) / f / 1e3:.1f}")
        rows.append(r)
    o += [table(["f MHz", "CNN P8 ms", "CNN P16", "CNN P32", "umpan ms", "dataset P8 ms", "dataset P16", "dataset P32", "mikrofon P32 ms"], rows), "",
          "- Mode mikrofon: pengambilan 0,5 s ([T] 8000 sampel/16 kHz) mendominasi di semua P dan f; selisih P dan f hanya mengubah < 50 ms.",
          "- Mode dataset: di bawah ~170 MHz, jarak 417 siklus antar sampel (kontrak frame_buf) lebih lambat dari host dan menjadi penentu.", ""]

    o += ["## 2. Sumber daya (tidak bergantung f)", ""]
    rows = []
    for p in PS:
        u = util(p)
        rows.append([f"P={p}", f"{u['lut']:,}", f"{u['ff']:,}", u["dsp"], u["bram"], u["src"],
                     f"{u['lut'] + AXI_DELTA['lut']:,}", f"{u['ff'] + AXI_DELTA['ff']:,}", "E" if p != 32 else "T (P32)"])
    o += [table(["", "LUT kv260_top", "FF", "DSP", "BRAM36", "sumber", "LUT sistem AXI", "FF sistem AXI", "sumber AXI"], rows), "",
          "- P=8: LUT/FF diskalakan dari K26 P16 dengan rasio P8/P16 pada XC7A35T (0,81 dan 0,86). DSP dan BRAM tidak bergantung P (laporan alat).",
          f"- Sistem AXI = kv260_top + selisih terukur P32 (+{AXI_DELTA['lut']} LUT, +{AXI_DELTA['ff']} FF: SmartConnect, MMCM, reset); dipakai juga untuk P8/P16 [E].",
          "- Kapasitas XCK26: 117.120 LUT, 234.240 FF, 1.248 DSP, 144 BRAM36; semua P memakai < 8% LUT.", ""]

    o += ["## 3. Timing: perkiraan WNS (ns) dan Fmax", "",
          "WNS = 1/f - T_jalur, T_jalur = T - WNS terukur: P16 3,27 ns (sistem penuh), P32 3,11 ns; P8 diasumsikan = P16. "
          "[T] hanya pada 300 MHz (P16, P32). Ketidakpastian +-0,3 ns (P&R tidak monoton).", ""]
    rows = [[f"{f}"] + [timing_cell(p, f) for p in PS] for f in FREQS]
    o += [table(["f MHz", "P8", "P16", "P32"], rows), "",
          f"- Fmax terukur [T]: P16 OOC lolos 333,7 / gagal 340,0 MHz; sistem penuh P16 gagal 333,8 MHz (WNS -0,270), P32 lolos 333,8 (+0,018). P8 belum dibangun di K26.",
          f"- Hold (WHS) terukur +{HOLD_WHS[0]:.3f} s.d. +{HOLD_WHS[1]:.3f} ns [T], tidak bergantung f; tipis tetapi positif.",
          "- Titik 10-250 MHz tidak pernah dibangun di K26 (kecuali P16 OOC 244/250/270 MHz lolos): angka WNS di atas adalah ekstrapolasi.", ""]

    o += ["## 4. Daya (vectorless, confidence Low) dan energi", "",
          f"Total = statis {PW['static']} + PS8 {PW['ps8']} + MMCM {PW['mmcm']} (tetap) + PL(P) x f/300. PL(P32) = {PL_SCAL_P32:.3f} W pada 300 MHz [T], "
          f"P16 = P32 - {DPW_32_16:.3f} [T selisih], P8 = P16 - {DPW_32_16 / 2:.3f} [E]. Energi = daya total x waktu CNN.", ""]
    rows = []
    for f in FREQS:
        r = [f"{f}"]
        for p in PS:
            r.append(f"{power_total(p, f):.3f}")
        for p in PS:
            r.append(f"{power_total(p, f) * CNN_CYC[p] / f / 1e6 * 1e3:.2f}")
        rows.append(r)
    o += [table(["f MHz", "W P8", "W P16", "W P32", "mJ/inferensi P8", "mJ P16", "mJ P32"], rows), "",
          f"- PS8 ({PW['ps8']} W) = {PW['ps8'] / PW['total']:.0%} dari total dan tidak berubah dengan f atau P: menurunkan clock PL menghemat paling banyak "
          f"{pl_scal(32):.2f} W ({pl_scal(32) / PW['total']:.1%}).",
          "- Energi per inferensi (daya total x waktu) naik di f rendah karena PS8 dan statis menyala lebih lama; yang terkecil: f tinggi, P32.",
          "- Daya adalah estimasi Vivado, bukan pengukuran; PS8 pada beban nyata (Linux, DDR) bisa berbeda.", ""]

    o += ["## 5. I2S dan kendala waktu nyata (mode mikrofon)", "",
          "CPB = round(f/1,024 MHz) seperti synth_axil.tcl; periode BCLK sebenarnya 2*floor(CPB/2) siklus (i2s_rx) [T dari RTL]. "
          "Margin frame_buf = (f/16 kHz)/404 [kontrak]; beban front-end = 7.000 siklus [E] / (siklus per hop).", ""]
    rows = []
    for f in FREQS:
        cpb, eff, bclk, fs = i2s(f)
        cps = f * 1e6 / fs
        rows.append([f"{f}", cpb, eff, f"{bclk / 1e6:.4f}", f"{fs / 1e3:.3f}", f"{(fs / FS - 1) * 100:+.2f}%",
                     f"{cps:.0f}", f"{cps / FRAME_MIN_GAP:.2f}x", f"{FE_CYC_FRAME / (cps * HOP):.1%}"])
    fmin = FRAME_MIN_GAP * FS / 1e6
    o += [table(["f MHz", "CPB", "periode BCLK", "BCLK MHz", "fs kHz", "galat fs", "siklus/sampel", "margin frame_buf", "beban front-end"], rows), "",
          f"- Batas bawah clock untuk mikrofon: f >= {fmin:.2f} MHz (404 siklus/sampel pada 16 kHz) [kontrak frame_buf]; front-end sendiri hanya butuh sekitar "
          f"{FE_CYC_FRAME / (HOP / FS) / 1e6:.2f} MHz. MMCM ultraScale+ -2 dari ingatan: VCO 800-1600 MHz, bagi hingga 128 -> f minimum sekitar 6,25 MHz (verifikasi DS925).",
          f"- Temuan: pada 300 MHz CPB = 293 (ganjil) sehingga periode BCLK 292 siklus, BCLK {i2s(299.997)[2] / 1e6:.4f} MHz dan fs {i2s(299.997)[3] / 1e3:.3f} kHz "
          f"({(i2s(299.997)[3] / FS - 1) * 100:+.2f}%), bukan 15,998 kHz seperti tertulis di README. Tidak merusak (INMP441 menerima kisaran fs lebar), tetapi catatan perlu dikoreksi.", ""]

    o += ["## 6. Slew I/O dan clock (estimasi orde-besaran)", "",
          "Slew keluaran Pmod ditentukan standar I/O, SLEW, DRIVE, dan beban, bukan clock inti. XDC: LVCMOS33, SLEW SLOW, DRIVE 4 mA. Tanpa model IBIS/report_ssn, hanya rentang yang bisa diberikan:", ""]
    lo, hi = 2.2 * 100 * 10e-12, 2.2 * 825 * 40e-12
    half = 1 / (2 * i2s(299.997)[2])
    o += [f"- t_r ~ 2,2 x R x C. R efektif 100-825 ohm (batas atas = 3,3 V / 4 mA), C beban 10-40 pF (jumper 10-15 cm + pin) -> t_r sekitar {lo * 1e9:.0f} sampai {hi * 1e9:.0f} ns [E].",
          f"- BCLK sekitar 1,03 MHz memiliki setengah periode {half * 1e9:.0f} ns: tepi terburuk {hi / half:.0%} dari setengah periode, jadi tidak membatasi pada f mana pun 10-300 MHz "
          "karena BCLK diturunkan ulang dari f (CPB), bukan ikut naik.",
          "- Slew menjadi relevan bila BCLK dinaikkan (INMP441 maks. sekitar 3,2 MHz dari ingatan datasheet; setengah periode sekitar 156 ns): tepi terburuk sekitar 47%. Ukur dengan osiloskop.",
          "- Slew clock internal (BUFG/MMCM) dan jitter tidak dapat diestimasi dari data yang ada; sudah tercakup dalam WNS terukur pada 300 MHz.", ""]

    o += ["## 7. Ringkasan", "",
          "1. **Latensi**: P32 @300 MHz 0,41 ms, P16 0,76 ms, P8 1,5 ms; di 10 MHz P32 12,3 ms. Semuanya jauh di bawah pengambilan 0,5 s: P dan f tidak mengubah latensi yang dirasakan pengguna.",
          "2. **Sumber daya**: P tidak mengubah DSP dan BRAM; LUT berbeda sekitar 4.8k (P8) sampai 8.1k (P32), semuanya < 8% perangkat.",
          "3. **Timing**: lolos terukur sampai 300 MHz (P16, P32); gagal di atas ~334 MHz. P8 belum pernah dibangun.",
          "4. **Daya**: didominasi PS8 (2,4 W). Menurunkan clock PL menghemat paling banyak ~0,13 W; tidak sepadan dengan risiko demo.",
          "5. **Mikrofon**: clock efektif dari ~6,5 MHz; di bawah itu frame_buf kehilangan sampel.", ""]
    text = "\n".join(o) + "\n"
    print(text)
    if a.out:
        p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        print("disimpan:", p)


if __name__ == "__main__":
    main()
