# SuaraTB: laporan hasil

Akselerator skrining TBC dari suara batuk, dibuat untuk Hackathon Deeptech 2026 (Indonesia Chip Hackathon Challenge, tema Medical Device).
Laporan ini mencatat apa yang sudah dibangun, apa yang terukur, dan apa yang tidak berhasil. Angka diambil dari skrip di repo,
laporan alat (Vivado 2026.1, Yosys 0.33, OpenLane 2.3.10), dan simulasi (Icarus 12 + cocotb 2.1). Keadaan per 23 Oktober 2026.

## 1. Ringkasan

| Pertanyaan | Jawaban | Bukti |
|---|---|---|
| Apakah pipeline audio ke skor jalan di akselerator khusus? | **Ya.** Bit-exact terhadap model numpy (golden) di tiap modul dan ujung ke ujung. Di papan KV260, 968 dari 968 klip (100 peserta) identik dengan golden | §4, §5.3 |
| Muat dan cukup cepat di FPGA? | **Ya.** Artix-7 XC7A35T: 150 MHz terpenuhi untuk P = 8/16/32. KV260: 300 MHz terpenuhi, P = 16 memakai 6.326 LUT (5,4%) | §5 |
| Apakah gejala klinis berguna untuk skrining? | AUROC 0,77 pada 1.828 peserta. **Belum** memenuhi standar WHO TPP | §7.2 |
| Apakah audio batuk mendeteksi TBC? | CNN dari nol: tidak (AUROC sekitar 0,56). Embedding HeAR: ada indikasi sinyal (AUROC 0,71 dalam jenis kelamin, p = 0,002), tetapi tambahannya di atas gejala kecil dan **belum terbukti** | §7.3 sampai 7.5 |
| Bisa dipindah ke hardware? | Sebagian besar. Murid distilasi AUROC 0,654 (guru 0,672), kuantisasi int8 hanya menurunkan 0,008, RTL bit-exact | §7.6 |
| Apakah bisa jadi chip? | `cnn_top` P = 16 pada 10,24 MHz selesai di-layout sky130 dengan kapasitansi, antena, LVS, DRC routing, dan signoff XOR/DRC semuanya 0. Chip utuh dan tape-out belum | §8 |

**Posisi klaim.** Alat ini membantu triase, yaitu menentukan siapa yang dirujuk lebih dulu ke tes TCM atau dahak. Ia bukan alat diagnosis.
Yang didukung bukti: pipeline audio ke skor berjalan di akselerator khusus, terukur latensi dan sumber dayanya, termasuk di papan, dan bobot bisa
diganti tanpa mengubah hardware. Yang **tidak** didukung: akurasi diagnosis, generalisasi ke populasi lain, dan pemenuhan standar WHO.

## 2. Sistem

| Bagian | Isi |
|---|---|
| Masukan | Mikrofon I2S (INMP441), 16 kHz, 16 bit; atau klip dataset yang dikirim host lewat AXI4-Lite |
| Front-end | Pre-emphasis 0,97, frame 400/hop 160, Hamming, FFT 512 radix-2 (data 24 bit), mel 40 band, log2 LUT, kuantisasi int8 |
| Detektor | Energi per hop, EMA derau, ambang 8x selama minimal 2 hop, tahan 300 ms; segmen 50 frame x 40 mel (5 frame pre-roll) |
| CNN | Conv3x3 16/32/32 + ReLU + MaxPool, GAP, FC 32 ke 16 ke 1; 14.496 bobot int8, 3.698.448 MAC; akumulator 24 bit |
| Akselerator | Output-stationary, P lane paralel (P = 8/16/32), requant per layer (M0 Q15, shift, saturasi) |
| Antarmuka host | AXI4-Lite saja (register kontrol, status, hasil, dan dataset). UART sudah dihapus (K-34) |
| Keluaran | Logit int16 per batuk. Skor pasien = rata-rata beberapa batuk di host, lalu digabung dengan gejala klinis di host |

Prinsip rekayasa: model golden numpy yang bit-exact adalah spesifikasinya; RTL tidak memakai IP vendor (kode khusus perangkat hanya di `target/`);
semua ukuran berasal dari satu sumber (`golden/params.py`); angka hardware hanya diambil dari laporan alat.

## 3. Fase 0: parameter dan kalibrasi

Parameter dibekukan setelah eksperimen pada audio sintetis, lalu audio nyata (perekam Zambia, 1.764 klip dari 150 rekaman).

| Keputusan | Hasil | Alasan |
|---|---|---|
| Lebar FFT 24 bit (awalnya 18) | Galat fitur 0,007 oktaf; W = 18 gagal (0,79 oktaf), W = 22 lolos (0,029) | Ambang 0,0625 oktaf (setengah langkah int8) |
| Offset fitur 8265 (sintetis: 6690) | Jenuh int8 0,2% (sebelumnya 2,0%) | K-14, dari audio nyata |
| Skala FFT 1/2 di semua stage | 0 sampel jenuh pada 60 klip berpuncak tertinggi | K-04 |
| Akumulator CNN 24 bit | Puncak teramati 258 ribu (batas 8,4 juta) | K-10 |
| Detektor K = 8, EMA 2^-6 | Sekitar ±15 kejadian per menit pada rekaman utuh. Tanpa ground truth batuk, presisinya tidak terukur | K-07 |

