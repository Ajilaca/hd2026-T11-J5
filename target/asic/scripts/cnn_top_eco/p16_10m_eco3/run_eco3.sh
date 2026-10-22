#!/bin/bash
# ECO putaran 3 di atas hasil putaran 2 (p16_10m_eco2/run): kapasitansi kecil (pelanggar checks.rpt corner max + pin >= LIMIT),
# hold (margin 0,25 ns), repair_antennas, lalu jumper met1 dengan target dari laporan antena putaran sumber (langkah terakhir),
# lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu signoff_nomacro. Hasil putaran sumber hanya dibaca.
set -e
B=$HOME/suaratb-data/build/asic/cnn_top; IMG=ghcr.io/efabless/openlane2:2.3.10
# TAG harus sama dengan run sumber: state_in.json langkah 40 berisi jalur absolut /work/runs/<tag>/...
SRCD=$B/p16_10m_eco2; BASE=$SRCD/run; W=$B/p16_10m_eco3; TAG=p16_10m; S=$W/eco_scripts; X=$W/eco
LIMIT=${LIMIT:-0.20}; HOLD_MARGIN=${HOLD_MARGIN:-0.25}; PREFIX=${CAP_PREFIX:-ECO_CAP30}
log() { echo "$(date '+%F %T') $*"; }

[ -d $W/runs ] && { echo "$W/runs sudah ada, berhenti"; exit 1; }
[ -f $BASE/final/metrics.json ] || { echo "$BASE/final tidak ada, berhenti"; exit 1; }
log "salin masukan dan langkah <= 40 dari p16_10m_eco2/run"
docker run --rm -v $B:/b --entrypoint sh $IMG -c "
  mkdir -p /b/p16_10m_eco3/runs/$TAG /b/p16_10m_eco3/eco && cd /b/p16_10m_eco2 && cp -a config.json cnn_top.v bb.v cnn_top_wrom.sv mem /b/p16_10m_eco3/ &&
  cd run && for d in \$(ls | grep -E '^[0-9]+-'); do n=\${d%%-*}; [ \$n -le 40 ] && cp -a \$d /b/p16_10m_eco3/runs/$TAG/; done;
  cp -a resolved.json /b/p16_10m_eco3/runs/$TAG/ 2>/dev/null; chown -R 1000:1000 /b/p16_10m_eco3; true"

# ---- target kapasitansi ------------------------------------------------------------------------------------------
docker run --rm -e RUN=/r -e LIMIT=$LIMIT -v $BASE:/r:ro -v $HOME/.volare:/pdk -v $S:/s $IMG openroad -exit /s/near_cap10.tcl 2>&1 \
  | awk '/VIOLATED/{print $1,$2,$3,$4}' > $X/near.txt
for c in max_ss_100C_1v60 max_tt_025C_1v80 max_ff_n40C_1v95 nom_ss_100C_1v60 nom_tt_025C_1v80 nom_ff_n40C_1v95; do
  awk '/max capacitance/{p=1;next} /max fanout|max slew|^=+$/{p=0} p && /VIOLATED/{print $1,$2,$3,$4}' $BASE/53-openroad-stapostpnr/$c/checks.rpt
done > $X/checks_viol.txt
sort -u -k1,1 $X/near.txt $X/checks_viol.txt > $X/cap_pins.txt
log "target kapasitansi: near(>=$LIMIT pF)=$(wc -l < $X/near.txt) checks=$(sort -u -k1,1 $X/checks_viol.txt | wc -l) gabungan=$(wc -l < $X/cap_pins.txt)"
cat $X/cap_pins.txt

# ---- sel ECO kapasitansi (lokasi kasar) ---------------------------------------------------------------------------
cp $S/cap_eco.py $S/eco_capfix10.tcl $X/
docker run --rm -e CAP_PREFIX=$PREFIX -v $W:/w -v $BASE:/s:ro $IMG openroad -python -exit /w/eco/cap_eco.py \
  /w/runs/$TAG/40-openroad-resizertimingpostgrt/cnn_top.odb /w/eco/cap_in.odb /w/eco/cap_pins.txt /s/42-openroad-detailedrouting/cnn_top.odb 2>&1 \
  | grep -E "CAPECO|Error|Trace" | tail -8

# ---- legalisasi + GRT + hold + antena (lingkungan langkah 40) -----------------------------------------------------
docker run --rm -v $W:/work -v $HOME/.volare:/pdk -e PDK_ROOT=/pdk -w /work/eco $IMG \
  python3 -m openlane.steps eject --id OpenROAD.ResizerTimingPostGRT -c /work/runs/$TAG/40-openroad-resizertimingpostgrt/config.json \
  -i /work/runs/$TAG/40-openroad-resizertimingpostgrt/state_in.json -o /work/eco/run.sh > $X/eject.log 2>&1 || { echo "EJECT GAGAL"; tail -5 $X/eject.log; exit 1; }
sed -E 's#^openroad (.*) \S+rsz_timing_postgrt.tcl$#export PL_OPTIMIZE_MIRRORING=0\nopenroad \1 ./eco_capfix10.tcl#' $X/run.sh > $X/run_eco.sh
docker run --rm -v $X:/x --entrypoint python3 $IMG -c "p='/x/_env.tcl'; s=open(p).read().replace('set ::env(PL_OPTIMIZE_MIRRORING) 1','set ::env(PL_OPTIMIZE_MIRRORING) 0'); open(p,'w').write(s)"
grep -q eco_capfix10.tcl $X/run_eco.sh || { echo "run_eco.sh tidak memanggil eco_capfix10.tcl, berhenti"; exit 1; }
log "ECO: legalisasi + GRT + hold (margin $HOLD_MARGIN) + repair_antennas"
docker run --rm -v $W:/work -v $HOME/.volare:/pdk -e PDK_ROOT=/pdk -w /work/eco -e ECO_ODB=/work/eco/cap_in.odb -e ECO_HOLD_MARGIN=$HOLD_MARGIN \
  $IMG sh ./run_eco.sh > $X/eco.log 2>&1 || { echo "ECO GAGAL"; tail -30 $X/eco.log; exit 1; }
grep -E "ECO_CAP|^worst slack|RSZ-00|ANT-0002|GRT-0118|ERROR" $X/eco.log | tail -24

# ---- jumper met1 (langkah terakhir sebelum detailed routing) -------------------------------------------------------
python3 - $BASE/44-openroad-checkantennas-1/reports/antenna_summary.rpt > $X/targets.txt <<'EOF'
import sys
for line in open(sys.argv[1], encoding="utf-8"):
    p = [x.strip() for x in line.split("\u2502")]
    if len(p) >= 7 and p[6] == "met1":
        print(p[4], p[5], "x", p[2])
EOF
log "jumper: $(wc -l < $X/targets.txt) net met1"
cp $S/guide_jumper.py $X/
docker run --rm -v $W:/w $IMG openroad -python -exit /w/eco/guide_jumper.py \
  /w/eco/cnn_top.odb /w/eco/cnn_top_j.odb /w/eco/cnn_top_j.def /w/eco/targets.txt 2>&1 | grep -E "JUMPER: [0-9]+ net|tidak ditemukan|Error|Trace" | tail -12
docker run --rm -v $X:/x --entrypoint sh $IMG -c "cd /x && test -s cnn_top_j.odb && mv cnn_top.odb cnn_top_prejumper.odb && mv cnn_top.def cnn_top_prejumper.def && mv cnn_top_j.odb cnn_top.odb && mv cnn_top_j.def cnn_top.def"

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
