#!/bin/bash
# Run dasar cnn_top P16 pada 10,24 MHz (CLOCK_PERIOD 97,656 ns). Masukan = p16 (konfigurasi fix13: FIX=1 CAP_PCT=50
# CTS_MAX_CAP=0.15 CTS_WIRE=300), hanya CLOCK_PERIOD diganti. Folder baru: tidak menimpa run lama.
# Langkah DRC/XOR yang memeriksa isi makro dilewati (sama dengan SIGNOFF=ip); signoff_nomacro.py dijalankan sesudahnya.
set -u
B=$HOME/suaratb-data/build/asic/cnn_top
W=$B/p16_10m
TAG=p16_10m
IMG=ghcr.io/efabless/openlane2:2.3.10
cd "$W"
if [ ! -f config.json ]; then
  cp -a "$B/p16/cnn_top.v" "$B/p16/bb.v" "$B/p16/cnn_top_wrom.sv" "$W/"
  cp -a "$B/p16/mem" "$W/"
  python3 - "$B/p16/config.json" "$W/config.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1]))
c["CLOCK_PERIOD"] = 97.656
json.dump(c, open(sys.argv[2], "w"), indent=1)
EOF
fi
echo "$(date '+%F %T') mulai OpenLane CLOCK_PERIOD=$(python3 -c "import json;print(json.load(open('config.json'))['CLOCK_PERIOD'])")"
docker run --rm -v "$W:/work" -v "$HOME/.volare:/pdk" -e PDK_ROOT=/pdk -w /work $IMG \
  openlane --pdk-root /pdk --pdk sky130A --run-tag $TAG \
  --skip KLayout.XOR --skip Magic.DRC --skip KLayout.DRC --skip Checker.MagicDRC --skip Checker.KLayoutDRC \
  config.json > "$W/$TAG.log" 2>&1
echo "$(date '+%F %T') OpenLane exit=$?"
if [ -d "$W/runs/$TAG/final" ] && [ ! -d "$W/run" ]; then
  docker run --rm -v "$W:/work" $IMG mv /work/runs/$TAG /work/run && docker run --rm -v "$W:/work" $IMG rmdir /work/runs
fi
F=$W/run/final/metrics.json
if [ -f "$F" ]; then
  python3 - "$F" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1])); g = m.get
print("LVS", g("design__lvs_error__count"), "routingDRC", g("route__drc_errors"), "antena", g("antenna__violating__nets"),
      "kap", g("design__max_cap_violation__count"), "slew", g("design__max_slew_violation__count"), "fanout", g("design__max_fanout_violation__count"))
for c in ("nom_tt_025C_1v80", "nom_ss_100C_1v60", "max_ss_100C_1v60", "nom_ff_n40C_1v95"):
    print(c, "setup", g("timing__setup__ws__corner:" + c), "hold", g("timing__hold__ws__corner:" + c))
EOF
  cd ~/suaratb && . .venv/bin/activate && KLAYOUT_THREADS=6 python target/asic/signoff_nomacro.py "$W/run" > "$W/signoff_nomacro.log" 2>&1
  echo "$(date '+%F %T') signoff_nomacro exit=$?"; tail -5 "$W/signoff_nomacro.log"
else
  echo "final tidak ada"; grep -E "\] ERROR" -A3 "$W/$TAG.log" | grep -v "Error while reading\|Unknown layer\|byte\|boundary\|sky130_fd_bd" | tail -10
fi
echo "$(date '+%F %T') selesai"
