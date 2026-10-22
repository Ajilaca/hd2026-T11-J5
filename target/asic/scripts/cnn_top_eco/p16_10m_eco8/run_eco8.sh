#!/bin/bash
# ECO putaran 8 (tanpa GRT ulang) di atas hasil putaran 7 (p16_10m_eco7/run): dioda + jumper met1 untuk net pelanggar
# antena pasca-DRT, buffer pemecah beban (driver sel standar) dan buffer pin makro untuk pelanggar kapasitansi
# (checks.rpt semua corner). Route guide net lain tidak diubah. Lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu
# signoff_nomacro. Hasil putaran 7 hanya dibaca.
set -e
B=$HOME/suaratb-data/build/asic/cnn_top; IMG=ghcr.io/efabless/openlane2:2.3.10
# TAG harus sama dengan run sumber: state_in.json langkah 40 berisi jalur absolut /work/runs/<tag>/...
SRCD=$B/p16_10m_eco7; BASE=$SRCD/run; W=$B/p16_10m_eco8; TAG=p16_10m; S=$W/eco_scripts; X=$W/eco
log() { echo "$(date '+%F %T') $*"; }

[ -d $W/runs ] && { echo "$W/runs sudah ada, berhenti"; exit 1; }
[ -f $BASE/final/metrics.json ] || { echo "$BASE/final tidak ada, berhenti"; exit 1; }
log "salin masukan dan langkah <= 40 dari p16_10m_eco7/run"
docker run --rm -v $B:/b --entrypoint sh $IMG -c "
  mkdir -p /b/p16_10m_eco8/runs/$TAG /b/p16_10m_eco8/eco && cd /b/p16_10m_eco7 && cp -a config.json cnn_top.v bb.v cnn_top_wrom.sv mem /b/p16_10m_eco8/ &&
  cd run && for d in \$(ls | grep -E '^[0-9]+-'); do n=\${d%%-*}; [ \$n -le 40 ] && cp -a \$d /b/p16_10m_eco8/runs/$TAG/; done;
  cp -a resolved.json /b/p16_10m_eco8/runs/$TAG/ 2>/dev/null; chown -R 1000:1000 /b/p16_10m_eco8; true"

# ---- target: pin gate pelanggar antena pasca-DRT ------------------------------------------------------------------
python3 - $BASE/44-openroad-checkantennas-1/reports/antenna.rpt > $X/dioda_pins.txt <<'EOF'
import sys, re
net = pin = lay = None; out = []
for l in open(sys.argv[1]):
    m = re.match(r"\s*(Net|Pin|Layer):\s+(\S+)", l)
    if m:
        if m.group(1) == "Net": net = m.group(2)
        elif m.group(1) == "Pin": pin = m.group(2)
        else: lay = m.group(2)
    elif "VIOLATED" in l: out.append((net, pin, lay))
