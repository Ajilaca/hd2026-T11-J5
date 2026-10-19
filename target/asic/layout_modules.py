"""Layout OpenLane (sky130A) untuk modul tanpa RAM. Dari ROOT repo: python target/asic/layout_modules.py [modul ...]
Per modul: sv2v -> Verilog, config OpenLane (clock 25 ns = 40 MHz (env CLK_NS), utilisasi inti 30%), jalankan OpenLane di Docker
(satu per satu). Bila pin melebihi keliling die (PPL-0024) die diperbesar sesuai saran alat dan dijalankan ulang.
Hasil: $SUARATB_DATA/build/asic/<modul>/runs/<tag>/ ; ringkasan angka ke stdout (dari metrics.json).
FIX=1: jalankan ulang modul yang sudah ada (netlist dan die sama) dengan perbaikan antena dan slew/kapasitansi, tag "fix".
"""
from __future__ import annotations
import json, math, os, pathlib, re, shutil, subprocess, sys

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
ROOT = pathlib.Path(__file__).resolve().parents[2]
SV2V = os.environ.get("SV2V") or shutil.which("sv2v") or "/data/tools/sv2v/sv2v-Linux/sv2v"
IMG = "ghcr.io/efabless/openlane2:2.3.10"
PKG = ["rtl/common/suaratb_pkg.sv"]
SRC = {  # modul: berkas RTL (selain paket)
    "preemph": ["rtl/audio/preemph.sv"], "i2s_rx": ["rtl/audio/i2s_rx.sv"], "cough_det": ["rtl/detect/cough_det.sv"],
    "window": ["rtl/common/rom_sync.sv", "rtl/dsp/window.sv"], "power": ["rtl/dsp/power.sv"],
    "mel": ["rtl/common/rom_sync.sv", "rtl/dsp/mel.sv"], "log_q": ["rtl/common/rom_sync.sv", "rtl/dsp/log_q.sv"],
    "requant": ["rtl/cnn/requant.sv"], "pe_array": ["rtl/cnn/pe_array.sv"],
    "cnn_top": ["rtl/common/rom_sync.sv", "rtl/common/ram_sdp.sv", "rtl/cnn/pe_array.sv", "rtl/cnn/requant.sv", "rtl/cnn/gap.sv",
                "rtl/cnn/cnn_ctrl.sv", "rtl/cnn/cnn_top.sv"], "gap": ["rtl/cnn/gap.sv"],
    "uart_bridge": ["rtl/sys/uart_rx.sv", "rtl/sys/uart_tx.sv", "rtl/sys/uart_bridge.sv"],
}
PP = int(os.environ.get("P", "16"))               # P untuk modul bergantung-P (pe_array, requant); P != 16 -> direktori <modul>_P<P>
CNN_PKG = D / f"build/synth/P{PP}/cnn_cfg_pkg.sv"
NEEDS_CNN = {"requant", "gap", "pe_array", "cnn_top"}


def pins(v: str) -> int:
    head = v[v.index("module"): v.index(");")]
    n = 0
    for m in re.finditer(r"\b(input|output|inout)\b\s*(?:wire|reg|signed)?\s*(?:\[(\d+):(\d+)\])?", head):
        n += (abs(int(m.group(2)) - int(m.group(3))) + 1) if m.group(2) else 1
    return n


def run_ol(w: pathlib.Path, cfg: dict, tag: str) -> pathlib.Path:
    (w / "config.json").write_text(json.dumps(cfg, indent=1))
    log = w / f"{tag}.log"
    subprocess.run(["docker", "run", "--rm", *(["--memory", os.environ["DOCKER_MEM"], "--memory-swap", os.environ["DOCKER_MEM"]] if os.environ.get("DOCKER_MEM") else []), *(["--cpus", os.environ["DOCKER_CPUS"]] if os.environ.get("DOCKER_CPUS") else []), "-v", f"{w}:/work", "-v", f"{pathlib.Path.home()}/.volare:/pdk", "-e", "PDK_ROOT=/pdk",
                    "-w", "/work", IMG, "openlane", "--pdk-root", "/pdk", "--pdk", "sky130A", "--run-tag", tag, "config.json"],
                   stdout=log.open("w"), stderr=subprocess.STDOUT)
    return log


def summary(w: pathlib.Path, tag: str, name: str, npins: int) -> None:
    f = w / "runs" / tag / "final/metrics.json"
    if not f.exists():
        print(f"{name}: GAGAL (lihat {w / (tag + '.log')})", flush=True); return
    m = json.load(open(f))
    g = lambda k: m.get(k)
    print(f"{name}: pin={g('design__io')} sel={g('design__instance__count__stdcell')} area_sel={g('design__instance__area'):.0f}um2 "
          f"die={g('design__die__area'):.0f}um2 util={g('design__instance__utilization'):.3f} DRC(magic/klayout)={g('magic__drc_error__count')}/{g('klayout__drc_error__count')} "
          f"LVS={g('design__lvs_error__count')} setup_ws={g('timing__setup__ws'):.2f} hold_ws={g('timing__hold__ws'):.2f} (1e+39 = tanpa jalur terkekang) "
          f"vio(setup/hold)={g('timing__setup_vio__count')}/{g('timing__hold_vio__count')} antena={g('antenna__violating__nets')} daya={g('power__total'):.4f}W", flush=True)


