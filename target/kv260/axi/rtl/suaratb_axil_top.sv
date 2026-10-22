// suaratb_axil_top: suaratb dengan antarmuka host AXI4-Lite (pengganti UART). Inti (i2s_rx -> preemph -> frame_buf ->
//            dsp_chain -> feat_buf -> cnn_top, cough_det, sekuenser segmen) sama dengan versi UART lama (rtl/sys/suaratb_top.sv, dihapus 2026-10-22; ada di riwayat git dan tag submission); hanya
//            host AXI4-Lite (axil_ctrl) menggantikan antarmuka UART lama. Sumber sampel: mikrofon I2S (mode 1) atau klip dataset lewat AXI (mode 0).
// Parameter : CLK_PER_BCLK (I2S; 293 pada 300,032 MHz), DS_GAP (jarak sampel dataset), INIT_* (.mem CNN dan DSP)
// Antarmuka : clk (inti, juga clock AXI), rst_n, s_axi_* (AXI4-Lite 12 bit alamat, 32 bit data), i2s (bclk/ws/sd),
//             led_busy/led_rec, irq (result_new)
// Catatan   : glue sistem (satu-satunya top level sejak UART dihapus); tb/sys/test_axil.py membandingkan hasil dengan golden
//             sehingga perbedaan perilaku akan terdeteksi.
module suaratb_axil_top #(
  parameter int CLK_PER_BCLK = 293,
  parameter int DS_GAP       = suaratb_pkg::FRAME_LEN + 16,
  parameter     INIT_W  = "tb/vectors/cnn/cnn_wrom.mem",
  parameter     INIT_B  = "tb/vectors/cnn/cnn_bias.mem",
  parameter     INIT_RQ = "tb/vectors/cnn/cnn_rq.mem",
  parameter     INIT_WIN = "rtl/mem/window_hamming.mem",
  parameter     INIT_COS = "rtl/mem/twiddle_cos.mem",
  parameter     INIT_SIN = "rtl/mem/twiddle_sin.mem",
  parameter     INIT_MEL = "rtl/mem/mel_rom.mem",
  parameter     INIT_LOG = "rtl/mem/log_lut.mem"
) (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [11:0] s_axi_awaddr,
  input  logic        s_axi_awvalid,
  output logic        s_axi_awready,
  input  logic [31:0] s_axi_wdata,
  input  logic [3:0]  s_axi_wstrb,
  input  logic        s_axi_wvalid,
  output logic        s_axi_wready,
  output logic [1:0]  s_axi_bresp,
  output logic        s_axi_bvalid,
  input  logic        s_axi_bready,
  input  logic [11:0] s_axi_araddr,
  input  logic        s_axi_arvalid,
  output logic        s_axi_arready,
  output logic [31:0] s_axi_rdata,
  output logic [1:0]  s_axi_rresp,
  output logic        s_axi_rvalid,
  input  logic        s_axi_rready,
  output logic bclk,
  output logic ws,
  input  logic sd,
  output logic led_busy,
  output logic led_rec,
  output logic irq
);
  localparam int PF = suaratb_pkg::PREEMPH_FRAC;
  localparam int W  = suaratb_pkg::FFT_W;

  // ---- host AXI4-Lite ----------------------------------------------------------------------------------
  logic        ds_start, ds_valid;
  logic signed [15:0] ds_sample;
  logic        res_valid;
  logic signed [15:0] res_logit;
  logic        mode_mic, clear_pulse;
  logic        cnn_busy, recording;
  logic [15:0] frame_count16, nsat16;
  logic        nsat_valid;

  axil_ctrl #(.DS_GAP(DS_GAP)) u_ctrl (
    .clk(clk), .rst_n(rst_n),
    .s_axi_awaddr(s_axi_awaddr), .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb), .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid), .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr), .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid), .s_axi_rready(s_axi_rready),
    .mode_mic(mode_mic), .clear_pulse(clear_pulse), .ds_start(ds_start), .ds_valid(ds_valid), .ds_sample(ds_sample),
    .cnn_busy(cnn_busy), .recording(recording), .res_valid(res_valid), .res_logit(res_logit),
    .nsat_frame(nsat16), .nsat_valid(nsat_valid), .frame_count(frame_count16), .irq(irq));

  // ---- reset lunak untuk jalur DSP (ds_start / clear) ---------------------------------------------------
  logic [2:0] clr_cnt;
  logic       mode_q;                                     // pindah mode membersihkan jalur DSP (sisa sampel mode lama)
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      clr_cnt <= '0;
      mode_q  <= 1'b0;
    end else begin
      mode_q <= mode_mic;
      if (ds_start || clear_pulse || (mode_mic != mode_q)) clr_cnt <= 3'd5;
      else if (clr_cnt != 0) clr_cnt <= clr_cnt - 3'd1;
    end
  end
  logic core_rst_n;                                      // terdaftar: jaringan reset fanout tinggi tidak di jalur kritis
  always_ff @(posedge clk) core_rst_n <= rst_n && (clr_cnt == 3'd0) && !(ds_start || clear_pulse || (mode_mic != mode_q));


  // ---- sumber sampel -------------------------------------------------------------------------------
  logic        mic_valid;
  logic signed [15:0] mic_sample;
  i2s_rx #(.CLK_PER_BCLK(CLK_PER_BCLK)) u_i2s (
    .clk(clk), .rst_n(rst_n), .en(mode_mic), .bclk(bclk), .ws(ws), .sd(sd),
    .sample(mic_sample), .sample_valid(mic_valid));

  wire        s_valid  = mode_mic ? mic_valid  : ds_valid;
  wire signed [15:0] s_sample = mode_mic ? mic_sample : ds_sample;

  // ---- front-end -------------------------------------------------------------------------------------
  logic        pe_valid;
  logic signed [15+PF:0] pe_wide;
  logic signed [15:0]    pe_s16;
  preemph u_pe (.clk(clk), .rst_n(core_rst_n), .in_valid(s_valid), .in_sample(s_sample),
                .out_valid(pe_valid), .out_wide(pe_wide), .out_s16(pe_s16));

  logic        fr_valid, fr_first, fr_last, e_valid;
  logic signed [15+PF:0] fr_data;
  logic [31:0] fr_idx;
  logic [47:0] e_out;
  frame_buf u_fb (.clk(clk), .rst_n(core_rst_n), .in_valid(pe_valid), .in_wide(pe_wide), .in_s16(pe_s16),
                  .frame_valid(fr_valid), .frame_data(fr_data), .frame_first(fr_first), .frame_last(fr_last),
                  .frame_idx(fr_idx), .e_valid(e_valid), .e_out(e_out));

  logic        det_trig, det_segdone;
  logic [31:0] det_onset, det_start, det_end;
  cough_det u_det (.clk(clk), .rst_n(core_rst_n), .e_valid(e_valid), .e(e_out), .trig(det_trig), .onset_frame(det_onset),
                   .start_frame(det_start), .end_frame(det_end), .seg_done(det_segdone), .recording(recording));

  // ---- DSP + feat_buf ---------------------------------------------------------------------------------
  logic        q_valid, q_last, fft_done;
  logic signed [7:0] q_data;
  logic [5:0]  q_idx;
  logic [31:0] n_sat;
  dsp_chain #(.INIT_WIN(INIT_WIN), .INIT_COS(INIT_COS), .INIT_SIN(INIT_SIN), .INIT_MEL(INIT_MEL), .INIT_LOG(INIT_LOG)) u_dsp (
    .clk(clk), .rst_n(core_rst_n), .in_valid(fr_valid), .in_data(fr_data), .in_first(fr_first),
    .out_valid(q_valid), .out_q(q_data), .out_idx(q_idx), .out_last(q_last), .fft_done(fft_done), .n_sat(n_sat));

  logic        seg_go, fb_valid, fb_last, seg_busy;
  logic signed [7:0] fb_q;
  logic [10:0] fb_addr;
  logic [31:0] seg_start, frame_count;
  feat_buf u_feat (.clk(clk), .rst_n(core_rst_n), .in_valid(q_valid), .in_q(q_data), .in_idx(q_idx), .in_last(q_last),
                   .seg_go(seg_go), .seg_start(seg_start), .out_valid(fb_valid), .out_q(fb_q), .out_addr(fb_addr),
                   .out_last(fb_last), .seg_busy(seg_busy), .frame_count(frame_count));
  assign frame_count16 = frame_count[15:0];
  assign nsat16        = n_sat[15:0];
  assign nsat_valid    = fft_done;

  // ---- sekuenser segmen -> inferensi -----------------------------------------------------------------
  typedef enum logic [1:0] {P_IDLE, P_WAIT, P_READ, P_INFER} p_t;
  p_t          p_state;
  logic [31:0] p_start, p_end;
  logic        cnn_start, cnn_done;
  logic signed [15:0] logit;
  logic        ds_arm;                                    // klip dataset baru menunggu diproses
  always_ff @(posedge clk) begin
    if (!rst_n) ds_arm <= 1'b0;
    else if (ds_start) ds_arm <= 1'b1;
    else if (core_rst_n && p_state == P_IDLE && !mode_mic && ds_arm && frame_count >= 32'(suaratb_pkg::N_FRAMES)) ds_arm <= 1'b0;
  end

  always_ff @(posedge clk) begin
    seg_go    <= 1'b0;
    cnn_start <= 1'b0;
    res_valid <= 1'b0;
    if (!rst_n || !core_rst_n) begin
      p_state <= P_IDLE;
    end else begin
      case (p_state)
        P_IDLE: begin
          if (mode_mic && det_trig) begin
            p_start <= det_start;
            p_end   <= det_start + 32'(suaratb_pkg::N_FRAMES - 1);   // start terpotong di 0: tunggu sampai frame ke-N
            p_state <= P_WAIT;
          end else if (!mode_mic && ds_arm && frame_count >= 32'(suaratb_pkg::N_FRAMES)) begin
            p_start <= 32'd0;
            p_end   <= 32'(suaratb_pkg::N_FRAMES - 1);
            p_state <= P_WAIT;
          end
        end
        P_WAIT: begin                                 // tunggu fitur frame terakhir segmen tertulis
          if (frame_count > p_end && !cnn_busy) begin
            seg_go    <= 1'b1;
            seg_start <= p_start;
            p_state   <= P_READ;
          end
        end
        P_READ: begin
          if (fb_valid && fb_last) begin
            cnn_start <= 1'b1;
            p_state   <= P_INFER;
          end
        end
        P_INFER: begin
          if (cnn_done) begin
            res_valid <= 1'b1;
            res_logit <= logit;
            p_state   <= P_IDLE;
          end
        end
      endcase
    end
  end

  cnn_top #(.INIT_W(INIT_W), .INIT_B(INIT_B), .INIT_RQ(INIT_RQ)) u_cnn (
    .clk(clk), .rst_n(rst_n), .ld_valid(fb_valid), .ld_addr(fb_addr), .ld_q(fb_q), .start(cnn_start),
    .busy(cnn_busy), .done(cnn_done), .logit(logit));

  assign led_busy = cnn_busy;
  assign led_rec  = recording;
endmodule
