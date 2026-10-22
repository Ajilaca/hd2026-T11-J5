"""Layout OpenLane (sky130A, 25 ns) untuk cnn_top dengan RAM = makro SRAM sky130 (wrapper target/asic/ram/ram_sdp_sky130.sv).
Dari ROOT repo: WROM=sram P=16 python target/asic/scripts/layout_cnn_macro.py [tag]
  env: P (16/32), SV2V (path sv2v, bawaan: sv2v di PATH), DOCKER_MEM, DOCKER_CPUS, CLK_NS, STA_THREADS, KLAYOUT_THREADS
       (bawaan 6), FIX=1 (perbaikan slew/kapasitansi/antena kabel panjang, lihat FIX_CFG), SKIP_STEPS (id langkah OpenLane dipisah koma, mis. "Magic.WriteLEF"), TRDRC_ERR,
       SIGNOFF (WROM=sram): "ip" (bawaan) = makro SRAM sebagai IP terverifikasi: XOR, Magic DRC, KLayout DRC OpenLane
       dilewati; setelah run, XOR dan KLayout DRC dijalankan pada GDS tanpa makro (signoff_nomacro.py); LVS tetap penuh.
       "full" = semua pemeriksaan OpenLane termasuk isi makro (P16: > 4 jam, > 25 GB memori+swap, XOR 41,7 juta selisih
       dan Magic DRC 33 juta pelanggaran, semua di dalam makro; KLayout DRC macet di aturan li/areaid_ce).
  butuh: Docker + citra openlane2 2.3.10, PDK sky130A lewat volare di ~/.volare, $SUARATB_DATA/build/synth/P<P>/
         (target/prep_synth.py). Magic WriteLEF P16 memakai sekitar 9 GB RAM (WSL 10 GB + swap cukup).
Keluaran WROM=sram: $SUARATB_DATA/build/asic/cnn_top/p<P>/ (masukan), .../p<P>/run/ (hasil OpenLane, dipindah dari runs/<tag>),
  .../p<P>/signoff_nomacro/ (SIGNOFF=ip: GDS tanpa makro, xor.xml, drc.xml, summary.json).
Mode lain (diagnosis lama): cnn_top_macro*. Penempatan makro manual: baris atas di tepi atas, sisanya di tepi bawah, logika di tengah.
"""
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys

D = pathlib.Path(os.environ.get("SUARATB_DATA", "/data/suaratb"))
ROOT = pathlib.Path(__file__).resolve().parents[3]
P = int(os.environ.get("P", "16"))
WROM = os.environ.get("WROM") == "sram"   # ROM bobot sebagai 8 makro SRAM + port muat wl_* (ram/wrom_sky130.sv, ram/patch_wrom.py)
TAG = sys.argv[1] if len(sys.argv) > 1 else (f"p{P}" if WROM else "m1")
GAP = int(os.environ.get("GAP", "40"))              # celah antar-makro (um)
if WROM:
    W = D / "build/asic/cnn_top" / f"p{P}"
else:
    W = D / "build/asic" / ("cnn_top_macro" + (f"_P{P}" if P != 16 else "") + (f"_g{GAP}" if GAP != 40 else "")
                             + ("_stub" if os.environ.get("WROM_STUB") == "1" else ""))
SV2V = os.environ.get("SV2V") or shutil.which("sv2v") or "/data/tools/sv2v/sv2v-Linux/sv2v"
IMG = "ghcr.io/efabless/openlane2:2.3.10"
MAC = "sky130_sram_2kbyte_1rw1r_32x512_8"
VOLARE = pathlib.Path.home() / ".volare/volare/sky130/versions"
HASH = next(VOLARE.iterdir()).name
MROOT = f"/pdk/volare/sky130/versions/{HASH}/sky130A/libs.ref/sky130_sram_macros"
MW, MH = 683.1, 416.54
WROM_DEPTH = {16: 921, 32: 489}                # dari build/synth/P<P>/cnn_cfg_pkg.sv
COLS, ROWS = (4, 4) if WROM else (3, 2)
# FLOOR=2 (WROM=sram): floorplan ulang. Pin makro OpenRAM (LEF): port baca dout1/clk1/sebagian addr1 di sisi ATAS, sisa
# addr1 di kanan; port tulis din0/dout0/wmask0 di BAWAH, sisa addr0/clk0 di kiri. FLOOR=1 (lama): semua orientasi N, sehingga
# port baca baris atas menghadap tepi die, dua baris bertumpuk dengan celah 40 um, pita logika 960 um (utilisasi ~14%).
# FLOOR=2: baris di atas pita logika diorientasi FS (cermin) agar port baca menghadap pita logika; baris luar = ROM bobot
# (port muat wl_* menghadap tepi die/pin IO), baris dalam = RAM aktivasi; celah antar-baris bertumpuk ROWGAP (kanal routing);
# pita logika BAND (bawaan FLOOR=2: 600 um).
FLOOR = int(os.environ.get("FLOOR", "1"))
ROWGAP = int(os.environ.get("ROWGAP", "120"))
BAND = int(os.environ.get("BAND", "600" if FLOOR == 2 and WROM else "960"))  # tinggi pita logika (um) di antara baris makro atas dan bawah
DIE_W = int(COLS * (MW + GAP) + GAP + 40)
DIE_H = int(4 * MH + 2 * ROWGAP + 4 * GAP + BAND) if FLOOR == 2 and WROM else int(ROWS * (MH + GAP) + GAP + BAND)


