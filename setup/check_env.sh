#!/usr/bin/env bash
# Cek alat yang dibutuhkan (dari ROOT repo, setelah `source setup/env.sh`). Hanya membaca, tidak memasang apa pun.
ok() { printf "  %-28s %s\n" "$1" "$2"; }
chk() { if command -v "$1" >/dev/null 2>&1; then ok "$1" "$($2 2>&1 | head -1)"; else ok "$1" "TIDAK ADA"; fi; }
echo "Simulasi dan sintesis:"
chk python3 "python3 --version"; chk iverilog "iverilog -V"; chk verilator "verilator --version"; chk yosys "yosys -V"
ok sv2v "$( [ -x "${SV2V:-}" ] && "$SV2V" --version || echo 'TIDAK ADA (isi SV2V)')"
ok ".venv cocotb" "$( [ -x .venv/bin/python ] && .venv/bin/python -c 'import cocotb;print(cocotb.__version__)' 2>&1 || echo 'TIDAK ADA')"
echo "Layout ASIC:"
chk docker "docker --version"
ok "citra openlane2 2.3.10" "$(docker image inspect ghcr.io/efabless/openlane2:2.3.10 >/dev/null 2>&1 && echo ada || echo 'TIDAK ADA')"
ok "PDK sky130 (volare)" "$(ls "$HOME/.volare/volare/sky130/versions" 2>/dev/null | tr '\n' ' ' || true)"
ok "RAM terlihat" "$(free -g | awk '/Mem:/{print $2" GB"}')"
echo "Data:"
ok SUARATB_DATA "${SUARATB_DATA:-TIDAK DISET} $( [ -d "${SUARATB_DATA:-/nonexistent}" ] && echo '(ada)' || echo '(belum ada)')"
ok "build/synth/P16" "$( [ -f "${SUARATB_DATA:-x}/build/synth/P16/cnn_cfg_pkg.sv" ] && echo ada || echo 'belum (target/artix7/prep_synth.py)')"
echo "Opsional:"
chk klayout "klayout -v"; chk graphify "graphify --version"
