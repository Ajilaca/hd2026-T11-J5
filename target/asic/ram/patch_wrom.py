"""Salinan cnn_top.sv untuk flow ASIC: instans u_wrom (rom_sync) diganti wrom_sky130 dan port muat bobot wl_* ditambahkan.
rtl/cnn/cnn_top.sv tidak diubah; hasilnya ditulis ke direktori build. Dipakai layout_cnn_macro.py (WROM=sram) dan check_ram_wrapper.py.
"""
from __future__ import annotations
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
PORTS_OLD = "  output logic signed [15:0]  logit\n);"
PORTS_NEW = ("  output logic signed [15:0]  logit,\n"
             "  input  logic                wl_we,      // muat bobot ke makro wrom_sky130 (target/asic)\n"
             "  input  logic [15:0]         wl_addr,\n"
             "  input  logic [31:0]         wl_data\n);")
INST_OLD = "rom_sync #(.WIDTH(P*8), .DEPTH(WROM_DEPTH), .INIT_FILE(INIT_W)) u_wrom (\n"
INST_NEW = ("wrom_sky130 #(.WIDTH(P*8), .DEPTH(WROM_DEPTH), .INIT_FILE(INIT_W)) u_wrom (\n"
            "    .wl_we(wl_we), .wl_addr(wl_addr), .wl_data(wl_data),\n")


def patched_cnn_top(out: pathlib.Path) -> pathlib.Path:
    s = (ROOT / "rtl/cnn/cnn_top.sv").read_text()
    for a, b in ((PORTS_OLD, PORTS_NEW), (INST_OLD, INST_NEW)):
        if s.count(a) != 1:
            raise SystemExit(f"patch_wrom: pola tidak ditemukan tepat sekali: {a!r}")
        s = s.replace(a, b)
    out.mkdir(parents=True, exist_ok=True)
    f = out / "cnn_top_wrom.sv"
    f.write_text(s)
    return f
