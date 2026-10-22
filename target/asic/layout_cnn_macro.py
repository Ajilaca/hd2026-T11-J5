"""Layout OpenLane (sky130A, 25 ns) untuk cnn_top dengan RAM = makro SRAM sky130 (wrapper target/asic/ram/ram_sdp_sky130.sv).
Dari ROOT repo: WROM=sram P=16 python target/asic/layout_cnn_macro.py [tag]
  env: P (16/32), SV2V (path sv2v, bawaan: sv2v di PATH), DOCKER_MEM, DOCKER_CPUS, CLK_NS, STA_THREADS, KLAYOUT_THREADS,
       SKIP_STEPS (id langkah OpenLane dipisah koma, mis. "Magic.WriteLEF,Odb.CheckDesignAntennaProperties"), TRDRC_ERR.
  butuh: Docker + citra openlane2 2.3.10, PDK sky130A lewat volare di ~/.volare, $SUARATB_DATA/build/synth/P<P>/
         (target/prep_synth.py). Tahap akhir (Magic WriteLEF, XOR, DRC) butuh > 8 GB RAM untuk 14 makro.
Keluaran WROM=sram: $SUARATB_DATA/build/asic/cnn_top/p<P>/ (masukan) dan .../p<P>/run/ (hasil OpenLane, dipindah dari runs/<tag>).
Mode lain (diagnosis lama): cnn_top_macro*. Penempatan makro manual: baris atas di tepi atas, sisanya di tepi bawah, logika di tengah.
"""
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = int(os.environ.get("P", "16"))
WROM = os.environ.get("WROM") == "sram"   # ROM bobot sebagai 8 makro SRAM + port muat wl_* (ram/wrom_sky130.sv, ram/patch_wrom.py)
TAG = sys.argv[1] if len(sys.argv) > 1 else (f"p{P}" if WROM else "m1")
GAP = int(os.environ.get("GAP", "40"))              # celah antar-makro (um)
if WROM:
    W = D / "build/asic/cnn_top" / f"p{P}"
else:
    W = D / "build/asic" / ("cnn_top_macro" + (f"_P{P}" if P != 16 else "") + (f"_g{GAP}" if GAP != 40 else "")
                             + ("_stub" if os.environ.get("WROM_STUB") == "1" else ""))
SV2V = os.environ.get("SV2V") or shutil.which("sv2v") or "/data/tools/sv2v/sv2v-Linux/sv2v"
IMG = "ghcr.io/efabless/openlane2:2.3.10"
MAC = "sky130_sram_2kbyte_1rw1r_32x512_8"
VOLARE = pathlib.Path.home() / ".volare/volare/sky130/versions"
HASH = next(VOLARE.iterdir()).name
MROOT = f"/pdk/volare/sky130/versions/{HASH}/sky130A/libs.ref/sky130_sram_macros"
MW, MH = 683.1, 416.54
WROM_DEPTH = {16: 921, 32: 489}                # dari build/synth/P<P>/cnn_cfg_pkg.sv
COLS, ROWS = (4, 4) if WROM else (3, 2)
BAND = int(os.environ.get("BAND", "960"))      # tinggi pita logika (um) di antara baris makro atas dan bawah
DIE_W = int(COLS * (MW + GAP) + GAP + 40)
DIE_H = int(ROWS * (MH + GAP) + GAP + BAND)


SKIP = [x for st in os.environ.get("SKIP_STEPS", "").split(",") if st for x in ("--skip", st)]


