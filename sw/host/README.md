# sw/host

| Berkas | Isi |
|---|---|
| `host.py` | Skrip host (pyserial): kirim klip dataset `D`, baca logit `L`, tulis/baca CSR, pilih mode dataset/mikrofon, rata-rata logit 3-5 batuk, bandingkan dengan golden. Opsi dan contoh ada di docstring |

Protokol didefinisikan di `rtl/sys/uart_bridge.sv` dan `rtl/sys/csr.sv`. Baud default 115200 (cocok dengan build KV260). Skrip diuji dengan
perangkat tiruan yang meniru protokol dan memakai logit golden; belum diuji dengan perangkat keras.