Tes golden: 67 lulus (blok, CNN, jadwal FFT, pengalamatan DSP, front-end, parameter, tabel). Anggaran analitik: memori logis 282 Kbit (P = 16)
dan 3,7 juta MAC. Muat di XC7A35T, EP4CE22, dan ECP5-25F; tidak muat di EP4CE6.

## 4. Verifikasi RTL

Caranya: vektor sintetis dari golden dibandingkan bit demi bit (`==` integer, tanpa toleransi) dengan keluaran RTL di Icarus + cocotb.

| Cakupan | Hasil |
|---|---|
| Front-end: `i2s_rx`, `preemph`, `frame_buf`, `cough_det` | Lulus |
| DSP: `window`, `fft512`, `power`, `mel`, `log_q`, `quant`, `feat_buf`, `dsp_chain` | Lulus (12 modul Fase 2-3) |
| CNN: `requant`, `gap`, `cnn_top` | Lulus: bobot acak (5 kasus), bobot terlatih (8 klip nyata), P = 8/16/32 |
| Sistem: `suaratb_axil_top` | Mode dataset lewat AXI4-Lite lulus bit-exact (`tb/sys/test_axil.py`: 3 lulus, 1 dilewati karena perlu `AXIL_MIC=1`). Mode mikrofon lulus di simulasi dan berjalan di papan |
| Setelah perbaikan timing (100 MHz) dan pipeline 150 MHz | Semua tes di atas diulang dan lulus |
| Dengan bobot murid distilasi | `cnn_top`, mode mikrofon, dan dataset + mikrofon lulus bit-exact |

Tes ujung ke ujung menemukan dua cacat RTL, dan keduanya sudah diperbaiki: DSP tidak dibersihkan saat mode diganti, dan segmen CNN dibaca sebelum
frame ke-50 selesai. Simulasi RTL hanya di Icarus; Verilator tidak dipakai karena cocotb 2.1 tidak cocok dengan Verilator 5.020.
Regresi terpadu 12 Oktober (20 tes `tb/`) dijalankan sebelum UART dihapus; setelah itu tes sistem diganti `test_axil.py`.

## 5. Sintesis dan papan

### 5.1 Artix-7 XC7A35T-1 (Vivado, mode OOC, setelah route)

Tanpa constraint I/O dan tanpa MMCM, jadi yang diukur adalah jalur register ke register di dalam inti. Model terlatih `model_v2`.

| P | Clock | LUT | FF | DSP48E1 | BRAM tile | WNS | Daya* |
|---|---|---|---|---|---|---|---|
| 8 | 100 MHz | 4.823 (23,2%) | 5.548 | 17 | 12 | +0,443 ns | 0,138 W |
| 16 | 100 MHz | 5.834 (28,1%) | 6.148 | 17 | 12 | +0,077 ns | 0,149 W |
| 32 | 100 MHz | 8.236 (39,6%) | 7.486 | 17 | 12 | +0,258 ns | 0,182 W |
| 8 | 150 MHz | 4.807 (23,1%) | 6.736 | 17 | 12 | +0,111 ns | 0,168 W |
| **16** | **150 MHz** | **5.926 (28,5%)** | **7.799** | 17 | 12 | **+0,222 ns** | 0,192 W |
| 32 | 150 MHz | 8.120 (39,0%) | 10.071 | 17 | 12 | +0,023 ns | 0,246 W |

\* Estimasi vectorless (keyakinan "Medium"), bukan pengukuran.

- Jalur kritis berpindah dari kupu-kupu FFT ke detektor, lalu ke baca BRAM + pengali PE. Semuanya diperbaiki tanpa mengubah hasil bit-exact
  (register keluaran BRAM, pengali dipecah, lebar aritmetika disempitkan).
- DSP tetap 17 untuk semua P karena pengali 8x8 PE dipetakan ke LUT: menaikkan P menambah LUT, bukan DSP. BRAM tidak bergantung P.
- Siklus inferensi CNN (simulasi Icarus): versi 100 MHz P = 8: 451.851; P = 16: 226.490; P = 32: 122.843. Versi 150 MHz (diukur ulang 13 Oktober):
  P = 8: 451.880; P = 16: 226.520; P = 32: 122.872.
