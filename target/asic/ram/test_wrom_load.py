"""Tes jalur muat wrom_sky130 (PRELOAD=0): tulis cnn_wrom.mem lewat wl_* per lane 32 bit, lalu baca semua alamat lewat en/addr
dan bandingkan dengan berkas; juga cek dout ditahan saat en=0. Dijalankan dari check_ram_wrapper.py (WROM=1)."""
import pathlib
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

ROOT = pathlib.Path(__file__).resolve().parents[3]


@cocotb.test()
async def load_then_read(dut):
    words = [int(l, 16) for l in (ROOT / "tb/vectors/cnn/cnn_wrom.mem").read_text().split("\n") if l.strip() and not l.startswith("//")]
    width, depth = int(dut.WIDTH.value), int(dut.DEPTH.value)
    lanes = width // 32
    lb = max(1, (lanes - 1).bit_length())
    assert len(words) == depth, f"{len(words)} kata di berkas, DEPTH={depth}"
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.en.value = 0; dut.addr.value = 0; dut.wl_we.value = 0; dut.wl_addr.value = 0; dut.wl_data.value = 0
    await RisingEdge(dut.clk)
    for r, w in enumerate(words):
        for l in range(lanes):
            dut.wl_we.value = 1
            dut.wl_addr.value = (r << lb) | l
            dut.wl_data.value = (w >> (32 * l)) & 0xFFFFFFFF
            await RisingEdge(dut.clk)
    dut.wl_we.value = 0
    await RisingEdge(dut.clk)
    bad = 0
    for r in list(range(depth)) + [depth - 1]:
        dut.en.value = 1; dut.addr.value = r
        await RisingEdge(dut.clk)
        dut.en.value = 0
        await RisingEdge(dut.clk)          # satu siklus tanpa en: dout harus ditahan
        await ReadOnly()
        got = dut.dout.value
        if not got.is_resolvable or int(got) != words[r]:
            bad += 1
            if bad <= 5:
                dut._log.error(f"addr {r}: dapat {got}, harap {words[r]:0{width // 4}x}")
        await RisingEdge(dut.clk)
    assert bad == 0, f"{bad} alamat salah"
    dut._log.info(f"{depth} alamat x {lanes} lane cocok setelah muat lewat wl_*")
