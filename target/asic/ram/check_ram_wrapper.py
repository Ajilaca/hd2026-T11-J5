"""Cek wrapper RAM makro sky130: jalankan tes cocotb cnn_top (bit-exact vs golden) dengan ram_sdp diganti ram_sdp_sky130 + model makro OpenRAM.
Dari ROOT repo: SIM=icarus .venv/bin/python target/asic/ram/check_ram_wrapper.py     (env CNN_CASES="noise3,cough" untuk membatasi kasus)
WROM=1: ROM bobot juga diganti makro (wrom_sky130, salinan cnn_top dari patch_wrom.py, model diisi PRELOAD), lalu jalur muat
wl_* diuji terpisah (test_wrom_load.py: muat lewat port, baca semua alamat, bandingkan dengan cnn_wrom.mem).
Model makro dari PDK memakai VERBOSE=1 (mencetak tiap akses); salinan dengan VERBOSE=0 dibuat di $SUARATB_DATA/build/asic/ram_model.
"""
import glob, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SIM", "icarus")
from tb.common.runner import rtl_files, run, mem_param

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
src = glob.glob(os.path.expanduser("~/.volare/volare/sky130/versions/*/sky130A/libs.ref/sky130_sram_macros/verilog/sky130_sram_2kbyte_1rw1r_32x512_8.v"))[0]
out = D / "build/asic/ram_model"
out.mkdir(parents=True, exist_ok=True)
model = out / "sky130_sram_2kbyte_1rw1r_32x512_8_quiet.v"
model.write_text(pathlib.Path(src).read_text().replace("parameter VERBOSE = 1 ;", "parameter VERBOSE = 0 ;"))
files = [f for f in rtl_files(sim="icarus") if not f.endswith("ram_sdp.sv")]
files += [str(ROOT / "target/asic/ram/ram_sdp_sky130.sv"), str(model)]
if os.environ.get("WROM") == "1":
    sys.path.insert(0, str(ROOT / "target/asic/ram"))
    from patch_wrom import patched_cnn_top
    top = patched_cnn_top(out)
    files = [str(top) if f.endswith("rtl/cnn/cnn_top.sv") else f for f in files] + [str(ROOT / "target/asic/ram/wrom_sky130.sv")]
    run("wrom_sky130", "target.asic.ram.test_wrom_load", parameters={"PRELOAD": 0},
        sources=[str(ROOT / "target/asic/ram/wrom_sky130.sv"), str(model)], tag="_load")
run("cnn_top", "test_cnn_top", parameters={"INIT_W": mem_param("../../tb/vectors/cnn/cnn_wrom.mem")}, sources=files, tag="_wrom" if os.environ.get("WROM") == "1" else "_macro")