- Latensi CNN (siklus dikali periode, angka turunan): 100 MHz: 4,52 / 2,26 / 1,23 ms untuk P = 8/16/32; 150 MHz: 3,01 / 1,51 / 0,82 ms.
- Pembanding Yosys 0,33 (tanpa timing): LUT 11.083 sampai 12.560, DSP 32 sampai 56. Ini bukan prediksi Vivado.
- Yang dirasakan pengguna adalah pengambilan 0,5 s audio. Komputasi CNN hanya sekitar 1 sampai 2 ms.
- Batas: satu jalankan per titik (tanpa seed sweep), margin P = 32 tipis (+0,023 ns).

### 5.2 Kria KV260 (XCK26-SFVC784-2LV-C, Vivado 2026.1)

Sistem lengkap: PS, SmartConnect, MMCM, dan inti SuaraTB dengan bobot model TBC, host lewat AXI4-Lite. Pasca-route untuk 300 MHz;
10,24 MHz baru sintesis. Daya adalah estimasi vectorless (keyakinan Low); PS8 saja menyumbang 2,415 W.

Clock 300 MHz (dicapai 299,997 MHz dari MMCM) adalah batas atas yang timingnya terpenuhi, dengan slack tipis. Clock inti dipilih 300,032 MHz = 293 x 1,024 MHz
supaya BCLK I2S tepat di nominal (K-24). Titik kerja berikutnya 10,24 MHz (10 x 1,024 MHz): rasio ke BCLK tepat 10:1, slack longgar (+93,8 ns),
dan latensi CNN tetap dalam milidetik.

| | 10,24 MHz P16 | 10,24 MHz P32 | 300 MHz P16 | 300 MHz P32 |
|---|---|---|---|---|
| LUT | 6.688 | 8.942 | 6.326 (5,4%) | 8.541 (7,3%) |
| FF | 8.491 | 10.761 | 8.446 | 11.107 |
| BRAM36 / DSP | 12 / 17 | 11,5 / 17 | 12 / 17 | 11,5 / 17 |
| WNS | +93,8 ns (sintesis) | +93,8 ns (sintesis) | +0,127 ns | +0,070 ns |
| Daya total | - | - | 2,949 W | 2,975 W |
| Latensi CNN (siklus simulasi / clock) | 22,1 ms | 12,0 ms | 0,76 ms | 0,41 ms |

Pencarian Fmax awal (build penuh dengan MMCM, I/O, dan XDC; satu seed): pada 300,032 MHz P = 16 WNS +0,065 ns dan P = 32 +0,219 ns; pada 333,82 MHz
P = 16 gagal (-0,270 ns) dan P = 32 lolos tipis (+0,018 ns). WNS di tabel (+0,127 dan +0,070 ns) berasal dari build akhir dengan bobot TBC dan berbeda dari angka pencarian itu.

### 5.3 Uji di papan

Yang terukur di papan (P32, sekitar 300 MHz):

| Hasil | Nilai |
|---|---|
| Kesesuaian dengan golden | Bit-exact pada 968 dari 968 klip (100 peserta) |
| Latensi | Sekitar 0,4 ms per klip setelah sampel terakhir (diukur dengan Python) |
| Mode | Dataset (klip lewat AXI4-Lite) dan mikrofon INMP441 |
| Model pembanding batuk vs bukan batuk (arsitektur sama) | 100 dari 100 klip bit-exact, 99 dari 100 benar |
| AUROC fusi di papan (gejala + rata-rata 10 batuk, 100 peserta) | 0,779 |

Latensi untuk 10,24 MHz dan P16 dihitung dari siklus simulasi, bukan diukur di papan.

## 6. Data

| Sumber | Peserta | Positif | Catatan |
|---|---|---|---|
| Zambia CIDRZ (Kaggle, ODbL-1.0), metadata | 1.828 | 205 | 3 klinik Lusaka; label `ground_truth_tb` (Xpert/kultur) |
| Zambia, dengan audio | 364 | 60 | 4 perangkat serentak (perekam, Phone A/B/C); rilis Kaggle memuat 1.481 berkas |
| TBscreen (Nairobi, CC BY 4.0) | 123 dengan audio | 87 | Cohort hampir sama dengan label (perancu rekrutmen) |
| CODA TB DREAM | - | - | Tidak dipakai: butuh akses terverifikasi (K-15) |

Audit (E1): angka "664 peserta" pada deskripsi dataset tidak ada di rilis, dan pemulihan barcode salah ketik tidak menambah peserta.
Pembagian selalu per peserta. Pelatihan hanya memakai data Zambia; belum ada data dari mikrofon INMP441.

## 7. Model dan hasil klinis

Ukuran yang dipakai: AUROC dengan CI 95% bootstrap atas peserta; nol permutasi (label diacak dalam klinik dan jenis kelamin, seluruh pipeline diulang);
kontrol jenis kelamin dan usia; uji lintas perangkat, dataset, dan klinik. Hasil negatif ikut dilaporkan.

### 7.1 Kuantisasi