def main() -> None:
    W.mkdir(parents=True, exist_ok=True)
    files = ["rtl/common/suaratb_pkg.sv", str(D / f"build/synth/P{P}/cnn_cfg_pkg.sv"), "rtl/common/rom_sync.sv", "target/asic/ram/ram_sdp_sky130.sv",
             "rtl/cnn/pe_array.sv", "rtl/cnn/requant.sv", "rtl/cnn/gap.sv", "rtl/cnn/cnn_ctrl.sv", "rtl/cnn/cnn_top.sv"]
    if WROM:
        sys.path.insert(0, str(ROOT / "target/asic/ram"))
        from patch_wrom import patched_cnn_top
        files[-1] = str(patched_cnn_top(W))
        files.insert(-1, "target/asic/ram/wrom_sky130.sv")
    r = subprocess.run([SV2V, "-DSYNTHESIS", "--top", "cnn_top"] + files, cwd=ROOT, capture_output=True, text=True, check=True)
    v = r.stdout.replace("rtl/mem/", "/work/mem/").replace("tb/vectors/cnn/", "/work/mem/")
    if os.environ.get("WROM_STUB") == "1":   # diagnosis saja: ROM bobot diganti stub kecil (keluaran tidak fungsional)
        i = v.index(") u_wrom("); j = v.rindex("rom_sync #(", 0, i)
        v = v[:j] + "wrom_stub #(" + v[j + len("rom_sync #("):] + """
module wrom_stub #(parameter WIDTH = 8, parameter DEPTH = 256, parameter INIT_FILE = "") (
  input clk, input en, input [$clog2(DEPTH)-1:0] addr, output reg [WIDTH-1:0] dout);
  always @(posedge clk) if (en) dout <= {32{addr}};
endmodule
"""
    (W / "cnn_top.v").write_text(v)
    (W / "mem").mkdir(exist_ok=True)
    for f in list((ROOT / "rtl/mem").glob("*.mem")) + list((D / f"build/synth/P{P}").glob("cnn_*.mem")):
        shutil.copy(f, W / "mem" / f.name)
    (W / "bb.v").write_text(f"""(* blackbox *)
module {MAC} (clk0, csb0, web0, wmask0, addr0, din0, dout0, clk1, csb1, addr1, dout1);
  input clk0; input csb0; input web0; input [3:0] wmask0; input [8:0] addr0; input [31:0] din0; output [31:0] dout0;
  input clk1; input csb1; input [8:0] addr1; output [31:0] dout1;
endmodule
""")
    names = [f"u_ramB.g_bank[{b}].u_m" for b in range(4)] + [f"u_ramA.g_bank[{b}].u_m" for b in range(2)]
    if WROM:
        lanes, banks = P * 8 // 32, -(-WROM_DEPTH[P] // 512)
        names += [f"u_wrom.g_bank[{b}].g_lane[{l}].u_m" for b in range(banks) for l in range(lanes)]
    assert len(names) <= COLS * ROWS
    inst = {}
    top_rows = ROWS - ROWS // 2 if WROM else ROWS - 1   # baris atas di tepi atas; sisanya di tepi bawah; logika di pita tengah
    for i, n in enumerate(names):
        row, col = divmod(i, COLS)
        x = GAP + col * (MW + GAP)
        if os.environ.get("SPLIT", "1") == "1" and row >= top_rows:
            y = GAP + (ROWS - 1 - row) * (MH + GAP)
        else:
            y = DIE_H - GAP - (row + 1) * MH - row * GAP
        inst[n] = {"location": [round(x, 2), round(y, 2)], "orientation": "N"}
    kt = os.environ.get("KLAYOUT_THREADS")
    cfg = {"DESIGN_NAME": "cnn_top", "VERILOG_FILES": "dir::cnn_top.v", "CLOCK_PORT": "clk", "CLOCK_PERIOD": float(os.environ.get("CLK_NS", "25")),
           "FP_SIZING": "absolute", "DIE_AREA": [0, 0, DIE_W, DIE_H], "PL_TARGET_DENSITY_PCT": int(os.environ.get("PL_DENS", "25")), "GPL_CELL_PADDING": int(os.environ.get("PAD", "2")), "DPL_CELL_PADDING": int(os.environ.get("PAD", "2")), "RUN_LINTER": False,
           "GRT_ADJUSTMENT": float(os.environ.get("GRT_ADJ", "0.3")), "STA_THREADS": int(os.environ.get("STA_THREADS", "2")), "ERROR_ON_TR_DRC": os.environ.get("TRDRC_ERR", "1") == "1",
           # Makro OpenRAM: mode "macro" (kotak hitam + penunjuk GDS) menghasilkan GDS Magic rusak ("Structure name not found");
           # mode PDK membaca GDS makro penuh. Saat membaca, Magic tetap melapor layer penanda OpenRAM yang tidak dikenalnya
           # (22/21, 22/22, 33/42, 33/43, 235/0), jadi galat Magic tidak fatal; kebenaran GDS diperiksa XOR terhadap KLayout.
           "MAGIC_MACRO_STD_CELL_SOURCE": "PDK", "MAGIC_CAPTURE_ERRORS": False,
           "PDN_MACRO_CONNECTIONS": ["u_ram.* VPWR VGND vccd1 vssd1"] + (["u_wrom.* VPWR VGND vccd1 vssd1"] if WROM else []),
           "MACROS": {MAC: {"gds": [f"{MROOT}/gds/{MAC}.gds"], "lef": [f"{MROOT}/lef/{MAC}.lef"],
                            "lib": {"*": f"{MROOT}/lib/{MAC}_TT_1p8V_25C.lib"}, "vh": ["dir::bb.v"], "spice": [f"{MROOT}/spice/{MAC}.spice"], "instances": inst}}}
    if kt:
        cfg.update({"KLAYOUT_XOR_THREADS": int(kt), "KLAYOUT_DRC_THREADS": int(kt)})
    (W / "config.json").write_text(json.dumps(cfg, indent=1))
    cmd = ["docker", "run", "--rm"] + (["--memory", os.environ["DOCKER_MEM"], "--memory-swap", os.environ["DOCKER_MEM"]] if os.environ.get("DOCKER_MEM") else []) \
        + (["--cpus", os.environ["DOCKER_CPUS"]] if os.environ.get("DOCKER_CPUS") else []) \
        + ["-v", f"{W}:/work", "-v", f"{pathlib.Path.home()}/.volare:/pdk", "-e", "PDK_ROOT=/pdk", "-w", "/work", IMG,
           "openlane", "--pdk-root", "/pdk", "--pdk", "sky130A", "--run-tag", TAG, "config.json"] + SKIP
    subprocess.run(cmd, stdout=(W / f"{TAG}.log").open("w"), stderr=subprocess.STDOUT)
    if WROM and (W / "runs" / TAG / "final").exists() and not (W / "run").exists():
        subprocess.run(["docker", "run", "--rm", "-v", f"{W}:/work", IMG, "mv", f"/work/runs/{TAG}", "/work/run"], check=True)
        subprocess.run(["docker", "run", "--rm", "-v", f"{W}:/work", IMG, "rmdir", "/work/runs"])
    f = (W / "run" if WROM else W / "runs" / TAG) / "final/metrics.json"
    if not f.exists():
        print(f"cnn_top_macro P={P}: GAGAL (lihat {W / (TAG + '.log')})"); return
    m = json.load(open(f)); g = m.get
    print(f"cnn_top_macro P={P}: pin={g('design__io')} sel={g('design__instance__count__stdcell')} area_sel={g('design__instance__area__stdcell')}um2 "
          f"makro={g('design__instance__count__macros')} die={g('design__die__area')}um2 DRC={g('magic__drc_error__count')}/{g('klayout__drc_error__count')} LVS={g('design__lvs_error__count')} "
          f"setup_ws={g('timing__setup__ws')} hold_ws={g('timing__hold__ws')} vio={g('timing__setup_vio__count')}/{g('timing__hold_vio__count')} antena={g('antenna__violating__nets')} daya={g('power__total')}")


if __name__ == "__main__":
    main()