IP = WROM and os.environ.get("SIGNOFF", "ip") == "ip"
# SIGNOFF=ip: pemeriksaan OpenLane yang membaca isi makro OpenRAM dilewati (lihat docstring); diganti signoff_nomacro.py.
IP_SKIP = ["KLayout.XOR", "Magic.DRC", "KLayout.DRC", "Checker.MagicDRC", "Checker.KLayoutDRC"] if IP else []
SKIP = [x for st in os.environ.get("SKIP_STEPS", "").split(",") + IP_SKIP if st for x in ("--skip", st)]
# FIX=1: perbaikan slew/kapasitansi/antena untuk kabel panjang antara pita logika dan pin makro (die ~3 x 3 mm). Run P16
# tanpa FIX: slew 1.612 / kap. 535 (corner terburuk; kap. ~500 juga di TT/FF), terutama pin dout makro (batas lib OpenRAM
# 0,028 pF), pin addr/din makro, buffer kabel yang memikul 0,4-0,55 pF, dan port clk -> buffer akar CTS (slew 1,77 ns);
# antena 133 net. Tanpa dioda heuristik (di mel menambah beban dan memperburuk slew).
# Tahap 1 (kabel 600 um, CTS_CLK_MAX_WIRE_LENGTH 400, perbaikan pasca-GRT): slew 1.612 -> 673, kap. 535 -> 204, routing 0,
# TT/FF bersih; tetapi antena 133 -> 189 (net buffer panjang), setup SS +0,24 -> -2,32 ns, hold SS -0,82 -> -2,08 ns:
# buffer kabel clock menambah latensi ke pin clk makro (~4,9 -> ~6,9 ns di SS), dan setelah perbaikan pasca-GRT (+331 buffer)
# tidak ada optimasi timing lagi (OpenLane: RUN_POST_GRT_RESIZER_TIMING bawaan False; resizer sudah memakai semua corner PDK).
# Tahap 2 (kabel 400 um + optimasi timing pasca-GRT): +1.300 buffer, slew 673 -> 656, kap. 204 -> 194, antena 189 -> 211,
# hold TT +0,29 -> -0,21 ns (detailed routing mengubah delay setelah perbaikan hold tanpa margin). Sisa slew/kap. sebagian besar
# di pin makro: batas lib OpenRAM max_transition 0,04 ns (addr/din/wmask) dan max_capacitance 17-28 fF (dout), tidak tercapai
# secara fisik; sisa di sel standar: buffer besar (buf_8/buf_6/clkbuf_16) di atas batas desain 0,2 pF. Antena: rasio side-area
# met1 di input sel kecil (buf_1, clkbuf_1, mux2_1); bertambah seiring jumlah buffer.
# Tahap 3: dasar tahap 1 (kabel 600 um), optimasi timing pasca-GRT dengan margin hold 0,2 ns, dioda heuristik hanya untuk
# net > 200 um (bukan semua net seperti percobaan mel).
# Tahap 3: routing 0, LVS 0, XOR/DRC tanpa makro 0, setup/hold TT dan FF bersih (hold TT +0,46 ns), antena 211 -> 74,
# slew sel standar (TT) 111 -> 50; +3.601 buffer hold (sel 97.478). Sisa antena: 73 dari 74 rasio side-area met1 (407-2.545,
# batas 400), yaitu kabel sinyal met1 panjang (PDK: GRT_LAYER_ADJUSTMENTS met1 = 0, kapasitas met1 penuh).
# Tahap 4 (kapasitas met1 global routing -60%): gagal GRT-0118 (kemacetan lokal di pita logika/pin makro; pemakaian total
# met1 tahap 3 hanya 14,6%, met2 12,1%). Tahap 5: kembali ke tahap 3, dioda heuristik untuk net > 100 um, margin antena 30%.
# Tahap 5: routing 0, LVS 0, XOR/DRC tanpa makro 0, antena 55. Analisis: perbaikan antena GRT berhasil (723 -> 11), tetapi DRT
# membuat 55 pelanggaran BARU, semuanya met1 side-area pada segmen met1 HORIZONTAL panjang (111-548 um), 21 di celah antar-makro
# dan 19 di pita logika; sel pelanggar adalah logika biasa (bukan sel baru dari resizer). Perbaikan antena setelah DRT tidak
# bisa dipakai di OpenROAD versi ini (repair_antennas tetap berbasis GRT; DRT ulang gagal DRT-0218 tanpa guide baru).
# FLOOR=2 (pita 600 um, kanal 120 um) gagal GRT-0118: port baca ROM luar dan port tulis RAM dalam berbagi kanal yang sama.
# Catatan: set_layer_adjustments.tcl memasang GRT_ADJUSTMENT (0,3) ke semua layer lalu menimpa per layer; nilai 0 dari PDK
# berarti tidak diubah, jadi met1 tahap 1-5 sudah 0,3 (tahap 6 dengan met1 = 0,3 identik dengan tahap 5, dihentikan).
# Tahap 7: met1 0,45 (antara 0,3 yang lolos dan 0,6 yang macet) agar kabel horizontal panjang pindah ke met3.
# Tahap 7: routing 0; met1 terpakai -5%, met3 +41%; antena 55 -> 42 (41 met1, semua baru di DRT, 25 <= 1,5x batas);
# slew/kap. sel standar 52/162 -> 44/138; setup/hold TT +4,37/+0,37 ns, FF bersih.
# Tahap 8 (met1 0,5 + margin antena 50%): gagal GRT-0118. Tahap 9 (met1 0,45 + margin 50%): antena 47 (tidak lebih baik
# dari 42): pelanggaran baru muncul di DRT, jadi perbaikan apa pun di tahap GRT sudah jenuh.
# Tahap 10: met1 0,45, margin 30%, ditambah satu putaran perbaikan antena SETELAH DRT lewat meta.substituting_steps:
# DetailedRouting -> RepairAntennas -> DetailedRouting -> RemoveRoutingObstructions (uji pada tahap 3: antena 74 -> 49).
# Tahap 10: antena 42 -> 35, tetapi LVS GAGAL (2 galat: output buffer wire3411 ke din0 makro terputus; GRT + DPL ulang di atas
# desain yang sudah dirutekan merusak sambungan). Ditolak: ANT_POSTDRT bawaan 0 (eksperimen saja).
# Tahap 11: celah antar-makro GAP 40 -> 60 um (kemacetan lokal di celah antar-makro; 21 dari 40 pelanggar terburuk di sana)
# agar met1 dapat dipotong lebih banyak (0,55; dengan celah 40 um 0,5 sudah macet).
# Tahap 11: antena 38 (semua met1, semua baru di DRT); slew sel standar 44 -> 4, kap. 138 -> 129, setup TT +4,98 ns, SS +1 ns
# lebih baik; die 8,99 mm2. Pemotongan met1 bertahap hanya ~10%/tahap.
# Tahap 12: global routing tidak memakai met1 sama sekali (RT_MIN_LAYER met2), detailed routing tetap boleh met1 untuk akses pin
# (DRT_MIN_LAYER met1); kabel jarak jauh hanya di met2+. (Dokumentasi OpenLane memberi pola yang sama untuk li1; untuk
# met1 ini percobaan.) Tahap 12: gagal GRT-0118 (area padat butuh met1 untuk akses pin). Bawaan kembali ke tahap 11:
# met1 0,55 dan RT_MIN met1; tahap 11 dijalankan dengan GAP=60 (env). Sisa antena tahap 11 ditangani ECO (eco_antenna.py).
# Antena sisa ECO dioda (tahap 11 + 1 putaran: 38 -> 19) jenuh karena dioda tersambung lewat met2, bukan segmen met1 yang
# melanggar; jumper lewat route guide (met1 panjang -> met3, lihat guide_jumper.py) menurunkan 19 -> 2.
# Kapasitansi (tahap 11, TT nominal 131: 38 pin dout makro, 93 sel standar 205-281 fF): kabel ter-route 1.000-1.330 um karena
# memutari makro; repair pasca-GRT menghitung dari perkiraan GRT, sedangkan laporan akhir dari RCX (termasuk kopling), jadi
# margin 30% kurang. Tahap 2 (kabel 400 um) hampir tidak mengubah kapasitansi; tahap 13 menaikkan margin (CAP_PCT) dan
# membatasi kapasitansi CTS (CTS_MAX_CAP, CTS_WIRE) dengan panjang kabel tetap 600 um.
RT_MIN = os.environ.get("RT_MIN", "met1")
CAP_PCT = int(os.environ.get("CAP_PCT", "30"))
FIX_CFG = {"GRT_LAYER_ADJUSTMENTS": [0.99, float(os.environ.get("M1_ADJ", "0.55")), 0, 0, 0, 0],
           **({"RT_MIN_LAYER": RT_MIN, "DRT_MIN_LAYER": "met1"} if RT_MIN != "met1" else {}),
           **({"CTS_MAX_CAP": float(os.environ["CTS_MAX_CAP"])} if os.environ.get("CTS_MAX_CAP") else {}),
           "DESIGN_REPAIR_MAX_WIRE_LENGTH": 600, "GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH": 600,
           "CTS_CLK_MAX_WIRE_LENGTH": int(os.environ.get("CTS_WIRE", "400")),
           "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": CAP_PCT, "RUN_POST_GRT_DESIGN_REPAIR": True,
           "GRT_DESIGN_REPAIR_MAX_SLEW_PCT": 30, "GRT_DESIGN_REPAIR_MAX_CAP_PCT": CAP_PCT,
           "RUN_POST_GRT_RESIZER_TIMING": True, "PL_RESIZER_HOLD_SLACK_MARGIN": 0.2, "GRT_RESIZER_HOLD_SLACK_MARGIN": 0.2,
           "RUN_HEURISTIC_DIODE_INSERTION": True, "HEURISTIC_ANTENNA_THRESHOLD": 100,
           "GRT_ANTENNA_ITERS": 10, "GRT_ANTENNA_MARGIN": int(os.environ.get("ANT_MARGIN", "30"))} if os.environ.get("FIX") == "1" else {}