| Model | AUROC float | AUROC int8 golden | Selisih | Kriteria <= 0,02 |
|---|---|---|---|---|
| CNN dari nol (`model_v2`) | 0,545 | 0,546 | +0,001 | lulus |
| Murid distilasi HeAR | 0,653 | 0,645 | 0,008 | lulus |

Lulus kuantisasi tidak membuktikan kemampuan klinis. Logit `model_v2` hampir konstan.

### 7.2 Gejala klinis dan standar WHO

| Model | n / positif | AUROC | CI 95% |
|---|---|---|---|
| Gejala klinis 14 fitur (LR), semua peserta | 1.828 / 205 | 0,772 | 0,74-0,81 |
| Klinis diperluas | 1.828 / 205 | 0,772 | 0,74-0,81 |
| Jenis kelamin + usia saja (360 peserta) | 360 / 58 | 0,654 | 0,58-0,72 |

| Syarat WHO TPP triase (sensitivitas >= 90%, spesifisitas >= 70%) | Hasil skor klinis |
|---|---|
| Sensitivitas >= 90% | spesifisitas 38% (butuh 70%) |
| Spesifisitas >= 70% | sensitivitas 71% (butuh 90%) |

Memenuhi 90% dan 70% sekaligus butuh AUROC sekitar 0,90 (aproksimasi binormal). Ini **tidak dipenuhi dan tidak diklaim**.

### 7.3 Audio, CNN dilatih dari nol (360 peserta, 58 positif)

| Model | AUROC | Catatan |
|---|---|---|
| CNN MIL | 0,562 (CI 0,48-0,64) | nol 0,523 (p95 0,591), p-empiris 0,41 |
| CNN diperbaiki (derau, klip mirip batuk) | 0,45-0,49 | di bawah acak |
| LR statistik log-mel | 0,66-0,70 mentah; 0,58-0,60 setelah jenis kelamin + usia | sebagian besar dari jenis kelamin |
| Audio memprediksi jenis kelamin | 0,89 | prevalensi TB laki-laki 25% vs perempuan 8% |
| VGGish pralatih | 0,51 (uji tidak sah: jendela 47% nol) | tidak disimpulkan |
| Lintas dataset Zambia dan TBscreen | 0,50-0,55 | tidak berpindah |
| Lintas perangkat (log-mel) | 0,52-0,63 | tidak lebih baik dari dalam-perangkat |

### 7.4 Embedding pralatih dengan protokol tetap (364 peserta, 60 positif)

Protokol (E0): CV 5 x 5-10 per peserta, stratifikasi label x klinik x jenis kelamin. Skor klinis dilatih hanya pada peserta tanpa audio.
Ukuran utama adalah AUROC terstratifikasi jenis kelamin dan selisih fusi dengan klinis; nol permutasi dalam klinik x jenis kelamin. Semua kandidat dilaporkan.

| Fitur | AUROC strat. jenis kelamin | Nol p95 / maks | Δ vs klinis (CI 95%) |
|---|---|---|---|
| Statistik log-mel (pembanding) | 0,599 | 0,619 / 0,672 | -0,002 (-0,032..+0,029) |
| HeAR | 0,675 | 0,561 / 0,582 | +0,015 (-0,023..+0,058) |
| OPERA-CT | 0,677 | 0,609 / 0,644 | +0,029 (-0,011..+0,068) |
| OPERA-CE | 0,606 | 0,604 / 0,612 | +0,013 (-0,013..+0,041) |

### 7.5 Uji permutasi final dan pemeriksaan

1.000 permutasi, statistik maksimum atas tiga kandidat, permutasi sama untuk semua kandidat, C tetap 0,03 (ditetapkan di muka; hasil serupa untuk
C = 0,01 dan 0,1). Kriteria lolos distilasi ditetapkan sebelum angka final keluar.

| Kandidat | AUROC strat. | p disesuaikan (label) | Δ di atas klinis | p (Δ) | CI bootstrap Δ |
|---|---|---|---|---|---|
| HeAR | 0,709 | 0,002 | +0,039 | 0,003 | -0,011..+0,092 |
| OPERA-CT | 0,664 | 0,006 | +0,025 | 0,015 | -0,017..+0,064 |
| OPERA-CE | 0,621 | 0,089 | +0,022 | 0,023 | -0,003..+0,048 |

| Pemeriksaan | Hasil |
|---|---|
| Kontrol negatif (fitur Gaussian acak, 2 seed) | Bersih: tidak ada p disesuaikan mendekati 0,05 |
| Lintas perangkat HeAR (Phone A/B/C, peserta sama) | AUROC strat. 0,62-0,69 di 9 pasangan. Ini ketahanan terhadap mikrofon, bukan terhadap populasi |
| Jalan pintas HeAR | Embedding memprediksi jenis kelamin 0,95 dan klinik Kan 0,90; AUROC dalam Kan 0,73, Cha 0,64 (11 positif) |
| Leave-one-clinic-out | Kan ke Cha: HeAR 0,55, OPERA-CT 0,73; Cha ke Kan: HeAR 0,62, OPERA-CT 0,56. Tidak konsisten antar arah (Cha hanya 11 positif) |

