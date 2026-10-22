# target: kode spesifik perangkat

Satu-satunya tempat kode yang bergantung perangkat atau alat (rtl/ dan golden/ tidak berubah).

| Subdirektori | Isi |
|---|---|
| `common/` | `prep_synth.py`: paket konfigurasi CNN dan ROM bobot untuk satu P; dipakai semua alur sintesis |
| `kv260/` | Kria KV260 (XCK26): sistem AXI4-Lite yang berjalan di papan (`axi/`) dan skrip analisis (`analisis/`) |
| `yosys/` | Sintesis lintas-vendor Yosys (Artix-7, `xc7`) sebagai pembanding sumber daya |
| `asic/` | Sintesis dan layout sky130 (Yosys, OpenLane/OpenROAD) |

Hasil dan batasannya: `docs/vault/sintesis.md`. Keluaran besar ditulis ke `$SUARATB_DATA/build`, bukan ke repo. Skrip sintesis Artix-7
dihapus 2026-10-22 (ada di riwayat git); referensi laporan Artix-7 tetap di `docs/vault/sintesis.md`.
