# Buat run_eco6.sh dari run_eco5.sh: sumber p16_10m_eco5, tujuan p16_10m_eco6, target antena + kapasitansi,
# skrip ECO eco6.py / eco6_views.tcl. Berhenti bila ada pola yang tidak ditemukan.
import sys, pathlib
src, dst = map(pathlib.Path, sys.argv[1:3])
s = src.read_text()
rep = [
    ("# ECO putaran 5 (khusus antena, tanpa GRT ulang) di atas hasil putaran 4 (p16_10m_eco4/run): satu dioda di samping tiap\n"
     "# pin gate yang melanggar antena pasca-DRT (laporan langkah 44). Route guide net lain, termasuk 87 jumper putaran 4,\n"
     "# tidak diubah. Lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu signoff_nomacro. Hasil putaran 4 hanya dibaca.",
     "# ECO putaran 6 (tanpa GRT ulang) di atas hasil putaran 5 (p16_10m_eco5/run): dioda untuk pin gate pelanggar antena\n"
     "# pasca-DRT, perbesaran driver sel standar dan buffer pin makro untuk pelanggar kapasitansi (checks.rpt semua corner).\n"
     "# Route guide net lain, termasuk jumper, tidak diubah. Lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu signoff_nomacro.\n"
     "# Hasil putaran 5 hanya dibaca."),
    ("/b/p16_10m_eco5", "/b/p16_10m_eco6"),
    ("SRCD=$B/p16_10m_eco4;", "SRCD=$B/p16_10m_eco5;"),
    ("W=$B/p16_10m_eco5;", "W=$B/p16_10m_eco6;"),
    ("dari p16_10m_eco4/run", "dari p16_10m_eco5/run"),
    ("cd /b/p16_10m_eco4 &&", "cd /b/p16_10m_eco5 &&"),
    ('log "target dioda: $(wc -l < $X/dioda_pins.txt) pin"\ncat $X/dioda_pins.txt',
     "cat $BASE/53-openroad-stapostpnr/*/checks.rpt | awk '/max capacitance/{p=1;next} /max fanout|max slew|^=+$/{p=0} "
     "p && /VIOLATED/{print $1}' | sort -u > $X/cap_pins.txt\n"
     'log "target: dioda $(wc -l < $X/dioda_pins.txt) pin, kapasitansi $(wc -l < $X/cap_pins.txt) pin"\n'
     "cat $X/dioda_pins.txt $X/cap_pins.txt"),
    ("# ---- dioda (lokasi legal, guide net lain tetap)", "# ---- sel ECO (lokasi legal, guide net lain tetap)"),
    ("cp $S/dioda_eco.py $S/dioda_views.tcl $X/\n"
     "docker run --rm -v $W:/w $IMG openroad -python -exit /w/eco/dioda_eco.py \\\n"
     "  /w/runs/$TAG/40-openroad-resizertimingpostgrt/cnn_top.odb /w/eco/dioda_in.odb /w/eco/dioda_pins.txt 2>&1 \\\n"
     '  | grep -E "DIODA|Error|Trace" | tail -20\n'
     '[ -s $X/dioda_in.odb ] || { echo "dioda_in.odb tidak ada, berhenti"; exit 1; }',
     "cp $S/eco6.py $S/eco6_views.tcl $X/\n"
     "docker run --rm -v $W:/w $IMG openroad -python -exit /w/eco/eco6.py \\\n"
     "  /w/runs/$TAG/40-openroad-resizertimingpostgrt/cnn_top.odb /w/eco/eco6_in.odb /w/eco/dioda_pins.txt /w/eco/cap_pins.txt "
     "/w/eco/resize.txt 2>&1 \\\n"
     '  | grep -E "ECO6|Error|Trace|Signal" | tail -20\n'
     '[ -s $X/eco6_in.odb ] || { echo "eco6_in.odb tidak ada, berhenti"; exit 1; }'),
    ("./dioda_views.tcl#", "./eco6_views.tcl#"),
    ('grep -q dioda_views.tcl $X/run_eco.sh || { echo "run_eco.sh tidak memanggil dioda_views.tcl, berhenti"; exit 1; }',
     'grep -q eco6_views.tcl $X/run_eco.sh || { echo "run_eco.sh tidak memanggil eco6_views.tcl, berhenti"; exit 1; }'),
    ('log "ECO: cek penempatan + tulis view"', 'log "ECO: perbesar sel + cek penempatan + tulis view"'),
    ("-e ECO_ODB=/work/eco/dioda_in.odb", "-e ECO_ODB=/work/eco/eco6_in.odb -e RESIZE_LST=/work/eco/resize.txt"),
    ('grep -E "DIODA|DPL-|ERROR" $X/eco.log | tail -12', 'grep -E "ECO6|DPL-|ERROR" $X/eco.log | tail -12'),
]
for a, b in rep:
    if a not in s:
        sys.exit("pola tidak ditemukan: " + a[:70])
    s = s.replace(a, b)
dst.write_text(s)
print("tulis", dst)
