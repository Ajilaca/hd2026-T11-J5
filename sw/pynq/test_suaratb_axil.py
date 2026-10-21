"""Uji driver suaratb_axil.py tanpa papan: MMIO tiruan dengan peta register yang sama dengan axil_ctrl.sv; logit dari golden.
    python -m pytest sw/pynq/test_suaratb_axil.py -q
"""
import pathlib
import struct
import sys
import wave

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sw" / "pynq"))

import suaratb_axil as S                      # noqa: E402
from golden import params                     # noqa: E402
from tb.common import vec                     # noqa: E402

N = params.CLIP_SAMPLES_PADDED


class FakeMMIO:
    """Meniru axil_ctrl: DS_DATA dikumpulkan; setelah N sampel, hasil = logit referensi (result_new=1, seq+1)."""

    def __init__(self, logit_for=lambda clip: 0, version=S.EXPECT_VERSION):
        self.logit_for, self.version = logit_for, version
        self.samples, self.mode, self.seq, self.logit, self.new, self.log = [], 0, 0, 0, False, []

    def write(self, off, val):
        self.log.append((off, val))
        if off == S.CTRL:
            self.mode = val & 1
            if val & 2:
                self.new = False
        elif off == S.DS_CTRL and val & 1:
            self.samples, self.new = [], False
        elif off == S.DS_DATA:
            assert 0 <= val <= 0xFFFF, "DS_DATA harus 16 bit"
            self.samples.append(val)
            if len(self.samples) == N:
                clip = np.array(self.samples, dtype=np.uint16).view(np.int16)
                self.logit, self.new, self.seq = self.logit_for(clip), True, (self.seq + 1) & 0xFF

    def read(self, off):
        if off == S.VERSION:
            return self.version
        if off == S.NSAMP:
            return N
        if off == S.STATUS:
            return (4 if self.new else 0) | 8
        if off == S.RESULT:
            self.new = False
            return (self.seq << 16) | (self.logit & 0xFFFF)
        return 0


def test_infer_matches_reference():
    x = np.array(vec.load("frontend", "cough", "in", 16), dtype=np.int16)
    exp = vec.load("cnn", "cough", "out_logit", 16)[0]
    m = FakeMMIO(lambda clip: exp if np.array_equal(clip, x) else -1)
    dev = S.SuaraTB(mmio=m)
    r = dev.infer(x)
    assert r.logit == exp and r.seq == 1
    offs = [o for o, _ in m.log]
    assert offs[0] == S.CTRL and offs[1] == S.DS_CTRL and offs[2:] == [S.DS_DATA] * N, "urutan: mode, mulai, 8240 sampel"
    assert not m.new, "membaca RESULT menghapus result_new"


def test_negative_logit_and_mean():
    m = FakeMMIO(lambda clip: -1234)
    dev = S.SuaraTB(mmio=m)
    r = dev.infer(np.zeros(N, dtype=np.int16))
    assert r.logit == -1234
    s = dev.summarize([-1234, 200, 34], threshold=0.0)
    assert s["mean_logit"] == -333.33 and s["above_threshold"] is False


def test_wrong_version_and_length():
    with pytest.raises(RuntimeError):
        S.SuaraTB(mmio=FakeMMIO(version=0))
    dev = S.SuaraTB(mmio=FakeMMIO())
    with pytest.raises(ValueError):
        dev.infer(np.zeros(100, dtype=np.int16))


def test_timeout():
    class Never(FakeMMIO):
        def write(self, off, val):
            if off == S.DS_DATA:
                return
            super().write(off, val)
    dev = S.SuaraTB(mmio=Never())
    with pytest.raises(TimeoutError):
        dev.infer(np.zeros(N, dtype=np.int16), timeout=0.05)


def _wav(path, sr, x, ch=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.asarray(x, dtype="<i2").tobytes())


def test_load_wav_resample_and_clip(tmp_path):
    t = np.arange(44100) / 44100
    sig = (8000 * np.sin(2 * np.pi * 1000 * t)).astype(np.int16)           # 1 s, 44,1 kHz
    _wav(tmp_path / "a.wav", 44100, sig)
    x = S.load_wav(tmp_path / "a.wav")
    assert x.dtype == np.int16 and abs(x.size - 16000) <= 1
    c = S.to_clip(x, N, "first")
    assert c.size == N and np.array_equal(c, x[:N])
    short = S.to_clip(x[:100], N)
    assert short.size == N and not short[100:].any()
    # jendela terkeras: letupan di tengah klip panjang harus tertangkap
    long_x = np.zeros(40000, dtype=np.int16)
    long_x[20000:20300] = 20000
    c2 = S.to_clip(long_x, N, "loudest")
    assert np.abs(c2).max() == 20000 and np.abs(S.to_clip(long_x, N, "first")).max() == 0
    _wav(tmp_path / "s.wav", 16000, np.repeat(sig[:1000, None], 2, axis=1).ravel(), ch=2)
    assert S.load_wav(tmp_path / "s.wav").size == 1000