def layout(name: str) -> None:
    w = D / "build/asic" / (name if PP == 16 or name not in ("pe_array", "requant", "cnn_top") else f"{name}_P{PP}")
    if any((w / "runs" / t / "final/metrics.json").exists() for t in ("c1", "c2")):
        print(f"{name}: sudah ada, dilewati", flush=True); return
    w.mkdir(parents=True, exist_ok=True)
    files = PKG + ([str(CNN_PKG)] if name in NEEDS_CNN else []) + SRC[name]
    v = subprocess.run([SV2V, "-DSYNTHESIS", "--top", name] + files, cwd=ROOT, capture_output=True, text=True)
    if v.returncode:
        print(f"{name}: sv2v gagal: {v.stderr[:200]}", flush=True); return
    text = v.stdout.replace("rtl/mem/", "/work/mem/").replace("tb/vectors/cnn/", "/work/mem/")
    (w / f"{name}.v").write_text(text)
    shutil.copytree(ROOT / "rtl/mem", w / "mem", dirs_exist_ok=True)
    for f in (D / f"build/synth/P{PP}").glob("cnn_*.mem"):
        shutil.copy(f, w / "mem" / f.name)
    n = 0
    cfg = {"DESIGN_NAME": name, "VERILOG_FILES": f"dir::{name}.v", "CLOCK_PORT": "clk" if re.search(r"input\s+wire\s+clk\b", text) else None,
           "CLOCK_PERIOD": float(os.environ.get("CLK_NS", "25")), "FP_SIZING": "relative", "FP_CORE_UTIL": int(os.environ.get("CORE_UTIL", "30")), "PL_TARGET_DENSITY_PCT": 40, "RUN_LINTER": False}
    cfg = {k: v for k, v in cfg.items() if v is not None}
    log = run_ol(w, cfg, "c1")
    t = log.read_text()
    m = re.search(r"Increase the die perimeter from\s+[\d.]+um\s+to\s+([\d.]+)um", t)
    if m:                                         # terlalu banyak pin: die persegi dengan keliling yang disarankan
        side = math.ceil(float(m.group(1)) / 4 / 10) * 10 + 10
        cfg.update({"FP_SIZING": "absolute", "DIE_AREA": [0, 0, side, side]}); cfg.pop("FP_CORE_UTIL")
        subprocess.run(["docker", "run", "--rm", "-v", f"{w}:/w", "--entrypoint", "sh", IMG, "-c", "rm -rf /w/runs/c1 /w/c1.log"])  # c1 gagal (pin), tidak dipakai
        run_ol(w, cfg, "c2"); summary(w, "c2", name, n)
    else:
        summary(w, "c1", name, n)


# Perbaikan antena (dioda heuristik + iterasi perbaikan antena lebih banyak) dan slew/kapasitansi (buffer pada kabel panjang,
# margin perbaikan lebih besar, perbaikan desain diulang setelah global routing). RTL dan netlist sintesis tidak berubah.
FIX_CFG = {"RUN_HEURISTIC_DIODE_INSERTION": True, "DIODE_ON_PORTS": "in", "GRT_ANTENNA_ITERS": 10, "GRT_ANTENNA_MARGIN": 15,
           "DESIGN_REPAIR_MAX_WIRE_LENGTH": 400, "GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH": 400,
           "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 30,
           "RUN_POST_GRT_DESIGN_REPAIR": True, "GRT_DESIGN_REPAIR_MAX_SLEW_PCT": 30, "GRT_DESIGN_REPAIR_MAX_CAP_PCT": 30}


def fix(name: str) -> None:
    w = D / "build/asic" / (name if PP == 16 or name not in ("pe_array", "requant", "cnn_top") else f"{name}_P{PP}")
    if (w / "runs/fix/final/metrics.json").exists():
        print(f"{name}: fix sudah ada, dilewati", flush=True); return
    base = w / "config_base.json"                        # config run asli (c1/c2), dipakai untuk pemulihan bila fix dibuang
    if not base.exists():
        shutil.copy(w / "config.json", base)
    cfg = json.loads(base.read_text())
    cfg.update(FIX_CFG)
    run_ol(w, cfg, "fix"); summary(w, "fix", name, 0)


if __name__ == "__main__":
    for mod in sys.argv[1:] or list(SRC):
        fix(mod) if os.environ.get("FIX") == "1" else layout(mod)
    print("SELESAI")