| Kriteria distilasi (praregistrasi) | Hasil |
|---|---|
| (1) p label disesuaikan < 0,01 | HeAR dan OPERA-CT lolos |
| (2) p Δ < 0,05 dan batas bawah CI Δ > 0 | **Gagal** (CI mencakup 0) |
| (3) leave-one-clinic-out tidak runtuh di kedua arah | **Gagal** |

### 7.6 Distilasi HeAR ke CNN golden (eksploratori)

Dijalankan atas permintaan, di luar kriteria di atas. Murid berarsitektur hardware, targetnya 32 komponen PCA dari embedding HeAR tanpa label TB.
PCA dan murid dilatih hanya pada peserta lipatan latih; probe LR di dalam lipatan.

| Model | AUROC strat. | Nol p95 / maks | Δ di atas klinis |
|---|---|---|---|
| Guru HeAR (klip yang sama) | 0,672 | 0,606 / 0,675 | +0,024 |
| **Murid distilasi (16-d)** | **0,654** | 0,580 / 0,642 | +0,015 |
| Kontrol: jaringan acak tanpa pelatihan | 0,598 | 0,583 / 0,627 | +0,000 |
| Kontrol: target teracak | 0,529 | 0,568 / 0,618 | -0,011 |
| `model_v2` (supervised dari nol) | sekitar 0,56 | - | - |

Murid memprediksi jenis kelamin 0,87 (guru 0,95) dan klinik Kan 0,66 (guru 0,90); AUROC dalam Kan 0,735. Fidelitas komponen PCA rendah (R² 0,16).
Kuantisasi int8 menurunkan 0,008 (lulus), dan RTL bit-exact dengan bobot ini.

### 7.7 Upaya menguatkan sinyal audio (21-22 Oktober)

Setelah 12 Oktober ada beberapa percobaan untuk menaikkan AUROC audio. Aturan ditulis sebelum angka dilihat, dan hasilnya tidak ada yang lolos.

| Kode | Percobaan | Hasil | Kesimpulan |
|---|---|---|---|
| K-25 | Tambah TBscreen ke pelatihan Zambia (HeAR + LR) | Δ = -0,011, CI [-0,056, +0,037]. Embedding mengenali asal dataset dengan AUROC 1,000 | Tidak membantu |
| K-26 (4) | Latih di TBscreen, uji di Zambia | AUROC strat. 0,644 (p = 0,035); kontrol berbobot jenis kelamin x label 0,634 (p = 0,065), gagal tipis | Bukan sinyal menurut kriteria, bukti lemah |
| K-26 (2)(3) | Guru lain (OPERA-CT, Whisper, WavLM, AST, CLAP) dan gabungannya | HeAR tetap terbaik tunggal (0,683). HeAR + OPERA-CT 0,714 (Δ +0,031, CI [-0,009, +0,071]) | Tidak ada yang lebih baik dari HeAR |
| K-27 | 327 Zambia + 110 TBscreen acak, uji pada sisanya (500 pembagian) | Z 0,697; G 0,680; Δ = -0,017, CI [-0,070, +0,035] | Tidak berhasil |
| K-28 | Kurva belajar 100 sampai 327 peserta | 0,700 / 0,704 / 0,692 / 0,703 / 0,698; Δ (327 - 291) = -0,005 | Datar |

### 7.8 Model gejala klinis dan simulasi

| Kode | Percobaan | Hasil |
|---|---|---|
| K-30 | Kurva belajar model gejala, 50 ulangan, uji tetap 400 peserta | 200: 0,717; 400: 0,739; 800: 0,752; 1.200: 0,761; 1.428: 0,765. Δ (1.428 - 400) = +0,026, CI [-0,014, +0,068], jadi datar menurut kriteria |
| K-31 | Simulasi 5.000 dan 10.000 peserta sintetis | 0,791 dan 0,792 terhadap batas atas generator 0,795; kontrol label acak 0,50. **Hanya ilustrasi metode, bukan bukti klinis** |

### 7.9 Lintas perangkat dan agregasi (349 peserta, 58 positif, murid CNN di FPGA)

| Kode | Percobaan | AUROC audio | Catatan |
|---|---|---|---|
| K-32 | Ponsel C, 10 klip (paket papan) | 0,715 | Acuan; fusi dengan gejala 0,798, gejala saja 0,782 |
| K-32 | Ponsel A+B+C, 10 klip per ponsel | 0,740 | Δ +0,025, CI [-0,016, +0,068]: tidak terbukti |
| K-33 | Rata-rata 50% logit tertinggi | 0,749 | Δ +0,034, CI [-0,016, +0,088]: tidak terbukti; fusi 0,822 |
| K-33 | Median, rata-rata terpangkas 20%, buang klip buruk | 0,708 / 0,721 / 0,736 | Tidak ada yang lolos |

