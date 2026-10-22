"""cocotb: suaratb_axil_top (antarmuka host AXI4-Lite pengganti UART). Register, protokol AXI, dan klip dataset -> logit vs golden.

    python -m tb.sys.test_axil                 # semua uji (Icarus; SIM=icarus)
    AXIL_CASES=cough python -m tb.sys.test_axil   # satu kasus dataset saja (lebih cepat)
    AXIL_MIC=1 python -m tb.sys.test_axil         # tambah uji mode mikrofon (lama, ~12 juta siklus)
Sumber tambahan di luar rtl/: target/kv260/axi/rtl/axil_ctrl.v dan suaratb_axil_top.sv.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import cocotb
import numpy as np
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, with_timeout

from golden import params
from golden.blocks import cnn as C
from golden.blocks import frontend as F
from golden.blocks.cough_det import hop_energy, cough_det
from golden.blocks.preemph import preemph
from tb.common import vec
from tb.common.cocotb_utils import start_clock, reset
from tb.common.golden_model import random_calibrated_model

ROOT = pathlib.Path(__file__).resolve().parents[2]
AXI_SRC = [str(ROOT / "target/kv260/axi/rtl/axil_ctrl.v"), str(ROOT / "target/kv260/axi/rtl/suaratb_axil_top.sv")]
CPBCLK = 8                                  # clk per BCLK I2S pada simulasi (512 siklus/sampel >= 404)
N_SAMPLES = params.CLIP_SAMPLES_PADDED
DS_GAP = params.FRAME_LEN + 16
MAX_WAIT = 2000                             # batas siklus menunggu satu handshake

CTRL, STATUS, RESULT, VERSION, NSAT, FRAMES, DS_CTRL, DS_DATA, NSAMP = 0x000, 0x004, 0x008, 0x00C, 0x010, 0x014, 0x018, 0x01C, 0x020


class Axil:
    """Driver master AXI4-Lite: tulis (AW/W dengan urutan dan jeda bebas), baca, dan tahan BREADY/RREADY."""

    def __init__(self, dut):
        self.d = dut
        for n in ("awvalid", "wvalid", "arvalid"):
            getattr(dut, "s_axi_" + n).value = 0
        dut.s_axi_awaddr.value = 0
        dut.s_axi_araddr.value = 0
        dut.s_axi_wdata.value = 0
        dut.s_axi_wstrb.value = 0xF
        dut.s_axi_bready.value = 1
        dut.s_axi_rready.value = 1

    async def _chan(self, valid, ready):
        valid.value = 1
        for _ in range(MAX_WAIT):
            await RisingEdge(self.d.clk)
            if int(ready.value):
                break
        else:
            raise AssertionError(f"handshake {ready._name} tidak pernah ready")
        valid.value = 0

    async def write(self, addr, data, strb=0xF, order="both", delay=0, bready_delay=0):
        """order: both (AW dan W bersamaan), aw_first / w_first (kanal kedua tertunda `delay` siklus). Kanal B dipantau sejak awal."""
        d = self.d
        bt = cocotb.start_soon(self._b(bready_delay))
        if order == "w_first":
            w = cocotb.start_soon(self._w(data, strb))
            await ClockCycles(d.clk, delay)
            aw = cocotb.start_soon(self._aw(addr))
        elif order == "aw_first":
            aw = cocotb.start_soon(self._aw(addr))
            await ClockCycles(d.clk, delay)
            w = cocotb.start_soon(self._w(data, strb))
        else:
            aw = cocotb.start_soon(self._aw(addr))
            w = cocotb.start_soon(self._w(data, strb))
        await aw
        await w
        resp = await bt
        await RisingEdge(d.clk)
        return resp

    async def _b(self, delay):
        d = self.d
        d.s_axi_bready.value = 0 if delay else 1
        seen = 0
        for _ in range(MAX_WAIT):
            await RisingEdge(d.clk)
            if int(d.s_axi_bvalid.value):
                if seen >= delay:
                    resp = int(d.s_axi_bresp.value)
                    if delay:                       # BVALID tertahan oleh BREADY=0: naikkan, handshake pada tepi berikutnya
                        d.s_axi_bready.value = 1
                        await RisingEdge(d.clk)
                    return resp
                seen += 1
        raise AssertionError("bvalid tidak pernah muncul")

    async def _aw(self, addr):
        self.d.s_axi_awaddr.value = addr
        await self._chan(self.d.s_axi_awvalid, self.d.s_axi_awready)

    async def _w(self, data, strb):
        self.d.s_axi_wdata.value = data
        self.d.s_axi_wstrb.value = strb
        await self._chan(self.d.s_axi_wvalid, self.d.s_axi_wready)

    async def read(self, addr, rready_delay=0):
        d = self.d
        d.s_axi_araddr.value = addr
        d.s_axi_rready.value = 0 if rready_delay else 1
        await self._chan(d.s_axi_arvalid, d.s_axi_arready)
        n = 0
        for _ in range(MAX_WAIT):
            await RisingEdge(d.clk)
            if int(d.s_axi_rvalid.value):
                if n >= rready_delay:
                    break
                n += 1
        else:
            raise AssertionError("rvalid tidak pernah muncul")
        val = int(d.s_axi_rdata.value)
        assert int(d.s_axi_rresp.value) == 0
        d.s_axi_rready.value = 1
        await RisingEdge(d.clk)
        return val


async def setup(dut):
    await start_clock(dut)
    dut.sd.value = 0
    ax = Axil(dut)
    await reset(dut)
    return ax


@cocotb.test()
async def test_registers_and_protocol(dut):
    ax = await setup(dut)
    dut._log.info("setup selesai")
    assert await ax.read(VERSION) == 0xA1000001
    assert await ax.read(NSAMP) == N_SAMPLES
    assert await ax.read(STATUS) & 0x7 == 0, "STATUS awal harus idle"
    assert await ax.read(STATUS) & 0x8, "ds_ready harus 1 saat idle"
    # CTRL: bit0 disimpan, bit1 (clear) selalu terbaca 0
    assert await ax.write(CTRL, 0x1) == 0
    assert await ax.read(CTRL) == 1
    assert await ax.write(CTRL, 0x2) == 0
    assert await ax.read(CTRL) == 0
    # urutan AW/W bebas, jeda bebas, BREADY/RREADY ditahan
    assert await ax.write(CTRL, 0x1, order="aw_first", delay=5) == 0 and await ax.read(CTRL) == 1
    assert await ax.write(CTRL, 0x0, order="w_first", delay=7) == 0 and await ax.read(CTRL) == 0
    assert await ax.write(CTRL, 0x1, bready_delay=6) == 0 and await ax.read(CTRL, rready_delay=6) == 1
    # strobe: byte 0 tidak ikut -> tidak berubah
    await ax.write(CTRL, 0x0, strb=0xE)
    assert await ax.read(CTRL) == 1
    await ax.write(CTRL, 0x0)
    # alamat di luar peta: baca 0, tulis diabaikan, respons OKAY
    assert await ax.read(0x3F0) == 0
    assert await ax.write(0x3F0, 0xFFFFFFFF) == 0
    assert await ax.read(CTRL) == 0
    # akses beruntun
    for _ in range(4):
        assert await ax.read(VERSION) == 0xA1000001
    dut._log.info("register dan protokol OK")


@cocotb.test()
async def test_ds_pacing(dut):
    """Dua tulis DS_DATA beruntun: ds_valid harus berjarak >= DS_GAP siklus (syarat frame_buf >= FRAME_LEN+4)."""
    ax = await setup(dut)
    await ax.write(CTRL, 0x0)
    await ax.write(DS_CTRL, 1)
    stamps = []

    async def mon():
        n = 0
        while True:
            await RisingEdge(dut.clk)
            n += 1
            if dut.ds_valid.value.is_resolvable and int(dut.ds_valid.value):
                stamps.append(n)
    t = cocotb.start_soon(mon())
    for s in (100, -100, 5, 0, 32767):
        await ax.write(DS_DATA, s & 0xFFFF)
    await ClockCycles(dut.clk, 10)
    t.cancel()
    assert len(stamps) == 5, f"ds_valid {len(stamps)} kali, harusnya 5"
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert min(gaps) >= params.FRAME_LEN + 4, f"jarak sampel {gaps} < FRAME_LEN+4"
    dut._log.info("jarak ds_valid (siklus): %s", gaps)


async def run_clip(dut, ax, x):
    await ax.write(CTRL, 0x0)
    await ax.write(DS_CTRL, 1)
    for s in np.asarray(x, dtype=np.int64):
        await ax.write(DS_DATA, int(s) & 0xFFFF)
    for _ in range(400):
        await ClockCycles(dut.clk, 2000)
        st = await ax.read(STATUS)
        if st & 0x4:
            break
    else:
        raise AssertionError("timeout menunggu result_new")
    return st


@cocotb.test()
async def test_dataset(dut):
    ax = await setup(dut)
    cases = os.environ.get("AXIL_CASES", "cough,noise3").split(",")
    n_res = 0
    for case in cases:
        x = np.array(vec.load("frontend", case, "in", 16), dtype=np.int16)
        exp = vec.load("cnn", case, "out_logit", 16)[0]
        st = await run_clip(dut, ax, x)
        assert st & 0x4 and not st & 0x1, f"{case}: STATUS {st:#x}"
        r = await ax.read(RESULT)
        got = r & 0xFFFF
        got = got - 0x10000 if got >= 0x8000 else got
        assert got == exp, f"{case}: logit {got} != golden {exp}"
        assert (r >> 16) & 0xFF == (n_res + 1) & 0xFF, f"{case}: seq {(r >> 16) & 0xFF}"
        assert not (await ax.read(STATUS)) & 0x4, "result_new harus terhapus setelah RESULT dibaca"
        n_res += 1
        dut._log.info("dataset %s: logit=%d OK (seq %d)", case, got, n_res)
    # clear menghapus status dan nsat
    await ax.write(CTRL, 0x2)
    assert (await ax.read(NSAT)) == 0


async def i2s_mic(dut, words):
    """Model INMP441: MSB keluar pada tepi turun BCLK berikutnya setelah WS berubah; slot kanan = 0."""
    prev_ws = None
    bits, idx = [], 0
    dut.sd.value = 0
    while True:
        await FallingEdge(dut.bclk)
        ws = int(dut.ws.value)
        if prev_ws is None or ws != prev_ws:
            if ws == 0 and idx < len(words):
                w = words[idx] & 0xFFFFFF
                bits = [(w >> (23 - i)) & 1 for i in range(24)]
                idx += 1
            else:
                bits = []
        prev_ws = ws
        dut.sd.value = bits.pop(0) if bits else 0


@cocotb.test(skip=not os.environ.get("AXIL_MIC"))
async def test_mic(dut):
    ax = await setup(dut)
    x = np.array(vec.load("frontend", "cough", "in", 16), dtype=np.int64)
    ev = cough_det(hop_energy(preemph(x)))
    assert ev, "golden tidak mendeteksi batuk"
    exp = int(C.cnn_forward(F.to_cnn_input(F.segment(F.features_q(x), ev[0].start)), random_calibrated_model())[0])
    words = [(int(v) & 0xFFFF) << 8 for v in x]
    await ax.write(CTRL, 0x1)
    mic = cocotb.start_soon(i2s_mic(dut, words))
    for _ in range(6000):
        await ClockCycles(dut.clk, 2000)
        if (await ax.read(STATUS)) & 0x4:
            break
    else:
        raise AssertionError("timeout mikrofon")
    mic.cancel()
    r = await ax.read(RESULT)
    got = r & 0xFFFF
    got = got - 0x10000 if got >= 0x8000 else got
    assert got == exp, f"mikrofon: logit {got} != golden {exp}"
    dut._log.info("mikrofon: logit=%d OK", got)


def test_runner():
    from tb.common.runner import run, rtl_files
    sim = os.environ.get("SIM", "icarus")
    run("suaratb_axil_top", "test_axil", parameters={"CLK_PER_BCLK": CPBCLK}, simulator=sim,
        sources=rtl_files(extra=AXI_SRC, sim=sim))


if __name__ == "__main__":
    test_runner()
