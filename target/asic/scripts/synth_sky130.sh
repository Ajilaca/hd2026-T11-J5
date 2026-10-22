#!/usr/bin/env bash
# Studi kelayakan ASIC tingkat 1: sintesis Yosys ke sel standar sky130_fd_sc_hd (tt_025C_1v80), area dari liberty. Dari ROOT repo:
#   target/asic/scripts/synth_sky130.sh 16     (butuh $SUARATB_DATA/build/synth/P16 dari target/prep_synth.py)
# Dua jalan: "full" = semua memori jadi flip-flop; "logic" = ram_sdp dijadikan blackbox (area logika + ROM tanpa RAM).
# Selisih full-logic = biaya RAM sebagai flip-flop. Jumlah bit RAM dibaca dari sel $mem_v2. RTL tidak diubah. Hanya studi area; tanpa timing/P&R.
set -eu
P=${1:?P}
D=${SUARATB_DATA:-/data/suaratb}
S=${SV2V:-$(command -v sv2v || echo /data/tools/sv2v/sv2v-Linux/sv2v)}
LIB=$(ls $HOME/.volare/volare/sky130/versions/*/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib | head -1)
B=$D/build/synth/P$P
O=$D/build/asic/P$P
mkdir -p "$O"
files="$(grep -v '^//' rtl/files.f | grep -v sva_stream | sed "s#rtl/cnn/cnn_cfg_pkg.sv#$B/cnn_cfg_pkg.sv#" | tr '\n' ' ') target/kv260/axi/rtl/axil_ctrl.v target/kv260/axi/rtl/suaratb_axil_top.sv"
$S -DSYNTHESIS $files | sed "s#tb/vectors/cnn/#$B/#g" > "$O/top.v"
# jumlah bit memori (sebelum dipetakan ke flip-flop)
yosys -q -l "$O/mem.log" -p "read_verilog -sv $O/top.v; hierarchy -top suaratb_axil_top; synth -top suaratb_axil_top -run begin:fine; memory_collect; write_json $O/mem.json" > /dev/null
for MODE in ${MODES:-logic full}; do
  BB=""; [ $MODE = logic ] && BB="blackbox *ram_sdp*"
  yosys -q -l "$O/$MODE.log" -p "
read_verilog -sv $O/top.v
hierarchy -top suaratb_axil_top
$BB
synth -top suaratb_axil_top
dfflibmap -liberty $LIB
abc -liberty $LIB
opt_clean
tee -o $O/stat_$MODE.txt stat -liberty $LIB -top suaratb_axil_top
" > /dev/null
  echo "P=$P $MODE: $(grep -E 'Chip area for top module' $O/stat_$MODE.txt | tail -1)"
done