Pada titik kerja fusi acuan (optimistis, ambang dipilih pada data yang sama): sensitivitas 90% memberi spesifisitas 49% (55 orang dirujuk per 100);
sensitivitas 80% memberi spesifisitas 68% (37 dirujuk per 100).

### 7.10 Model demonstrasi batuk vs bukan batuk (K-29)

Model audio TBC lemah dan tidak banyak ruang untuk diperbaiki dalam waktu yang tersisa. Untuk memperlihatkan bahwa akselerator berfungsi pada tugas dengan
sinyal yang jelas, arsitektur yang sama dilatih ulang untuk tugas lain: batuk (klip Zambia) lawan bukan batuk (Speech Commands v0.02). RTL dan golden tidak berubah;
yang berganti hanya bobot.

| Ukuran | Hasil (uji: 1.272 batuk dan 1.063 bukan batuk dari pembicara dan peserta yang tidak dilatih) |
|---|---|
| AUROC int8 golden | 0,9989 |
| Akurasi pada ambang 0 | 99,1% (batuk terdeteksi 99,4%, bukan batuk ditolak 98,8%) |
| Penurunan kuantisasi float ke int8 | 0,0000 |
| Di papan | 100 dari 100 klip bit-exact, 99 dari 100 benar |

Batas klaim: ini **bukan** kinerja skrining TBC. Sumber batuk dan bicara berbeda (perangkat, ruang, bahasa), sehingga sebagian pemisahan bisa berasal dari perbedaan sumber.

## 8. Layout ASIC sky130

Selain FPGA, blok-blok SuaraTB dicoba dibuat sebagai layout chip di proses terbuka SkyWater 130 nm (sky130A) dengan OpenLane 2.3.10 (Yosys, OpenROAD,
Magic, KLayout, Netgen) di Docker. Tujuannya menunjukkan bahwa desain ini bisa menjadi chip dan menyiapkan bahan untuk tape-out. Hasilnya adalah studi layout, belum chip utuh.

### 8.1 Keputusan desain

| Aspek | Keputusan | Alasan |
|---|---|---|
| Clock | 10,24 MHz (periode 97,656 ns) | Di 25 ns hold corner SS gagal (-1,78 ns): delay input SDC (20% periode) lebih kecil dari latensi clock SS (8 sampai 12 ns). Di 97,656 ns sebabnya hilang. Clock tidak sepenting itu untuk alat ini |
| Lebar CNN | P = 16 | FPGA yang diuji memakai P = 32; ASIC dibuat lebih kecil |
| Antarmuka host | AXI4-Lite, tanpa UART | Sama dengan yang sudah jalan di papan |
| Memori | 14 makro SRAM OpenRAM 2 KB (6 RAM, 8 ROM bobot) | ROM bobot 116 Kbit yang disintesis sebagai logika membuat global routing macet lebih dari 40 menit |
| Bobot CNN | Dimuat lewat port `wl_*` setelah chip menyala | ROM berupa SRAM, jadi kosong saat start. Perilaku ini beda dari RTL FPGA |

### 8.2 Hasil `cnn_top` P16, 10,24 MHz (run `p16_10m_eco8`)

Die 3.072 x 2.926 µm (8,99 mm²), 116.016 sel standar, 14 makro, utilisasi inti 49,7%. Daya estimasi OpenROAD 15,7 mW (tanpa vektor aktivitas).

| Cek | Hasil |
|---|---|
| Kapasitansi maksimum | 0 pelanggaran (9 corner) |
| Antena | 0 net |
| LVS | 0 |
| DRC routing | 0 |
| Setup / hold | 0 pelanggaran; slack terburuk +34,4 ns / +0,10 ns |
| XOR Magic vs KLayout dan DRC KLayout (GDS tanpa makro) | 0 / 0 |
| Slew / fanout maksimum | 666 / 1.205 pelanggaran, belum ditangani; timing tetap aman |

XOR dan DRC dijalankan pada GDS dengan 14 instans makro dikeluarkan. DRC Magic penuh melaporkan sekitar 33 juta pelanggaran di dalam makro OpenRAM (0 di luar makro),
dan perlu dikonfirmasi sebagai waiver ke penyelenggara shuttle.

### 8.3 Perjalanan perbaikan kapasitansi dan antena

Run dasar di 10,24 MHz menyisakan 147 pelanggaran kapasitansi dan 43 antena. Delapan putaran ECO (perubahan kecil langsung di layout) membawanya ke 0 dan 0.

