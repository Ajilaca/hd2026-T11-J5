# target: kode spesifik perangkat

Satu-satunya tempat kode yang bergantung perangkat/alat. Referensi laporan: Artix-7 XC7A35T-1 (Vivado). Bukan janji hardware
demo; FPGA di lokasi acara disediakan panitia (belum diumumkan).

| Subdirektori | Isi |
|---|---|
| `artix7/` | Sintesis dan implementasi Vivado (mode OOC) dengan sapuan P |
| `yosys/` | Sintesis lintas-vendor Yosys sebagai pembanding |
| `kv260/` | Wrapper, block design, constraint, dan skrip sintesis untuk Kria KV260 (XCK26); belum dijalankan |

Hasil dan batasannya: `docs/vault/sintesis.md`. Pin, MMCM, dan constraint I/O hanya ada di `kv260/` (belum dibuktikan di papan).
