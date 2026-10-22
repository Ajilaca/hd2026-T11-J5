# Buat run_eco4.sh dari run_eco3.sh: sumber p16_10m_eco3, tujuan p16_10m_eco4, prefix ECO_CAP40, dan target jumper =
# gabungan pelanggar met1 dari laporan antena semua run sebelumnya (jumper kumulatif: GRT ECO membuat ulang route guide,
# sehingga jumper putaran lama hilang bila hanya target putaran terakhir yang dipakai).
import pathlib, sys
src, dst = map(pathlib.Path, sys.argv[1:3])
s = src.read_text()
rep = [
    ("p16_10m_eco3", "p16_10m_eco4"),
    ("SRCD=$B/p16_10m_eco2;", "SRCD=$B/p16_10m_eco3;"),
    ("cd /b/p16_10m_eco2 &&", "cd /b/p16_10m_eco3 &&"),
    ("dari p16_10m_eco2/run", "dari p16_10m_eco3/run"),
    ("CAP_PREFIX:-ECO_CAP30", "CAP_PREFIX:-ECO_CAP40"),
    ("# ECO putaran 3 di atas hasil putaran 2 (p16_10m_eco2/run)", "# ECO putaran 4 di atas hasil putaran 3 (p16_10m_eco3/run)"),
    ("lalu jumper met1 dengan target dari laporan antena putaran sumber",
     "lalu jumper met1 dengan target gabungan laporan antena semua run sebelumnya"),
    ("python3 - $BASE/44-openroad-checkantennas-1/reports/antenna_summary.rpt > $X/targets.txt <<'EOF'",
     "A=44-openroad-checkantennas-1/reports/antenna_summary.rpt\n"
     "python3 - $B/p16_10m/runs/p16_10m/$A $B/p16_10m_eco/run/$A $B/p16_10m_eco2/run/$A $BASE/$A > $X/targets.txt <<'EOF'"),
    ("""for line in open(sys.argv[1], encoding="utf-8"):
    p = [x.strip() for x in line.split("\\u2502")]
    if len(p) >= 7 and p[6] == "met1":
        print(p[4], p[5], "x", p[2])""",
     """best = {}
for f in sys.argv[1:]:
    for line in open(f, encoding="utf-8"):
        p = [x.strip() for x in line.split("\\u2502")]
        if len(p) >= 7 and p[6] == "met1" and (p[4] not in best or float(p[2]) > float(best[p[4]][2])):
            best[p[4]] = (p[4], p[5], p[2])
for n, pin, partial in best.values():
    print(n, pin, "x", partial)"""),
]
for a, b in rep:
    if a not in s:
        sys.exit("pola tidak ditemukan: " + a[:70])
    s = s.replace(a, b)
dst.write_text(s)
print("tulis", dst)