| Putaran | Cara | Kapasitansi | Antena |
|---|---|---|---|
| Dasar | Alur penuh | 147 | 43 |
| 1 | Buffer kapasitansi, GRT ulang, perbaikan antena, jumper met1 | 11 | 38 |
| 2 | Sama | 2 | 17 |
| 3 | Sama | 1 | 31 |
| 4 | Jumper kumulatif (87 net) | 0 | 12 |
| 5 | Dioda tanpa GRT ulang | 2 | 5 |
| 6 | Dioda + buffer pin makro, tanpa GRT ulang | 1 | 3 |
| 7 | Dioda + buffer pin makro, tanpa GRT ulang | 2 | 4 |
| **8** | **Buffer pemecah beban + dioda + jumper, tanpa GRT ulang** | **0** | **0** |

Yang terbukti berhasil: (1) routing global tidak diulang di setiap putaran, karena GRT membuat ulang semua panduan routing sehingga jumper putaran lama hilang
dan routing mengacak net lain; (2) beban dipecah dengan buffer, bukan sel diperbesar, karena batas 0,2 pF sama untuk semua ukuran sel; (3) dioda saja
tidak cukup, karena router kadang menyambungnya lewat cabang lain, sehingga jumper met1 ikut dipasang.

### 8.4 Modul lain (13 layout, 40 MHz)

Setiap modul tanpa RAM sudah di-layout sendiri-sendiri pada 40 MHz: DRC Magic 0, DRC KLayout 0, LVS 0, XOR 0, DRC routing 0, setup dan hold 0 pelanggaran.
Sisanya ada di antena, slew, kapasitansi, dan fanout. Layout `uart_bridge` tidak dipakai lagi (K-34).

| Layout | Sel | Die (mm²) | Setup (ns) | Antena | Slew | Kap. | Fanout | Daya (mW) |
|---|---|---|---|---|---|---|---|---|
| i2s_rx | 393 | 0,011 | +17,67 | 0 | 0 | 0 | 0 | 0,24 |
| preemph | 2.424 | 0,059 | +12,50 | 0 | 0 | 0 | 10 | 2,01 |
| gap | 1.128 | 0,029 | +15,01 | 0 | 0 | 0 | 5 | 0,57 |
| window | 4.591 | 0,107 | +8,75 | 0 | 106 | 0 | 8 | 5,71 |
| log_q | 1.537 | 0,036 | +10,43 | 0 | 7 | 0 | 3 | 0,95 |
| cough_det | 5.225 | 0,119 | +4,19 | 1 | 8 | 0 | 26 | 4,59 |
| power | 10.365 | 0,237 | +3,43 | 9 | 18 | 0 | 13 | 12,45 |
| mel (setelah perbaikan) | 82.308 | 1,335 | +5,15 | 9 | 2.840 | 75 | 3.156 | 26,13 |
| requant P16 | 9.143 | 0,198 | +6,68 | 5 | 11 | 0 | 38 | 16,57 |
| pe_array P16 | 26.435 | 0,624 | +12,88 | 29 | 18 | 9 | 120 | 27,62 |

`requant`, `pe_array`, dan `gap` sudah termasuk di dalam `cnn_top`. Varian P32 hanya perbandingan. `mel` paling bermasalah: perbaikan antena menurunkan antena dari 189 ke 9,
tetapi memperburuk slew dan fanout.

### 8.5 Yang belum ada

- Blok yang belum pernah di-layout: `fft512`, `frame_buf`, `feat_buf`, `quant`, `dsp_chain`, `axil_ctrl`. Top chip belum dibuat.
- `axil_ctrl` belum punya register untuk memuat bobot ke SRAM (rencananya `WL_ADDR` di 0x024 dan `WL_DATA` di 0x028).
- Lib makro OpenRAM hanya TT, dipakai di semua corner, jadi timing jalur melewati makro di corner SS dan FF tidak bisa dipercaya penuh.
- Luas: die `cnn_top` saja 8,99 mm² dan lebarnya 3,07 mm, sedangkan area pengguna di Caravel sekitar 2,92 x 3,52 mm. Seluruh sistem kemungkinan tidak muat tanpa dipadatkan.
- Pin: `suaratb_axil_top` punya sekitar 116 pin, sedangkan Caravel hanya 38 GPIO. AXI-Lite harus tetap di dalam chip (lewat jembatan Wishbone) atau memakai platform dengan pad ring sendiri.
- Laptop dengan WSL 10 GB hampir kehabisan memori pada signoff `cnn_top`; signoff chip utuh kemungkinan butuh mesin 32 GB atau lebih.
- Platform tape-out (Caravel atau pad ring sendiri) belum diputuskan.

## 9. Keputusan penting

