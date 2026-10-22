# cnn_top_eco: skrip ECO kapasitansi dan antena `cnn_top` P16 10,24 MHz

Salinan skrip yang menghasilkan layout final `cnn_top` (run `p16_10m_eco8`): satu run dasar, lalu delapan putaran ECO
yang masing-masing mengambil hasil putaran sebelumnya. Hasil dan angkanya ada di `../../results/cnn_top/`
(`riwayat_eco.csv`, `metrics.json`, `timing_ringkas.txt`, `signoff_nomacro.json`). GDS dan netlist final ada di GitHub Release
`asic-cnn-top-p16-10m24-v1` (lihat `../../README.md`).

Skrip ini **bukan** bagian alur yang bisa dijalankan dari root repo seperti `layout_modules.py`: tiap direktori di sini
adalah isi `eco_scripts/` di direktori build (`$HOME/suaratb-data/build/asic/cnn_top/<direktori>/eco_scripts/`) dan
berpath `$HOME/suaratb-data/build/asic/cnn_top/...`. Dijalankan di WSL dengan Docker (`ghcr.io/efabless/openlane2:2.3.10`),
berurutan, dengan hasil putaran N-1 sudah ada di direktori build-nya.

| Direktori | Putaran | Skrip utama | Isi |
|---|---|---|---|
| `p16_10m/` | dasar | `run_base.sh`, `sta_ringkas.py` | Salin masukan `p16`, `CLOCK_PERIOD` 97,656 ns, jalankan alur penuh tanpa XOR/DRC bawaan; `sta_ringkas.py` mencetak setup, hold, kapasitansi, slew per corner dan antena |
| `p16_10m_eco/` | 1 | `run_eco10.sh` | Buffer kapasitansi (`cap_eco.py`), GRT ulang, perbaikan hold, `repair_antennas`, jumper met1 (`guide_jumper.py`) |
| `p16_10m_eco2/`, `p16_10m_eco3/` | 2, 3 | `run_eco2.sh`, `run_eco3.sh` | Sama, dengan target dari putaran sebelumnya |
| `p16_10m_eco4/` | 4 | `run_eco4.sh`, `mk_eco4.py` | Jumper kumulatif: gabungan pelanggar antena semua putaran sebelumnya |
| `p16_10m_eco5/` | 5 | `run_eco5.sh`, `dioda_eco.py` | **Tanpa GRT ulang**: dioda di samping pin gate pelanggar antena |
| `p16_10m_eco6/`, `p16_10m_eco7/` | 6, 7 | `run_eco6.sh`, `run_eco7.sh`, `eco6.py` | Dioda, buffer pin makro, perbesar sel (tanpa GRT ulang); putaran 7 memakai `ECO_TAG` supaya nama sel unik |
| `p16_10m_eco8/` | 8 (final) | `run_eco8.sh`, `eco8.py`, `guide_jumper.py` | Buffer pemecah beban (bukan perbesar sel), dioda, dan jumper, tanpa GRT ulang |

Berkas yang sama muncul di beberapa direktori (`cap_eco.py`, `eco_capfix10.tcl`, `near_cap10.tcl`, `guide_jumper.py`,
`eco6_views.tcl`) karena tiap direktori adalah salinan utuh `eco_scripts/` putaran itu.

Alasan urutannya: GRT di tiap putaran ECO membuat ulang route guide sehingga jumper putaran lama hilang, dan detailed routing
mengacak net lain. Dari putaran 5, guide yang ada tidak diubah. Batas kapasitansi 0,2 pF sama untuk semua ukuran sel, jadi
beban dipecah dengan buffer (putaran 8), bukan dengan memperbesar sel.

Signoff XOR dan DRC KLayout pada GDS tanpa makro: `../signoff_nomacro.py <direktori run>`.
