# Buat run_eco8.sh dari run_eco7.sh: sumber p16_10m_eco7, tujuan p16_10m_eco8, skrip eco8.py (pemecah beban, bukan
# perbesaran sel) + guide_jumper.py untuk net antena met1, eco8_views.tcl. Berhenti bila ada pola yang tidak ditemukan.
import sys, pathlib
src, dst = map(pathlib.Path, sys.argv[1:3])
s = src.read_text()
rep = [
    ("# ECO putaran 7 (tanpa GRT ulang) di atas hasil putaran 6 (p16_10m_eco6/run): dioda untuk pin gate pelanggar antena\n"
     "# pasca-DRT, perbesaran driver sel standar dan buffer pin makro untuk pelanggar kapasitansi (checks.rpt semua corner).\n"
     "# Route guide net lain, termasuk jumper, tidak diubah. Lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu signoff_nomacro.\n"
     "# Hasil putaran 6 hanya dibaca.",
     "# ECO putaran 8 (tanpa GRT ulang) di atas hasil putaran 7 (p16_10m_eco7/run): dioda + jumper met1 untuk net pelanggar\n"
     "# antena pasca-DRT, buffer pemecah beban (driver sel standar) dan buffer pin makro untuk pelanggar kapasitansi\n"
     "# (checks.rpt semua corner). Route guide net lain tidak diubah. Lanjutkan alur dari OpenROAD.STAMidPNR-3, lalu\n"
     "# signoff_nomacro. Hasil putaran 7 hanya dibaca."),
    ("p16_10m_eco7", "p16_10m_eco8"),
    ("p16_10m_eco6", "p16_10m_eco7"),
    ("cp $S/eco6.py $S/eco6_views.tcl $X/", "cp $S/eco8.py $S/eco8_views.tcl $S/guide_jumper.py $X/"),
    ("eco6_views.tcl", "eco8_views.tcl"),
    ("-e ECO_TAG=7", "-e ECO_TAG=8"),
    ("/w/eco/eco6.py \\", "/w/eco/eco8.py \\"),
    ("/w/eco/eco6_in.odb /w/eco/dioda_pins.txt /w/eco/cap_pins.txt /w/eco/resize.txt 2>&1",
     "/w/eco/eco8_pre.odb /w/eco/dioda_pins.txt /w/eco/cap_pins.txt /w/eco/resize.txt /w/eco/jumper.txt 2>&1"),
    ('[ -s $X/eco6_in.odb ] || { echo "eco6_in.odb tidak ada, berhenti"; exit 1; }',
     '[ -s $X/eco8_pre.odb ] || { echo "eco8_pre.odb tidak ada, berhenti"; exit 1; }\n'
     'log "jumper: $(wc -l < $X/jumper.txt) net met1"\n'
     "docker run --rm -v $W:/w $IMG openroad -python -exit /w/eco/guide_jumper.py \\\n"
     "  /w/eco/eco8_pre.odb /w/eco/eco8_in.odb /w/eco/eco8_in.def /w/eco/jumper.txt 2>&1 "
     '| grep -E "JUMPER|tidak ditemukan|Error|Trace" | tail -8\n'
     '[ -s $X/eco8_in.odb ] || { echo "eco8_in.odb tidak ada, berhenti"; exit 1; }'),
    ("-e ECO_ODB=/work/eco/eco6_in.odb", "-e ECO_ODB=/work/eco/eco8_in.odb"),
    ('log "ECO: perbesar sel + cek penempatan + tulis view"', 'log "ECO: cek penempatan + tulis view"'),
]
for a, b in rep:
    if a not in s:
        sys.exit("pola tidak ditemukan: " + a[:70])
    s = s.replace(a, b)
dst.write_text(s)
print("tulis", dst)