| Kode | Keputusan |
|---|---|
| K-04 | Lebar FFT 24 bit, skala 1/2 di semua stage |
| K-14 | Offset fitur dari audio nyata (6690 menjadi 8265) |
| K-15 | TBscreen sebagai data tambahan, bukan CODA (akses) |
| K-17 | CNN output-stationary, paralel di kanal keluaran |
| K-21 | Target akurasi 0,70/0,80 diganti pelaporan terukur + pembanding WHO TPP |
| K-22 | Clock inti 147,456 MHz untuk Artix-7 |
| K-23 | Embedding pralatih diuji; kriteria distilasi tidak terpenuhi; distilasi dicoba eksploratori |
| K-24 | Target KV260 dengan clock inti 300,032 MHz |
| K-25 sampai K-28 | Penguatan sinyal audio (TBscreen, guru lain, pembagian acak, kurva belajar): tidak ada yang lolos |
| K-29 | Model demonstrasi batuk vs bukan batuk untuk membuktikan akselerator |
| K-30, K-31 | Kurva belajar model gejala; simulasi sintetis (ilustrasi saja) |
| K-32, K-33 | Lintas perangkat dan agregasi logit: tidak terbukti lebih baik |
| K-34 | UART dihapus; AXI4-Lite satu-satunya antarmuka host |

Keputusan di luar nomor: layout ASIC memakai 10,24 MHz, P = 16, dan makro SRAM (§8.1).

## 10. Keterbatasan

1. **Data kecil dan satu populasi.** 60 positif beraudio, 3 klinik di Lusaka, tanpa data independen. CI lebar (sekitar ±0,08), jadi selisih di bawah ±0,05 tidak bisa dibuktikan.
2. **Perancu.** Jenis kelamin dan klinik, dan embedding memprediksi keduanya. Strata mengendalikannya tetapi tidak menghilangkan risikonya.
3. **Mikrofon.** Semua data dari perekam dan telepon; belum ada data latih dari INMP441. `FEAT_OFFSET` dan detektor masih sementara.
4. **Detektor tanpa ground truth batuk.** Presisinya tidak terukur; klip bisa memuat bicara atau derau.
5. **Hardware.** Sudah jalan di papan KV260, tetapi daya adalah estimasi vectorless, uji papan baru satu konfigurasi (P32, sekitar 300 MHz), dan 10,24 MHz baru sintesis.
6. **Pemilihan model pada data yang sama.** Percobaan §7.4 sampai 7.9 memakai peserta yang sama. Konfirmasi hanya sah pada data baru.
7. **Standar WHO.** Tidak dipenuhi, dan audio tidak menutup jaraknya.
8. **ASIC.** Baru `cnn_top` yang selesai. Chip utuh, simulasi gate-level, dan pemeriksaan tape-out belum dilakukan (§8.5).

## 11. Peta jalan

| Langkah | Tujuan |
|---|---|
| Data besar (CODA, 300+ positif) atau pengumpulan prospektif dengan INMP441 | Satu-satunya jalan mengubah kesimpulan "belum terbukti" |
| Validasi HeAR dan distilasi pada klinik atau populasi independen | Menjawab soal jalan pintas klinik dan nilai tambah di atas gejala |
| Seed sweep, uji papan untuk konfigurasi lain, benchmark vs CPU | Menutup batas hardware dan menghasilkan angka latensi dan energi akhir |
| Pilih platform tape-out, hitung anggaran luas dari sintesis blok yang belum di-layout | Menentukan apakah seluruh sistem muat |
| RTL top chip: register muat bobot, jembatan bus bila Caravel; verifikasi lewat cocotb | Chip bisa dipakai tanpa ROM bobot tertanam |
| Layout blok di 10,24 MHz, layout top, signoff chip, precheck platform | Tape-out |

## 12. Repositori dan dokumentasi

- Pekerjaan ASIC digabung ke `main` lewat pull request #1. Semua cabang kerja lain sudah dihapus; tag `submission` tetap ada.
- `target/asic/` berisi skrip (`scripts/`, termasuk skrip delapan putaran ECO di `scripts/cnn_top_eco/`), pengganti RAM berbasis makro SRAM (`ram/`), metrik
  hasil (`results/`), dan README yang menjelaskan fungsi tiap direktori, hasil, keterbatasan, dan rencana.
- Berkas hasil besar (GDS, DEF, netlist, SPEF; 13 modul dan `cnn_top` final) tidak disimpan di git. Paketnya disiapkan sebagai aset GitHub Release.
  Saat laporan ini ditulis, Release tersebut berstatus draft karena tag-nya dihapus.
- Perubahan terkini di sisi sistem: UART dihapus (K-34), skrip papan di `sw/pynq/papan/`, dan diagram arsitektur baru (jalur mikrofon I2S dan host AXI4-Lite).

## Lampiran: lokasi bukti

| Topik | Berkas |
|---|---|
| Spesifikasi, parameter | `golden/params.py`, `docs/vault/spesifikasi.md` |
| Keputusan | `docs/vault/keputusan.md` |
| Verifikasi | `tb/`, `docs/vault/verifikasi.md` |
| Sintesis dan papan | `target/`, `docs/vault/sintesis.md` |
| Data | `docs/vault/data.md`, `model/data/` |
| Model dan evaluasi | `docs/vault/model.md`, `model/` |
| Layout ASIC | `target/asic/README.md`, `target/asic/results/cnn_top/`, `target/asic/scripts/` |
