#!/usr/bin/env bash
# Sintesis KV260. Dari ROOT repo: target/kv260/run.sh [ooc|full] [P ...]    (default: ooc 16 32)
# Env: VIVADO (jalur vivado), CLK_NS (6.782 = 147,456 MHz), SUARATB_DATA, MODEL (qmodel.npz untuk ROM bobot)
set -u
MODE=${1:-ooc}; shift || true
D=${SUARATB_DATA:-/data/suaratb}
V=${VIVADO:-/data/tools/Xilinx/2026.1/Vivado/bin/vivado}
MODEL=${MODEL:-$D/runs/model_v2/qmodel.npz}
mkdir -p "$D/build/kv260"
for P in ${@:-16 32}; do
  [ -f "$D/build/synth/P$P/cnn_cfg_pkg.sv" ] || .venv/bin/python target/artix7/prep_synth.py --p "$P" --out "$D/build/synth/P$P" --model "$MODEL"
  P=$P PDIR=$D/build/synth/P$P OUT=$D/build/kv260/${MODE}_P$P MODE=$MODE CLK_NS=${CLK_NS:-6.782} \
    $V -mode batch -source target/kv260/synth.tcl -log "$D/build/kv260/${MODE}_P$P.log" -journal "$D/build/kv260/${MODE}_P$P.jou" > /dev/null 2>&1
  echo "MODE=$MODE P=$P rc=$? $(date +%H:%M)"
done
echo SELESAI
