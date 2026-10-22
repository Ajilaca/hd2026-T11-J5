// wrom_sky130: ROM bobot CNN sebagai makro SRAM sky130 yang diisi saat boot (HANYA di target/asic; rtl/ tidak diubah).
// Pengganti instans u_wrom (rom_sync) di cnn_top lewat target/asic/ram/patch_wrom.py. ROM 116 Kbit yang disintesis jadi
// logika membuat routing macet (run d1 vs s1), jadi bobot disimpan di makro dan dimuat dari luar (port wl_*).
// Isi      : LANES = WIDTH/32 makro berdampingan x BANKS = ceil(DEPTH/512) baris; P=16: 4x2, P=32: 8x1 (8 makro).
// Antarmuka: baca sama dengan rom_sync (en, addr -> dout, 1 siklus, ditahan saat en=0).
//            muat: wl_we, wl_addr = {baris, lane} (lane di bit bawah, LB bit), wl_data = 32 bit untuk satu lane.
// Latensi  : 1 siklus (data makro keluar di paruh kedua siklus setelah alamat dilatch, dicuplik pemakai di tepi berikutnya).
// Simulasi : PRELOAD=1 mengisi model makro dari INIT_FILE (pengganti muat lewat UART/SPI); tidak disintesis.
module wrom_sky130 #(
  parameter int WIDTH   = 128,
  parameter int DEPTH   = 921,
  parameter     INIT_FILE = "",
  parameter int PRELOAD = 1
) (
  input  logic                     clk,
  input  logic                     en,
  input  logic [$clog2(DEPTH)-1:0] addr,
  output logic [WIDTH-1:0]         dout,
  input  logic                     wl_we,
  input  logic [15:0]              wl_addr,
  input  logic [31:0]              wl_data
);
  localparam int AW    = $clog2(DEPTH);
  localparam int LANES = WIDTH / 32;
  localparam int LB    = (LANES > 1) ? $clog2(LANES) : 1;
  localparam int BANKS = (DEPTH + 511) / 512;
  localparam int BAW   = (BANKS > 1) ? $clog2(BANKS) : 1;
  if (WIDTH % 32 != 0) begin : g_bad
    initial $error("wrom_sky130: WIDTH harus kelipatan 32 (WIDTH=%0d)", WIDTH);
  end

  logic [AW-1:0]   wrow;
  logic [LB-1:0]   wlane;
  logic [8:0]      wa, ra;
  logic [BAW-1:0]  wbank, rbank, rbank_q;
  logic            en_q;
  logic [31:0]     dq [0:BANKS-1][0:LANES-1];
  logic [WIDTH-1:0] cur, hold;

  assign wlane = wl_addr[LB-1:0];
  assign wrow  = wl_addr[LB +: AW];
  if (AW > 9) begin : g_ab
    assign wbank = wrow[AW-1:9];  assign rbank = addr[AW-1:9];
    assign wa = wrow[8:0];        assign ra = addr[8:0];
  end else begin : g_nb
    assign wbank = '0;            assign rbank = '0;
    assign wa = 9'(wrow);         assign ra = 9'(addr);
  end

`ifndef SYNTHESIS
  logic [WIDTH-1:0] init [0:DEPTH-1];
  initial if (PRELOAD != 0 && INIT_FILE != "") $readmemh(INIT_FILE, init);
`endif

  for (genvar b = 0; b < BANKS; b++) begin : g_bank
    for (genvar l = 0; l < LANES; l++) begin : g_lane
      sky130_sram_2kbyte_1rw1r_32x512_8 u_m (
        .clk0(clk), .csb0(~(wl_we && wbank == BAW'(b) && wlane == LB'(l))), .web0(1'b0), .wmask0(4'hF),
        .addr0(wa), .din0(wl_data), .dout0(),
        .clk1(clk), .csb1(~(en && rbank == BAW'(b))), .addr1(ra), .dout1(dq[b][l]));
`ifndef SYNTHESIS
      initial if (PRELOAD != 0 && INIT_FILE != "") begin
        #1;
        for (int r = 0; r < 512; r++) if (b * 512 + r < DEPTH) u_m.mem[r] = init[b * 512 + r][l * 32 +: 32];
      end
`endif
    end
  end

  always_comb for (int l = 0; l < LANES; l++) cur[l * 32 +: 32] = dq[rbank_q][l];
  assign dout = en_q ? cur : hold;          // rom_sync menahan dout saat en=0; makro tidak
  always_ff @(posedge clk) begin
    en_q    <= en;
    rbank_q <= rbank;
    hold    <= dout;
  end
endmodule
