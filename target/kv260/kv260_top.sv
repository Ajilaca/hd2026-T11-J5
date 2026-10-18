// kv260_top: pembungkus khusus papan Kria KV260 (Zynq UltraScale+ XCK26) untuk suaratb_top.
// Fungsi   : memasang clock inti dari block design (PS pl_clk0 -> MMCM), menyinkronkan reset dan masukan asinkron
//            (uart_rx, i2s_sd), lalu meneruskan ke suaratb_top. suaratb_top TIDAK diubah.
// Parameter: UART_BAUD (default 115200), CORE_HZ (frekuensi nominal clock inti; dipakai hanya untuk membagi CLK_PER_*),
//            INIT_* (berkas .mem; diberikan absolut oleh synth.tcl)
// Port     : lihat kv260.xdc (semuanya di Pmod 3,3 V). UART PL harus keluar lewat Pmod ke adaptor USB-UART 3,3 V.
// Latensi  : 2 siklus clock untuk tiap masukan tersinkron.
// Catatan  : kode spesifik perangkat (atribut ASYNC_REG, BD wrapper) hanya ada di target/.
module kv260_top #(
  parameter int UART_BAUD = 115200,
  parameter int CORE_HZ   = 300_032_000,                       // 293 x 1,024 MHz (K-24; K-22 untuk Artix-7)
  parameter     INIT_W    = "tb/vectors/cnn/cnn_wrom.mem",
  parameter     INIT_B    = "tb/vectors/cnn/cnn_bias.mem",
  parameter     INIT_RQ   = "tb/vectors/cnn/cnn_rq.mem",
  parameter     INIT_WIN  = "rtl/mem/window_hamming.mem",
  parameter     INIT_COS  = "rtl/mem/twiddle_cos.mem",
  parameter     INIT_SIN  = "rtl/mem/twiddle_sin.mem",
  parameter     INIT_MEL  = "rtl/mem/mel_rom.mem",
  parameter     INIT_LOG  = "rtl/mem/log_lut.mem"
) (
  input  logic uart_rx,      // Pmod: dari TXD adaptor USB-UART
  output logic uart_tx,      // Pmod: ke RXD adaptor USB-UART
  output logic i2s_bclk,     // Pmod: ke SCK INMP441
  output logic i2s_ws,       // Pmod: ke WS INMP441
  input  logic i2s_sd,       // Pmod: dari SD INMP441
  output logic led_busy,     // Pmod (opsional): CNN sibuk
  output logic led_rec       // Pmod (opsional): sedang merekam
);
  localparam int CLK_PER_BIT  = CORE_HZ / UART_BAUD;           // 300,032 MHz / 115200 = 2604 (dibulatkan ke bawah)
  localparam int CLK_PER_BCLK = CORE_HZ / 1_024_000;           // BCLK = 16 kHz x 64 = 1,024 MHz -> 144

  logic core_clk, core_rst_n_bd;
  kv260_clk_wrapper u_clk (.core_clk(core_clk), .core_rst_n(core_rst_n_bd));

  // sinkronisasi reset (lepas sinkron ke core_clk) dan masukan asinkron
  (* ASYNC_REG = "TRUE" *) logic [1:0] rst_sync = 2'b00;
  (* ASYNC_REG = "TRUE" *) logic [1:0] rx_sync  = 2'b11;
  (* ASYNC_REG = "TRUE" *) logic [1:0] sd_sync  = 2'b00;
  always_ff @(posedge core_clk or negedge core_rst_n_bd) begin
    if (!core_rst_n_bd) rst_sync <= 2'b00;
    else                rst_sync <= {rst_sync[0], 1'b1};
  end
  always_ff @(posedge core_clk) begin
    rx_sync <= {rx_sync[0], uart_rx};
    sd_sync <= {sd_sync[0], i2s_sd};
  end

  suaratb_top #(
    .CLK_PER_BIT(CLK_PER_BIT), .CLK_PER_BCLK(CLK_PER_BCLK),
    .INIT_W(INIT_W), .INIT_B(INIT_B), .INIT_RQ(INIT_RQ),
    .INIT_WIN(INIT_WIN), .INIT_COS(INIT_COS), .INIT_SIN(INIT_SIN), .INIT_MEL(INIT_MEL), .INIT_LOG(INIT_LOG)
  ) u_core (
    .clk(core_clk), .rst_n(rst_sync[1]),
    .bclk(i2s_bclk), .ws(i2s_ws), .sd(sd_sync[1]),
    .uart_rx(rx_sync[1]), .uart_tx(uart_tx),
    .led_busy(led_busy), .led_rec(led_rec)
  );
endmodule
