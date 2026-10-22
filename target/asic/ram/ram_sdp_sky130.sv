// ram_sdp_sky130: pengganti ram_sdp untuk flow ASIC sky130 (HANYA di target/asic; rtl/ tidak diubah).
// Nama modul, parameter, dan port SAMA dengan rtl/common/ram_sdp.sv, jadi cnn_top/fft512/frame_buf/feat_buf tidak berubah.
// Isi      : makro OpenRAM sky130_sram_2kbyte_1rw1r_32x512_8 (512 kata x 32 bit, mask tulis per byte). Port 0 hanya menulis,
//            port 1 hanya membaca. Untuk WIDTH <= 32, PACK elemen dikemas dalam satu kata makro (WIDTH<=8: 4, <=16: 2, lainnya 1);
//            alamat tinggi memilih bank (BANKS = ceil(DEPTH / (512*PACK))), alamat rendah memilih elemen dalam kata.
// Latensi  : data baca keluar dari makro di paruh kedua siklus setelah alamat dilatch; rdata = dout1 (kombinasional, dipilih
//            bank dan elemen) dan dicuplik flip-flop pemakai pada tepi berikutnya, sama dengan rdata terdaftar di ram_sdp.
// Beda     : ram_sdp menahan rdata saat re=0 dan memberi data LAMA pada baca-saat-tulis alamat sama; makro tidak menjamin
//            keduanya. Kecocokan dengan pemakaian di cnn_top diperiksa lewat simulasi (target/asic/ram/check_ram_wrapper.py).
module ram_sdp #(
  parameter int WIDTH = 8,
  parameter int DEPTH = 256
) (
  input  logic                     clk,
  input  logic                     we,
  input  logic [$clog2(DEPTH)-1:0] waddr,
  input  logic [WIDTH-1:0]         wdata,
  input  logic                     re,
  input  logic [$clog2(DEPTH)-1:0] raddr,
  output logic [WIDTH-1:0]         rdata
);
  localparam int AW    = $clog2(DEPTH);
  localparam int SLOTW = (WIDTH <= 8) ? 8 : (WIDTH <= 16) ? 16 : 32;   // bit per elemen dalam kata makro
  localparam int PACK  = 32 / SLOTW;                                   // elemen per kata makro: 4, 2, 1
  localparam int SB    = $clog2(PACK);                                 // bit alamat untuk memilih elemen
  localparam int WPB   = 512 * PACK;                                   // elemen per bank
  localparam int BANKS = (DEPTH + WPB - 1) / WPB;
  localparam int BAW   = (BANKS > 1) ? $clog2(BANKS) : 1;
  localparam int MB    = SB + 9;                                       // bit alamat di dalam bank
  localparam int BPS   = SLOTW / 8;                                    // byte per elemen
  if (WIDTH > 32) begin : g_bad
    initial $error("ram_sdp_sky130: WIDTH > 32 tidak didukung (WIDTH=%0d)", WIDTH);
  end

  logic [AW-1:0]  waddr_x, raddr_x;
  logic [8:0]     wa, ra;
  logic [BAW-1:0] wbank, rbank, rbank_q;
  logic [(SB>0?SB:1)-1:0] wsub, rsub, rsub_q;
  logic [31:0]    wd, dq [0:BANKS-1];
  logic [3:0]     wm;
  logic [SLOTW-1:0] sel;

  assign waddr_x = waddr;  assign raddr_x = raddr;
  if (SB > 0) begin : g_sub
    assign wsub = waddr_x[SB-1:0];  assign rsub = raddr_x[SB-1:0];
  end else begin : g_nosub
    assign wsub = '0;  assign rsub = '0;
  end
  if (AW > MB) begin : g_ab
    assign wbank = waddr_x[AW-1:MB];  assign rbank = raddr_x[AW-1:MB];
  end else begin : g_nb
    assign wbank = '0;  assign rbank = '0;
  end
  if (AW > SB + 9) begin : g_wa_full
    assign wa = waddr_x[SB+8:SB];  assign ra = raddr_x[SB+8:SB];
  end else begin : g_wa_short
    assign wa = 9'(waddr_x >> SB);  assign ra = 9'(raddr_x >> SB);
  end

  // data tulis diulang di semua slot; mask byte memilih slot yang benar-benar ditulis
  always_comb begin
    wd = '0;  wm = '0;
    for (int p = 0; p < PACK; p++) begin
      wd[p*SLOTW +: SLOTW] = SLOTW'(wdata);
      if (p == int'(wsub)) for (int b = 0; b < BPS; b++) wm[p*BPS + b] = 1'b1;
    end
  end

  for (genvar b = 0; b < BANKS; b++) begin : g_bank
    sky130_sram_2kbyte_1rw1r_32x512_8 u_m (
      .clk0(clk), .csb0(~(we && wbank == BAW'(b))), .web0(1'b0), .wmask0(wm), .addr0(wa), .din0(wd), .dout0(),
      .clk1(clk), .csb1(~(re && rbank == BAW'(b))), .addr1(ra), .dout1(dq[b]));
  end

  always_ff @(posedge clk) begin
    rbank_q <= rbank;
    rsub_q  <= rsub;
  end
  always_comb begin
    sel = dq[rbank_q][int'(rsub_q)*SLOTW +: SLOTW];
  end
  assign rdata = sel[WIDTH-1:0];
endmodule
