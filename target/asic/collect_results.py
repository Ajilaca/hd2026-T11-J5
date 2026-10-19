"""Kumpulkan hasil layout modul dari $SUARATB_DATA/build/asic ke repo dan (opsional) paket serah-terima.
Dari ROOT repo: python target/asic/collect_results.py [--pack]
  repo  : target/asic/results/metrics/<layout>.json (salinan final/metrics.json) + target/asic/results/metrics.csv (ringkasan)
  --pack: $SUARATB_DATA/handoff/suaratb_asic_layout.zip berisi final/{gds,def,nl,pnl,sdc,spef/nom,lef,lib,metrics.*} per layout
          (berkas internal OpenLane seperti odb, mag, sdf tidak ikut). PNG berlabel layer: target/asic/render_layout.py.
Satu run per layout di runs/ (c1, c2, atau fix); bila lebih dari satu, run dengan final/metrics.json terbaru dipakai.
"""
from __future__ import annotations
import csv, json, os, pathlib, shutil, sys, zipfile

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
ROOT = pathlib.Path(__file__).resolve().parents[2]
LAYOUTS = ["i2s_rx", "preemph", "uart_bridge", "gap", "window", "log_q", "cough_det", "power", "mel",
           "requant", "requant_P32", "pe_array", "pe_array_P32"]
COLS = {  # kolom csv: kunci metrics.json OpenLane
    "pin": "design__io", "sel": "design__instance__count__stdcell", "area_sel_um2": "design__instance__area__stdcell",
    "die_um2": "design__die__area", "util": "design__instance__utilization",
    "drc_magic": "magic__drc_error__count", "drc_klayout": "klayout__drc_error__count", "lvs": "design__lvs_error__count",
    "xor": "design__xor_difference__count", "route_drc": "route__drc_errors",
    "setup_ws_ns": "timing__setup__ws", "hold_ws_ns": "timing__hold__ws",
    "setup_vio": "timing__setup_vio__count", "hold_vio": "timing__hold_vio__count",
    "antena_net": "antenna__violating__nets", "slew_vio": "design__max_slew_violation__count",
    "cap_vio": "design__max_cap_violation__count", "fanout_vio": "design__max_fanout_violation__count",
    "daya_W": "power__total", "kabel_um": "route__wirelength",
}
PACK = ["gds", "def", "nl", "pnl", "sdc", "spef/nom", "lef", "lib"]


def final_dir(name: str) -> pathlib.Path:
    runs = sorted((D / "build/asic" / name / "runs").glob("*/final/metrics.json"), key=lambda p: p.stat().st_mtime)
    if not runs:
        sys.exit(f"{name}: tidak ada final/metrics.json")
    return runs[-1].parent


def main(pack: bool) -> None:
    out = ROOT / "target/asic/results"
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    rows = []
    for name in LAYOUTS:
        f = final_dir(name)
        shutil.copy(f / "metrics.json", out / "metrics" / f"{name}.json")
        m = json.loads((f / "metrics.json").read_text())
        rows.append({"layout": name, "run": f.parent.name, **{c: m.get(k) for c, k in COLS.items()}})
    with open(out / "metrics.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["layout", "run", *COLS]); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} layout -> {out / 'metrics.csv'}")
    if pack:
        z = D / "handoff/suaratb_asic_layout.zip"
        z.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(out / "metrics.csv", "suaratb_asic_layout/metrics.csv")
            for name in LAYOUTS:
                f = final_dir(name)
                for part in PACK + ["metrics.json", "metrics.csv"]:
                    p = f / part
                    for x in ([p] if p.is_file() else sorted(p.rglob("*")) if p.is_dir() else []):
                        if x.is_file():
                            zf.write(x, f"suaratb_asic_layout/{name}/{x.relative_to(f)}")
        print(f"paket -> {z} ({z.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main("--pack" in sys.argv[1:])
