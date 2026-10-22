# target/kv260

Kria KV260 (XCK26-SFVC784-2LV-C). Satu-satunya jalur host adalah AXI4-Lite; versi awal berbasis UART dihapus 2026-10-22 (ada di riwayat git). Hasil terukur ada di `docs/vault/sintesis.md` dan laporan alat di `$SUARATB_DATA/build/kv260/`.

| Direktori | Isi |
|---|---|
| `axi/rtl/` | `axil_ctrl.v` (slave AXI4-Lite), `suaratb_axil_top.sv` (glue), `suaratb_axil_ip.v.in` (pembungkus IP dari template). `legacy/axil_ctrl.sv` = versi SystemVerilog yang menjadi sumber bitstream awal yang terbukti di papan; modul yang sama dengan `axil_ctrl.v`, jangan didaftarkan bersamaan |
| `axi/flow/` | `synth_axil.tcl` (sintesis, implementasi, bitstream), `create_bd_axil.tcl` (PS, SmartConnect, MMCM, reset), `kv260_axil.xdc` (pin Pmod J2), `make_app.sh` (paket xmutil), `program_jtag.tcl` |
| `analisis/` | `sweep_estimasi.py`: perhitungan sapuan clock x P (estimasi, bukan build) |

Varian AXI terbukti di papan (P32, sekitar 300 MHz, model TBC dan model batuk): bit-exact terhadap golden dan latensi sekitar 0,4 ms per klip.
Pin Pmod J2 dan peta register: lihat komentar di `axi/flow/kv260_axil.xdc` dan `axi/rtl/axil_ctrl.v`.