for t in dict.fromkeys(out): print(*t)
EOF
cat $BASE/53-openroad-stapostpnr/*/checks.rpt | awk '/max capacitance/{p=1;next} /max fanout|max slew|^=+$/{p=0} p && /VIOLATED/{print $1}' | sort -u > $X/cap_pins.txt
log "target: dioda $(wc -l < $X/dioda_pins.txt) pin, kapasitansi $(wc -l < $X/cap_pins.txt) pin"
cat $X/dioda_pins.txt $X/cap_pins.txt

# ---- sel ECO (lokasi legal, guide net lain tetap) --------------------------------------------------------------------
cp $S/eco8.py $S/eco8_views.tcl $S/guide_jumper.py $X/
docker run --rm -e ECO_TAG=8 -v $W:/w $IMG openroad -python -exit /w/eco/eco8.py \
  /w/runs/$TAG/40-openroad-resizertimingpostgrt/cnn_top.odb /w/eco/eco8_pre.odb /w/eco/dioda_pins.txt /w/eco/cap_pins.txt /w/eco/resize.txt /w/eco/jumper.txt 2>&1 \
  | grep -E "ECO6|Error|Trace|Signal" | tail -20
[ -s $X/eco8_pre.odb ] || { echo "eco8_pre.odb tidak ada, berhenti"; exit 1; }
log "jumper: $(wc -l < $X/jumper.txt) net met1"
docker run --rm -v $W:/w $IMG openroad -python -exit /w/eco/guide_jumper.py \
  /w/eco/eco8_pre.odb /w/eco/eco8_in.odb /w/eco/eco8_in.def /w/eco/jumper.txt 2>&1 | grep -E "JUMPER|tidak ditemukan|Error|Trace" | tail -8
[ -s $X/eco8_in.odb ] || { echo "eco8_in.odb tidak ada, berhenti"; exit 1; }

# ---- cek penempatan + global connect + tulis view (lingkungan langkah 40) -------------------------------------------
docker run --rm -v $W:/work -v $HOME/.volare:/pdk -e PDK_ROOT=/pdk -w /work/eco $IMG \
  python3 -m openlane.steps eject --id OpenROAD.ResizerTimingPostGRT -c /work/runs/$TAG/40-openroad-resizertimingpostgrt/config.json \
  -i /work/runs/$TAG/40-openroad-resizertimingpostgrt/state_in.json -o /work/eco/run.sh > $X/eject.log 2>&1 || { echo "EJECT GAGAL"; tail -5 $X/eject.log; exit 1; }
sed -E 's#^openroad (.*) \S+rsz_timing_postgrt.tcl$#openroad \1 ./eco8_views.tcl#' $X/run.sh > $X/run_eco.sh
grep -q eco8_views.tcl $X/run_eco.sh || { echo "run_eco.sh tidak memanggil eco8_views.tcl, berhenti"; exit 1; }
log "ECO: cek penempatan + tulis view"
docker run --rm -v $W:/work -v $HOME/.volare:/pdk -e PDK_ROOT=/pdk -w /work/eco -e ECO_ODB=/work/eco/eco8_in.odb -e RESIZE_LST=/work/eco/resize.txt \
  $IMG sh ./run_eco.sh > $X/eco.log 2>&1 || { echo "ECO GAGAL"; tail -30 $X/eco.log; exit 1; }
grep -E "ECO6|DPL-|ERROR" $X/eco.log | tail -12

# ---- lanjutkan alur -------------------------------------------------------------------------------------------------
docker run --rm -v $W:/w --entrypoint sh $IMG -c "cd /w/eco && for f in cnn_top.odb cnn_top.def cnn_top.nl.v cnn_top.pnl.v cnn_top.sdc; do [ -f \$f ] && cp -f \$f /w/runs/$TAG/40-openroad-resizertimingpostgrt/\$f && echo ganti \$f; done; true"
log "lanjutkan alur dari OpenROAD.STAMidPNR-3"
set +e
docker run --rm -v $W:/work -v $HOME/.volare:/pdk -e PDK_ROOT=/pdk -w /work $IMG \
  openlane --pdk-root /pdk --pdk sky130A --run-tag $TAG --from OpenROAD.STAMidPNR-3 \
  --skip KLayout.XOR --skip Magic.DRC --skip KLayout.DRC --skip Checker.MagicDRC --skip Checker.KLayoutDRC config.json > $W/eco.log 2>&1
log "openlane exit=$?"
if [ -d $W/runs/$TAG/final ] && [ ! -d $W/run ]; then
  docker run --rm -v $W:/work $IMG mv /work/runs/$TAG /work/run && docker run --rm -v $W:/work $IMG rmdir /work/runs
fi
R=$W/run; [ -d $R ] || R=$W/runs/$TAG
python3 $B/p16_10m/sta_ringkas.py $R
for c in max_ss_100C_1v60 max_tt_025C_1v80 max_ff_n40C_1v95; do
  awk '/max capacitance/{p=1;next} /max fanout|max slew|^=+$/{p=0} p && /VIOLATED/' $R/53-openroad-stapostpnr/$c/checks.rpt
done | sort -u
if [ -f $R/final/metrics.json ]; then
  python3 -c "import json;m=json.load(open('$R/final/metrics.json'));g=m.get;print('LVS',g('design__lvs_error__count'),'antena',g('antenna__violating__nets'),'kap',g('design__max_cap_violation__count'),'routing',g('route__drc_errors'))"
  cd ~/suaratb && . .venv/bin/activate && python target/asic/signoff_nomacro.py $R > $W/signoff_nomacro.log 2>&1
  log "signoff_nomacro exit=$?"; tail -6 $W/signoff_nomacro.log
else
  echo "final tidak ada"; grep -E "\] ERROR" -A4 $W/eco.log | grep -v "Error while reading\|Unknown layer\|byte\|boundary\|sky130_fd_bd" | tail -12
fi
log "selesai"
