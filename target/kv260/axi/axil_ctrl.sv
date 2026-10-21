// axil_ctrl: slave AXI4-Lite + file register untuk suaratb (menggantikan uart_bridge + csr pada jalur host).
// Fungsi    : PS (Linux/PYNQ) menulis klip dataset sampel demi sampel dan membaca hasil lewat register 32 bit.
// Peta (offset byte, alamat 12 bit; akses 32 bit; alamat di luar peta: baca 0, tulis diabaikan, selalu OKAY):
//   0x000 CTRL    RW  bit0 mode (0=dataset 1=mikrofon); bit1 clear (tulis 1: denyut bersih-bersih, selalu terbaca 0)
//   0x004 STATUS  R   bit0 cnn_busy, bit1 recording, bit2 result_new (hapus saat RESULT dibaca), bit3 ds_ready
//   0x008 RESULT  R   [15:0] logit (int16), [23:16] seq (jumlah hasil, modulo 256); membaca menghapus result_new
//   0x00C VERSION R   0xA1000001 ([31:24]=0xA1 wrapper AXI-Lite, [7:0]=0x01 sama dengan CSR VERSION UART)
//   0x010 NSAT    R   [15:0] maks. jumlah saturasi FFT per frame sejak clear
//   0x014 FRAMES  R   [15:0] jumlah frame fitur
//   0x018 DS_CTRL W   bit0=1: mulai klip dataset baru (membersihkan jalur DSP)
//   0x01C DS_DATA W   [15:0] satu sampel int16 klip; tulis ini DITAHAN (tanpa BVALID) sampai jarak DS_GAP siklus
//                     sejak sampel sebelumnya terpenuhi (frame_buf butuh >= FRAME_LEN+4 siklus antar sampel)
//   0x020 NSAMP   R   jumlah sampel per klip (8240)
// Parameter : DS_GAP (siklus min. antar sampel, default FRAME_LEN+16), N_SAMPLES
// Antarmuka : AXI4-Lite satu clock (clk); satu transaksi tulis dan satu baca pada satu waktu (tanpa pipeline).
//             AW dan W boleh datang dalam urutan apa pun; BRESP/RRESP selalu OKAY.
// Latensi   : tulis: 2 siklus setelah AW dan W diterima (+ penahanan DS_GAP); baca: 1 siklus setelah AR.
// Referensi : semantik register sama dengan rtl/sys/csr.sv; aliran dataset sama dengan rtl/sys/uart_bridge.sv.
module axil_ctrl #(
  parameter int DS_GAP    = suaratb_pkg::FRAME_LEN + 16,
  parameter int N_SAMPLES = suaratb_pkg::CLIP_SAMPLES_PADDED
) (
  input  logic        clk,
  input  logic        rst_n,
  // AXI4-Lite slave
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
  // ke inti
  output logic        mode_mic,
  output logic        clear_pulse,
  output logic        ds_start,
  output logic        ds_valid,
  output logic signed [15:0] ds_sample,
  // dari inti
  input  logic        cnn_busy,
  input  logic        recording,
  input  logic        res_valid,
  input  logic signed [15:0] res_logit,
  input  logic [15:0] nsat_frame,
  input  logic        nsat_valid,
  input  logic [15:0] frame_count,
  output logic        irq
);
  localparam logic [9:0] A_CTRL = 10'h000 >> 2, A_STATUS = 10'h004 >> 2, A_RESULT = 10'h008 >> 2, A_VERSION = 10'h00C >> 2,
                         A_NSAT = 10'h010 >> 2, A_FRAMES = 10'h014 >> 2, A_DS_CTRL = 10'h018 >> 2, A_DS_DATA = 10'h01C >> 2,
                         A_NSAMP = 10'h020 >> 2;
  localparam int GAP_W = $clog2(DS_GAP + 1);
  localparam logic [GAP_W-1:0] GAP_INIT = DS_GAP;

  assign s_axi_bresp = 2'b00;
  assign s_axi_rresp = 2'b00;

  logic        res_new, mic_r;
  logic [15:0] logit_r, nsat_max;
  logic [7:0]  seq;
  logic [GAP_W-1:0] gap_cnt;
  wire         ds_ready = (gap_cnt == '0);

  assign mode_mic = mic_r;
  assign irq      = res_new;

  // ---- kanal tulis -------------------------------------------------------------------------------------
  logic        aw_v, w_v;
  logic [11:0] aw_a;
  logic [31:0] w_d;
  logic [3:0]  w_s;
  assign s_axi_awready = !aw_v && !s_axi_bvalid;
  assign s_axi_wready  = !w_v  && !s_axi_bvalid;

  wire [9:0] aw_w   = aw_a[11:2];
  wire       wr_go  = aw_v && w_v && !s_axi_bvalid && !(aw_w == A_DS_DATA && !ds_ready);

  // ---- kanal baca --------------------------------------------------------------------------------------
  assign s_axi_arready = !s_axi_rvalid;
  wire   rd_go = s_axi_arvalid && s_axi_arready;

  logic [31:0] s_axi_rdata_n;
  always_comb begin
    case (s_axi_araddr[11:2])
      A_CTRL:    s_axi_rdata_n = {31'd0, mic_r};
      A_STATUS:  s_axi_rdata_n = {28'd0, ds_ready, res_new, recording, cnn_busy};
      A_RESULT:  s_axi_rdata_n = {8'd0, seq, logit_r};
      A_VERSION: s_axi_rdata_n = 32'hA100_0001;
      A_NSAT:    s_axi_rdata_n = {16'd0, nsat_max};
      A_FRAMES:  s_axi_rdata_n = {16'd0, frame_count};
      A_NSAMP:   s_axi_rdata_n = 32'(N_SAMPLES);
      default:   s_axi_rdata_n = 32'd0;
    endcase
  end

  always_ff @(posedge clk) begin
    clear_pulse <= 1'b0;
    ds_start    <= 1'b0;
    ds_valid    <= 1'b0;
    if (gap_cnt != '0) gap_cnt <= gap_cnt - 1'b1;

    if (!rst_n) begin
      aw_v         <= 1'b0;
      w_v          <= 1'b0;
      s_axi_bvalid <= 1'b0;
      s_axi_rvalid <= 1'b0;
      s_axi_rdata  <= '0;
      mic_r        <= 1'b0;
      res_new      <= 1'b0;
      logit_r      <= '0;
      nsat_max     <= '0;
      seq          <= '0;
      gap_cnt      <= '0;
    end else begin
      // tulis: tangkap AW dan W secara terpisah
      if (s_axi_awvalid && s_axi_awready) begin aw_v <= 1'b1; aw_a <= s_axi_awaddr; end
      if (s_axi_wvalid  && s_axi_wready)  begin w_v  <= 1'b1; w_d  <= s_axi_wdata; w_s <= s_axi_wstrb; end
      if (wr_go) begin
        aw_v         <= 1'b0;
        w_v          <= 1'b0;
        s_axi_bvalid <= 1'b1;
        case (aw_w)
          A_CTRL: if (w_s[0]) begin
            mic_r <= w_d[0];
            if (w_d[1]) begin
              clear_pulse <= 1'b1;
              nsat_max    <= '0;
              res_new     <= 1'b0;
            end
          end
          A_DS_CTRL: if (w_s[0] && w_d[0]) begin
            ds_start <= 1'b1;
            gap_cnt  <= GAP_INIT;       // inti ditahan reset lunak beberapa siklus setelah ds_start
          end
          A_DS_DATA: if (w_s[1:0] == 2'b11) begin
            ds_valid  <= 1'b1;
            ds_sample <= w_d[15:0];
            gap_cnt   <= GAP_INIT;
          end
          default: ;
        endcase
      end
      if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 1'b0;

      // baca
      if (rd_go) begin
        s_axi_rvalid <= 1'b1;
        s_axi_rdata  <= s_axi_rdata_n;
        if (s_axi_araddr[11:2] == A_RESULT) res_new <= 1'b0;
      end
      if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 1'b0;

      // hasil inferensi dan statistik (didahulukan atas penghapusan di atas)
      if (res_valid) begin
        logit_r <= res_logit;
        seq     <= seq + 8'd1;
        res_new <= 1'b1;
      end
      if (nsat_valid && nsat_frame > nsat_max) nsat_max <= nsat_frame;
    end
  end
endmodule