def main() -> None:
    W.mkdir(parents=True, exist_ok=True)
    files = ["rtl/common/suaratb_pkg.sv", str(D / f"build/synth/P{P}/cnn_cfg_pkg.sv"), "rtl/common/rom_sync.sv", "target/asic/ram/ram_sdp_sky130.sv",
             "rtl/cnn/pe_array.sv", "rtl/cnn/requant.sv", "rtl/cnn/gap.sv", "rtl/cnn/cnn_ctrl.sv", "rtl/cnn/cnn_top.sv"]
    if WROM:
        sys.path.insert(0, str(ROOT / "target/asic/ram"))
        from patch_wrom import patched_cnn_top
        files[-1] = str(patched_cnn_top(W))
        files.insert(-1, "target/asic/ram/wrom_sky130.sv")
    r = subprocess.run([SV2V, "-DSYNTHESIS", "--top", "cnn_top"] + files, cwd=ROOT, capture_output=True, text=True, check=True)
    v = r.stdout.replace("rtl/mem/", "/work/mem/").replace("tb/vectors/cnn/", "/work/mem/")
    if os.environ.get("WROM_STUB") == "1":   # diagnosis saja: ROM bobot diganti stub kecil (keluaran tidak fungsional)
        i = v.index(") u_wrom("); j = v.rindex("rom_sync #(", 0, i)
        v = v[:j] + "wrom_stub #(" + v[j + len("rom_sync #("):] + """
module wrom_stub #(parameter WIDTH = 8, parameter DEPTH = 256, parameter INIT_FILE = "") (
  input clk, input en, input [$clog2(DEPTH)-1:0] addr, output reg [WIDTH-1:0] dout);
  always @(posedge clk) if (en) dout <= {32{addr}};
endmodule
"""
    (W / "cnn_top.v").write_text(v)
    (W / "mem").mkdir(exist_ok=True)
    for f in list((ROOT / "rtl/mem").glob("*.mem")) + list((D / f"build/synth/P{P}").glob("cnn_*.mem")):
        shutil.copy(f, W / "mem" / f.name)
    (W / "bb.v").write_text(f"""(* blackbox *)
module {MAC} (clk0, csb0, web0, wmask0, addr0, din0, dout0, clk1, csb1, addr1, dout1);
  input clk0; input csb0; input web0; input [3:0] wmask0; input [8:0] addr0; input [31:0] din0; output [31:0] dout0;
  input clk1; input csb1; input [8:0] addr1; output [31:0] dout1;
endmodule
""")
    names = [f"u_ramB.g_bank[{b}].u_m" for b in range(4)] + [f"u_ramA.g_bank[{b}].u_m" for b in range(2)]
    if WROM:
        lanes, banks = P * 8 // 32, -(-WROM_DEPTH[P] // 512)
        names += [f"u_wrom.g_bank[{b}].g_lane[{l}].u_m" for b in range(banks) for l in range(lanes)]
    assert len(names) <= COLS * ROWS
    inst = {}
    if FLOOR == 2 and WROM:
        wrom = [n for n in names if n.startswith("u_wrom")]; ram = [n for n in names if not n.startswith("u_wrom")]
        y_bo = GAP; y_bi = y_bo + MH + ROWGAP                     # baris bawah luar / dalam (orientasi N: port baca ke atas)
        y_ti = y_bi + MH + GAP + BAND + GAP; y_to = y_ti + MH + ROWGAP  # baris atas dalam / luar (FS: port baca ke bawah)
        rows = [(y_to, "FS", wrom[:COLS]), (y_ti, "FS", ram[:COLS]), (y_bi, "N", ram[COLS:]), (y_bo, "N", wrom[COLS:])]
        for y, o, ns in rows:
            for col, n in enumerate(ns):
                inst[n] = {"location": [round(GAP + col * (MW + GAP), 2), round(y, 2)], "orientation": o}
        assert len(inst) == len(names) and y_to + MH + GAP <= DIE_H + 1
    top_rows = ROWS - ROWS // 2 if WROM else ROWS - 1   # baris atas di tepi atas; sisanya di tepi bawah; logika di pita tengah
    for i, n in enumerate(names if not inst else []):
        row, col = divmod(i, COLS)
        x = GAP + col * (MW + GAP)
        if os.environ.get("SPLIT", "1") == "1" and row >= top_rows:
            y = GAP + (ROWS - 1 - row) * (MH + GAP)
        else:
            y = DIE_H - GAP - (row + 1) * MH - row * GAP
        inst[n] = {"location": [round(x, 2), round(y, 2)], "orientation": "N"}
    kt = os.environ.get("KLAYOUT_THREADS", "6")
    cfg = {"DESIGN_NAME": "cnn_top", "VERILOG_FILES": "dir::cnn_top.v", "CLOCK_PORT": "clk", "CLOCK_PERIOD": float(os.environ.get("CLK_NS", "25")),
           "FP_SIZING": "absolute", "DIE_AREA": [0, 0, DIE_W, DIE_H], "PL_TARGET_DENSITY_PCT": int(os.environ.get("PL_DENS", "25")), "GPL_CELL_PADDING": int(os.environ.get("PAD", "2")), "DPL_CELL_PADDING": int(os.environ.get("PAD", "2")), "RUN_LINTER": False,
           "GRT_ADJUSTMENT": float(os.environ.get("GRT_ADJ", "0.3")), "STA_THREADS": int(os.environ.get("STA_THREADS", "2")), "ERROR_ON_TR_DRC": os.environ.get("TRDRC_ERR", "1") == "1",
           # Makro OpenRAM: mode "macro" (kotak hitam + penunjuk GDS) menghasilkan GDS Magic rusak ("Structure name not found");
           # mode PDK membaca GDS makro penuh. Saat membaca, Magic tetap melapor layer penanda OpenRAM yang tidak dikenalnya
           # (22/21, 22/22, 33/42, 33/43, 235/0), jadi galat Magic tidak fatal; kebenaran GDS diperiksa XOR terhadap KLayout.
           "MAGIC_MACRO_STD_CELL_SOURCE": "PDK", "MAGIC_CAPTURE_ERRORS": False,
           # Magic (mode PDK) menulis ulang isi makro saat StreamOut (kontak/via dibuat ulang, implan dibuat ulang, layer
           # penanda OpenRAM dibuang). GDS KLayout menyalin GDS makro OpenRAM apa adanya, jadi dijadikan GDS utama
           # (final/gds, dipakai Magic WriteLEF/DRC); GDS Magic tetap ada di final/mag_gds untuk pembanding XOR.
           "PRIMARY_GDSII_STREAMOUT_TOOL": "klayout",
           "PDN_MACRO_CONNECTIONS": ["u_ram.* VPWR VGND vccd1 vssd1"] + (["u_wrom.* VPWR VGND vccd1 vssd1"] if WROM else []),
           "MACROS": {MAC: {"gds": [f"{MROOT}/gds/{MAC}.gds"], "lef": [f"{MROOT}/lef/{MAC}.lef"],
                            "lib": {"*": f"{MROOT}/lib/{MAC}_TT_1p8V_25C.lib"}, "vh": ["dir::bb.v"], "spice": [f"{MROOT}/spice/{MAC}.spice"], "instances": inst}}}
    if kt:
        cfg.update({"KLAYOUT_XOR_THREADS": int(kt), "KLAYOUT_DRC_THREADS": int(kt)})
    cfg.update(FIX_CFG)
    if FIX_CFG and os.environ.get("ANT_POSTDRT", "0") == "1":   # perbaikan antena setelah DRT (lihat komentar FIX_CFG)
        cfg["meta"] = {"version": 1, "flow": "Classic", "substituting_steps": {
            "+OpenROAD.DetailedRouting": "OpenROAD.RepairAntennas", "-Odb.RemoveRoutingObstructions": "OpenROAD.DetailedRouting"}}
    if WROM and not IP:   # SIGNOFF=full: pelanggaran DRC di dalam makro dicatat, tidak menghentikan alur sebelum LVS
        cfg.update({"ERROR_ON_MAGIC_DRC": False, "ERROR_ON_KLAYOUT_DRC": False})
    (W / "config.json").write_text(json.dumps(cfg, indent=1))
    cmd = ["docker", "run", "--rm"] + (["--memory", os.environ["DOCKER_MEM"], "--memory-swap", os.environ["DOCKER_MEM"]] if os.environ.get("DOCKER_MEM") else []) \
        + (["--cpus", os.environ["DOCKER_CPUS"]] if os.environ.get("DOCKER_CPUS") else []) \
        + ["-v", f"{W}:/work", "-v", f"{pathlib.Path.home()}/.volare:/pdk", "-e", "PDK_ROOT=/pdk", "-w", "/work", IMG,
           "openlane", "--pdk-root", "/pdk", "--pdk", "sky130A", "--run-tag", TAG, "config.json"] + SKIP
    subprocess.run(cmd, stdout=(W / f"{TAG}.log").open("w"), stderr=subprocess.STDOUT)
    if WROM and (W / "runs" / TAG / "final").exists() and not (W / "run").exists():
        subprocess.run(["docker", "run", "--rm", "-v", f"{W}:/work", IMG, "mv", f"/work/runs/{TAG}", "/work/run"], check=True)
        subprocess.run(["docker", "run", "--rm", "-v", f"{W}:/work", IMG, "rmdir", "/work/runs"])
    f = (W / "run" if WROM else W / "runs" / TAG) / "final/metrics.json"
    if not f.exists():
        print(f"cnn_top_macro P={P}: GAGAL (lihat {W / (TAG + '.log')})"); return
    m = json.load(open(f)); g = m.get
    print(f"cnn_top_macro P={P}: pin={g('design__io')} sel={g('design__instance__count__stdcell')} area_sel={g('design__instance__area__stdcell')}um2 "
          f"makro={g('design__instance__count__macros')} die={g('design__die__area')}um2 DRC={g('magic__drc_error__count')}/{g('klayout__drc_error__count')} LVS={g('design__lvs_error__count')} "
          f"setup_ws={g('timing__setup__ws')} hold_ws={g('timing__hold__ws')} vio={g('timing__setup_vio__count')}/{g('timing__hold_vio__count')} antena={g('antenna__violating__nets')} daya={g('power__total')} "
          f"slew/kap/fanout={g('design__max_slew_violation__count')}/{g('design__max_cap_violation__count')}/{g('design__max_fanout_violation__count')}")
    if IP:
        sys.path.insert(0, str(ROOT / "target/asic/scripts"))
        from signoff_nomacro import run as signoff
        signoff(f.parents[1], int(kt))


if __name__ == "__main__":
    main()
