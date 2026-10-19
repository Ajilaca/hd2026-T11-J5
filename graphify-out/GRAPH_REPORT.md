# Graph Report - HACKATON  (2026-10-19)

## Corpus Check
- 26 files · ~467,271 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1158 nodes · 3285 edges · 78 communities (55 shown, 23 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 127 edges (avg confidence: 0.86)
- Token cost: 76,930 input · 0 output

## Community Hubs (Navigation)
- CNN Golden dan Kalibrasi
- Anggaran Sumber Daya
- Dokumen Vault dan Konteks
- Model Klinis
- Testbench DSP Frame
- Kalibrasi Detektor
- Runner cocotb DSP
- Tabel FFT dan Log
- Data Batuk dan Energi
- Testbench I2S dan Sistem
- Arsitektur RTL DSP
- Golden FFT512
- Evaluasi Lintas Perangkat
- Audit Dataset
- Uji Permutasi
- Golden Blok Front-end
- Path Data Golden
- Protokol Evaluasi
- Ekspor Model Kuantisasi
- Setup Lingkungan WSL2
- Host UART
- Segmentasi dan Jendela
- Testbench CNN
- Front-end Golden
- Laporan Hasil
- Sinyal Uji Sintetis
- Target KV260 dan Sapuan P
- Distilasi HeAR
- RTL Front-end Audio
- Sintesis Artix-7 dan sv2v
- Golden Mel
- Tes Muat ROM dan Frame
- Pelatihan MIL
- Embedding Pralatih
- Layout cnn_top Makro
- Model Student Distilasi
- Pelatihan MIL2
- Baseline CNN
- Detektor Batuk RTL
- Diagram Arsitektur
- Spesifikasi Golden Fase 0
- RTL Rantai DSP
- Testbench Pre-emphasis
- Wrapper RAM Makro sky130
- Kalibrasi Data Nyata
- RTL Kontrol CNN
- Kumpulan Hasil Layout
- Ringkasan Model
- Jadwal FFT
- HeAR Lintas Perangkat
- RTL FFT dan ROM
- Pencari Fmax KV260
- Render Layout PNG
- RTL UART
- Hasil Model Audio
- Top KV260
- Cek Lingkungan
- Gambar Arsitektur
- Hasil Klinis
- Assertion Stream
- FIFO Sinkron

## God Nodes (most connected - your core abstractions)
1. `preemph()` - 46 edges
2. `start_clock()` - 45 edges
3. `reset()` - 43 edges
4. `run()` - 40 edges
5. `StreamMonitor` - 35 edges
6. `fft512()` - 29 edges
7. `features_dir()` - 28 edges
8. `runs_dir()` - 28 edges
9. `hop_energy()` - 26 edges
10. `cough_det()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Tes rantai DSP (window..dsp_chain)` --references--> `dsp_chain (window->fft512->power->mel->log_q->quant)`  [INFERRED]
  tb/dsp/README.md → rtl/dsp/README.md
- `CNN dari nol (negatif AUROC 0,56)` --shares_data_with--> `cnn.py QModel`  [INFERRED]
  model/scratch/README.md → golden/blocks/README.md
- `Dataset Google + CIDRZ Zambia` --references--> `Data (Zambia CIDRZ)`  [INFERRED]
  README.md → docs/vault/data.md
- `int_logits()` --references--> `QModel`  [EXTRACTED]
  model/scratch/export.py → golden/blocks/cnn.py
- `ptq()` --references--> `QModel`  [EXTRACTED]
  model/scratch/export.py → golden/blocks/cnn.py

## Import Cycles
- 1-file cycle: `rtl/cnn/cnn_ctrl.sv -> rtl/cnn/cnn_ctrl.sv`
- 1-file cycle: `rtl/cnn/cnn_top.sv -> rtl/cnn/cnn_top.sv`

## Hyperedges (group relationships)
- **Evaluasi model: embedding, permutasi, distilasi** — docs_result_report_pretrained_embeddings, docs_result_report_permutation_test, docs_result_report_hear_distillation [EXTRACTED 0.75]
- **Protokol host UART** — sw_host_readme_host_py, rtl_sys_readme_uart_bridge, rtl_sys_readme_csr, rtl_sys_readme_uart_rx_tx [EXTRACTED 0.90]
- **Rantai fitur DSP satu frame** — rtl_dsp_readme_window, rtl_dsp_readme_fft512, rtl_dsp_readme_mel, rtl_dsp_readme_log_q, rtl_dsp_readme_dsp_chain [EXTRACTED 0.95]
- **Pipeline audio ke skor risiko** — docs_img_arsitektur_i2s_rx, docs_img_arsitektur_preemph, docs_img_arsitektur_frame_buf, docs_img_arsitektur_dsp_chain, docs_img_arsitektur_feat_buf, docs_img_arsitektur_cnn_top, docs_img_arsitektur_skor_risiko [EXTRACTED 1.00]
- **Jalur deteksi batuk mikrofon** — docs_img_arsitektur_frame_buf, docs_img_arsitektur_cough_det, docs_img_arsitektur_feat_buf [EXTRACTED 1.00]
- **Evaluasi hardware dan model: sintesis, verifikasi, AUROC** — readme_hasil_sintesis_artix7, readme_auroc_model_audio, docs_vault_verifikasi, readme_who_tpp_triase [INFERRED 0.75]
- **Verifikasi bit-exact RTL vs golden** — tb_vectors_readme_synthetic_vectors, tb_common_readme_vec, tb_common_readme_runner, rtl_dsp_readme_golden_blocks [INFERRED 0.85]
- **Rantai kalibrasi Fase 0 ke parameter beku** — docs_vault_kalibrasi_fase0, docs_vault_kalibrasi_data_nyata, docs_vault_keputusan_k04_fft_24_bit, docs_vault_spesifikasi_frontend_dsp [INFERRED 0.85]
- **Golden, RTL verification, dan sintesis** — docs_result_report_golden_model, docs_result_report_rtl_verification, docs_result_report_synthesis [INFERRED 0.85]
- **Vendor-specific synthesis/implementation targets (Artix-7, KV260, Yosys, sky130)** — target_artix7_readme, target_kv260_readme, target_yosys_readme, target_asic_readme, target_readme_device_specific_isolation [INFERRED 0.85]
- **cnn_top SRAM-macro ASIC flow (wrapper, patch, verify, layout)** — target_asic_readme_wrom_sky130, target_asic_readme_ram_sdp_sky130, target_asic_ram_patch_wrom, target_asic_ram_check_ram_wrapper, target_asic_ram_test_wrom_load, target_asic_layout_cnn_macro [EXTRACTED 1.00]
- **KV260 build flow (block design, wrapper, XDC, synth)** — target_kv260_readme_create_bd, target_kv260_readme_kv260_top, target_kv260_readme_xdc, target_kv260_readme_synth_tcl, target_kv260_run [EXTRACTED 1.00]

## Communities (78 total, 23 thin omitted)

### Community 0 - "CNN Golden dan Kalibrasi"
Cohesion: 0.06
Nodes (35): AccOverflow, calibrate_requant(), check_acc(), cnn_forward(), conv3x3(), gap(), load_qmodel(), m0_shift_from_scale() (+27 more)

### Community 1 - "Anggaran Sumber Daya"
Cohesion: 0.06
Nodes (33): assess(), cycles_cnn(), fmt_markdown(), frontend_cycles_per_frame(), main(), Mem, memories(), mult_cost() (+25 more)

### Community 2 - "Dokumen Vault dan Konteks"
Cohesion: 0.07
Nodes (40): Indeks konteks SuaraTB, Pemetaan golden ke RTL, docs/img README (arsitektur.png), docs README, docs/result README, Laporan hasil SuaraTB, Peta jalan dan keterbatasan, Anggaran Fase 0 (+32 more)

### Community 3 - "Model Klinis"
Cohesion: 0.10
Nodes (21): audio_score(), boot(), clin_extended(), auc_ci(), cv_scores(), main(), gbm(), lr() (+13 more)

### Community 4 - "Testbench DSP Frame"
Cohesion: 0.11
Nodes (19): test_frames_and_energy(), test_random(), test_random(), StreamMonitor, uval(), assert_equal(), cases(), compare() (+11 more)

### Community 5 - "Kalibrasi Detektor"
Cohesion: 0.11
Nodes (26): choose_detector(), _det_streams(), ensemble(), _err_octave(), exp_detector(), exp_fft_width(), exp_mel_shift(), exp_quant_ranges() (+18 more)

### Community 6 - "Runner cocotb DSP"
Cohesion: 0.14
Nodes (12): test_runner(), test_runner(), test_runner(), send(), mem_param(), run(), test_runner(), test_runner() (+4 more)

### Community 7 - "Tabel FFT dan Log"
Cohesion: 0.11
Nodes (18): twiddle_q15(), log2_q(), log_lut(), main(), main(), _meta(), read_mem(), write_mem() (+10 more)

### Community 8 - "Data Batuk dan Energi"
Cohesion: 0.10
Nodes (17): cough_det(), Event, hop_energy(), raw_dir(), test_detector_finds_synthetic_coughs(), test_detector_floor_blocks_digital_silence_trigger(), test_detector_quiet_noise_no_events(), test_detector_refractory_and_noise_floor() (+9 more)

### Community 9 - "Testbench I2S dan Sistem"
Cohesion: 0.11
Nodes (14): i2s_mic(), test_rates(), test_runner(), test_samples(), reset(), start_clock(), uart_model.py model UART host, read_segment() (+6 more)

### Community 10 - "Arsitektur RTL DSP"
Cohesion: 0.08
Nodes (28): dsp_chain (window->fft512->power->mel->log_q->quant), feat_buf.sv ring buffer fitur, fft512.sv radix-2 DIT 1 butterfly, golden/blocks (spesifikasi bit-exact), log_q.sv log2 LUT 256, mel.sv filterbank 40 band sparse, window.sv Hamming 400 zero-pad 512, golden/gen/gen_cnn_rom.py (ROM bobot CNN) (+20 more)

### Community 11 - "Golden FFT512"
Cohesion: 0.14
Nodes (14): _bitrev(), fft512(), bit_length(), rshift_round(), sat(), _ref_fft(), test_bit_length_exact_large(), test_fft_impulse_and_sine() (+6 more)

### Community 12 - "Evaluasi Lintas Perangkat"
Cohesion: 0.18
Nodes (18): per_participant(), ci(), clip_vec(), cv_auc(), fit_apply(), load_tbs(), load_zambia(), main() (+10 more)

### Community 13 - "Audit Dataset"
Cohesion: 0.18
Nodes (10): fix_rows(), folder_fac(), main(), main(), device_of(), index_audio(), joined(), load_meta() (+2 more)

### Community 14 - "Uji Permutasi"
Cohesion: 0.15
Nodes (13): main(), groups(), main(), mk(), one_rep(), perm_job(), cv_auc(), main() (+5 more)

### Community 15 - "Golden Blok Front-end"
Cohesion: 0.15
Nodes (6): quant_feat(), test_quant_saturation_and_monotone(), _feat(), active_mask(), _job(), segment()

### Community 16 - "Path Data Golden"
Cohesion: 0.17
Nodes (12): build_dir(), data_root(), features_dir(), processed_dir(), runs_dir(), clip_feats(), main(), zambia_active() (+4 more)

### Community 17 - "Protokol Evaluasi"
Cohesion: 0.19
Nodes (11): auc_strat(), boot_delta(), boot_delta_reps(), evaluate(), main(), make_folds(), oof_scores(), perm_null() (+3 more)

### Community 18 - "Ekspor Model Kuantisasi"
Cohesion: 0.22
Nodes (12): act_scales(), cv_eval(), final_train(), float_layers(), _fq(), int_logits(), load(), main() (+4 more)

### Community 19 - "Setup Lingkungan WSL2"
Cohesion: 0.13
Nodes (15): env.sh script, SUARATB_DATA, link_data.sh script, cocotb 2.1.0, volare 0.20.6 (PDK manager), setup/README.md (Claude Code setup runbook), Follow-up ASIC work (cnn_top P16/P32, SS corner, antenna/slew), graphify repo graph (graphify-out/) (+7 more)

### Community 20 - "Host UART"
Cohesion: 0.19
Nodes (5): Device, golden_logit(), load_clip(), main(), pad_clip()

### Community 21 - "Segmentasi dan Jendela"
Cohesion: 0.16
Nodes (10): segment(), to_cnn_input(), apply_window(), hamming_q15(), mel_rom_words(), test_hamming_symmetric_and_close(), test_window_output_range_and_pad(), test_feat_buf_ring_addressing() (+2 more)

### Community 22 - "Testbench CNN"
Cohesion: 0.17
Nodes (6): test_logits(), test_trained(), sval(), wait_for(), np_array(), read_mem()

### Community 23 - "Front-end Golden"
Cohesion: 0.16
Nodes (10): features_q(), frame_signal(), input_floor_L(), log_mel_q(), log_mel_ref(), pad_clip(), power(), golden/blocks blok pengolahan (+2 more)

### Community 24 - "Laporan Hasil"
Cohesion: 0.12
Nodes (15): Laporan Lengkap SuaraTB, Akselerator CNN output-stationary P lane, Latensi CNN P=16 1,51 ms @150 MHz, Detektor batuk (K=8, EMA 2^-6), Keputusan penting K-04..K-23, Fase 0 parameter dan kalibrasi, Golden numpy bit-exact, Distilasi HeAR ke CNN golden (murid AUROC 0,654) (+7 more)

### Community 25 - "Sinyal Uji Sintetis"
Cohesion: 0.26
Nodes (9): click(), clip(), cough_burst(), _i16(), noise(), _shape(), speech_like(), stream() (+1 more)

### Community 26 - "Target KV260 dan Sapuan P"
Cohesion: 0.13
Nodes (12): pyserial (host UART), P sweep (16, 8, 32), run_sweep.sh script, target/kv260/README.md (Kria KV260), create_bd.tcl (kv260_clk block design), OOC Fmax ~333.7 MHz (suaratb_top only), kv260_top.sv wrapper, Pmod J2 pin mapping (UART, I2S INMP441, LEDs) (+4 more)

### Community 28 - "Distilasi HeAR"
Cohesion: 0.24
Nodes (9): cv(), embed(), final(), fit_probe(), load(), part_mean(), targets(), to_hw_net() (+1 more)

### Community 29 - "RTL Front-end Audio"
Cohesion: 0.13
Nodes (8): frame_buf, i2s_rx, preemph, ram_sdp, cough_det, feat_buf, csr, suaratb_top

### Community 31 - "Sintesis Artix-7 dan sv2v"
Cohesion: 0.13
Nodes (9): sv2v v0.0.13, main(), artix7 synth.tcl (Vivado OOC XC7A35T-1), synth_sky130.sh script, target/README.md (device-specific code), docs/vault/sintesis.md (synthesis results), Artix-7 XC7A35T-1 synthesis reference, sv2v + synth_xilinx -family xc7 (no timing) (+1 more)

### Community 32 - "Golden Mel"
Cohesion: 0.25
Nodes (10): _hz2mel(), _mel2hz(), mel_acc(), mel_energy(), mel_filterbank_float(), mel_sparse(), mel_weights_q(), test_mel_energy_matches_dense_float() (+2 more)

### Community 33 - "Tes Muat ROM dan Frame"
Cohesion: 0.19
Nodes (3): load_then_read(), test_runner(), test_runner()

### Community 34 - "Pelatihan MIL"
Cohesion: 0.19
Nodes (5): augment(), fit(), make_bags(), Net, part_logit()

### Community 35 - "Embedding Pralatih"
Cohesion: 0.24
Nodes (6): cmd_embed(), embed(), logmel(), _mel_module(), VGGish, zambia_clips()

### Community 36 - "Layout cnn_top Makro"
Cohesion: 0.37
Nodes (5): main(), fix(), layout(), run_ol(), summary()

### Community 37 - "Model Student Distilasi"
Cohesion: 0.19
Nodes (7): Student, run(), __init__(), probe(), sc_oof(), stat(), train_student()

### Community 38 - "Pelatihan MIL2"
Cohesion: 0.24
Nodes (6): aux_table(), fit(), main(), Net2, part_score(), prep()

### Community 39 - "Baseline CNN"
Cohesion: 0.27
Nodes (7): auc_ci(), main(), Net, part_scores(), predict(), to_t(), train()

### Community 40 - "Detektor Batuk RTL"
Cohesion: 0.24
Nodes (6): cough_det.sv (detektor batuk, 3 tahap pipeline), expect(), run_seq(), test_random_bursts(), test_runner(), test_synthetic_vectors()

### Community 41 - "Diagram Arsitektur"
Cohesion: 0.20
Nodes (11): cnn_top (3 Conv, GAP, FC), cough_det (EMA, ambang 8x), dsp_chain (FFT 512, mel, log2), feat_buf (segmen 40x50), frame_buf (400 / hop 160), i2s_rx (24 bit, MSB-first), Mikrofon I2S (INMP441), preemph (pre-emphasis 0,97) (+3 more)

### Community 42 - "Spesifikasi Golden Fase 0"
Cohesion: 0.20
Nodes (10): golden/analysis Fase 0, calibrate.py / calibrate_real.py, golden spesifikasi bit-exact, params.py parameter beku, suaratb_pkg.sv, rtl/audio, pe_array, rtl/cnn akselerator output-stationary (+2 more)

### Community 43 - "RTL Rantai DSP"
Cohesion: 0.18
Nodes (5): dsp_chain, mel, power, quant, window

### Community 44 - "Testbench Pre-emphasis"
Cohesion: 0.27
Nodes (4): test_runner(), test_saturation(), test_vectors(), StreamDriver

### Community 45 - "Wrapper RAM Makro sky130"
Cohesion: 0.29
Nodes (4): patched_cnn_top(), target/asic/README.md (sky130 ASIC feasibility), ram_sdp_sky130.sv (OpenRAM ram_sdp replacement), wrom_sky130.sv (weight ROM as SRAM macro, wl_* load port)

### Community 46 - "Kalibrasi Data Nyata"
Cohesion: 0.36
Nodes (8): detector_rates(), err_octave(), load_clips(), main(), mel_bits(), quant_ranges(), schedule_table(), width_table()

### Community 47 - "RTL Kontrol CNN"
Cohesion: 0.20
Nodes (6): cnn_ctrl, cnn_cfg_pkg, cnn_top, cnn_cfg_pkg, gap, requant

### Community 48 - "Kumpulan Hasil Layout"
Cohesion: 0.31
Nodes (4): final_dir(), main(), results/metrics.csv, 13 module layouts (DRC/LVS/XOR clean)

### Community 49 - "Ringkasan Model"
Cohesion: 0.33
Nodes (8): cnn.py QModel, clinical_models fusi gejala, model/data dataset Zambia CIDRZ, Distilasi HeAR ke CNN golden, evaluation protokol dan permutasi, pretrained VGGish HeAR OPERA, model pelatihan evaluasi, CNN dari nol (negatif AUROC 0,56)

### Community 50 - "Jadwal FFT"
Cohesion: 0.33
Nodes (5): bitrev(), schedule_fft(), test_drain_margin(), test_schedule_full_scale_and_impulse(), test_schedule_matches_golden_random()

### Community 51 - "HeAR Lintas Perangkat"
Cohesion: 0.28
Nodes (3): boot(), main(), per_participant()

### Community 52 - "RTL FFT dan ROM"
Cohesion: 0.22
Nodes (3): rom_sync, fft512, log_q

### Community 53 - "Pencari Fmax KV260"
Cohesion: 0.52
Nodes (4): cached(), run(), search(), snap()

### Community 55 - "RTL UART"
Cohesion: 0.33
Nodes (3): uart_bridge, uart_rx, uart_tx

### Community 56 - "Hasil Model Audio"
Cohesion: 0.50
Nodes (4): CNN dari nol AUROC ~0,56, Data: Zambia CIDRZ, TBscreen, CODA TB DREAM, Kuantisasi int8 (selisih AUROC <= 0,02), Perancu jenis kelamin dan klinik

### Community 58 - "Cek Lingkungan"
Cohesion: 1.00
Nodes (3): chk(), ok(), check_env.sh script

## Knowledge Gaps
- **49 isolated node(s):** `cnn_cfg_pkg`, `cnn_cfg_pkg`, `sva_stream`, `sync_fifo`, `uart_model.py model UART host` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 397 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `rtl/cnn akselerator output-stationary` connect `Spesifikasi Golden Fase 0` to `Ringkasan Model`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **What connects `cnn_cfg_pkg`, `cnn_cfg_pkg`, `sva_stream` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CNN Golden dan Kalibrasi` be split into smaller, more focused modules?**
  _Cohesion score 0.058173076923076925 - nodes in this community are weakly interconnected._
- **Why does `pe_array` connect `Spesifikasi Golden Fase 0` to `RTL Kontrol CNN`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Should `Anggaran Sumber Daya` be split into smaller, more focused modules?**
  _Cohesion score 0.0593990216631726 - nodes in this community are weakly interconnected._
- **Why does `cnn_top` connect `RTL Kontrol CNN` to `Spesifikasi Golden Fase 0`, `RTL FFT dan ROM`, `RTL Front-end Audio`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Should `Dokumen Vault dan Konteks` be split into smaller, more focused modules?**
  _Cohesion score 0.0673758865248227 - nodes in this community are weakly interconnected._