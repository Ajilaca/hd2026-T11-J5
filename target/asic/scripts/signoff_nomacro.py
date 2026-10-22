"""Pemeriksaan integrasi cnn_top dengan makro SRAM sebagai IP terverifikasi (OpenRAM): instans makro dihapus dari GDS Magic
dan GDS KLayout hasil run, lalu XOR (Magic vs KLayout) dan KLayout DRC sky130 dijalankan pada sisanya (sel standar, routing,
PDN, pin makro di routing). Isi makro tidak diperiksa: Magic menulis ulang isi makro saat StreamOut (XOR penuh P16: 41,7 juta
selisih, semua di layer penanda/pin/kontak/implan makro) dan bitcell memakai aturan SRAM (Magic DRC penuh P16: 33 juta
pelanggaran, semua di dalam makro). Sambungan ke makro tetap dibuktikan LVS (netlist SPICE makro).
Dipanggil layout_cnn_macro.py setelah run; sendiri: python target/asic/scripts/signoff_nomacro.py <dir run> (mis. .../cnn_top/p16/run)
Keluaran: <dir run>/../signoff_nomacro/ (GDS tanpa makro, xor.xml, drc.xml, log) dan ringkasan ke stdout.
"""
from __future__ import annotations
import collections, json, os, pathlib, subprocess, sys
import xml.etree.ElementTree as ET

IMG = "ghcr.io/efabless/openlane2:2.3.10"
PRUNE = """import sys, klayout.db as db
ly = db.Layout(); ly.read(sys.argv[1]); top = ly.top_cell(); n = 0
for i in list(top.each_inst()):
    if "sky130_sram" in i.cell.name:
        i.delete(); n += 1
for c in [c for c in ly.top_cells() if c.cell_index() != top.cell_index()]:
    ly.prune_cell(c.cell_index(), -1)          # sel makro yatim (top kedua) beserta subselnya
ly.write(sys.argv[2]); print(f"{sys.argv[1]}: {n} instans makro dihapus, top={[c.name for c in ly.top_cells()]}")
"""


def _count(xml: pathlib.Path) -> collections.Counter:
    c = collections.Counter()
    if xml.exists():
        for _, el in ET.iterparse(xml):
            if el.tag == "item":
                c[(el.findtext("category") or "?").strip("'")] += 1
                el.clear()
    return c


def run(run_dir: pathlib.Path, threads: int = 6) -> dict:
    run_dir = pathlib.Path(run_dir).resolve(); w = run_dir.parent; rel = run_dir.relative_to(w).as_posix()
    out = w / "signoff_nomacro"; out.mkdir(exist_ok=True)
    pdk = next((pathlib.Path.home() / ".volare/volare/sky130/versions").iterdir()).name
    (out / "prune.py").write_text(PRUNE)
    # GDS Magic: final/mag_gds bila ada (PRIMARY_GDSII_STREAMOUT_TOOL=klayout -> final/gds = salinan GDS KLayout), selain itu final/gds
    mag = next(iter(sorted((run_dir / "final/mag_gds").glob("*.gds"))), None) or run_dir / "final/gds/cnn_top.gds"
    (out / "run.sh").write_text(f"""set -e
cd /w
python3 signoff_nomacro/prune.py {mag.relative_to(w).as_posix()} signoff_nomacro/magic_nomacro.gds
python3 signoff_nomacro/prune.py {rel}/final/klayout_gds/cnn_top.klayout.gds signoff_nomacro/klayout_nomacro.gds
XOR=$(python3 -c 'import openlane, os; print(os.path.dirname(openlane.__file__))')/scripts/klayout/xor.drc
ruby $XOR --output signoff_nomacro/xor.xml --top cnn_top --threads {threads} --ignore 81/14 \\
  signoff_nomacro/magic_nomacro.gds signoff_nomacro/klayout_nomacro.gds > signoff_nomacro/xor.log 2>&1
klayout -b -zz -r /pdk/volare/sky130/versions/{pdk}/sky130A/libs.tech/klayout/drc/sky130A_mr.drc \\
  -rd input=signoff_nomacro/klayout_nomacro.gds -rd topcell=cnn_top -rd report=signoff_nomacro/drc.xml \\
  -rd feol=true -rd beol=true -rd floating_metal=false -rd offgrid=true -rd seal=true -rd threads={threads} \\
  > signoff_nomacro/drc.log 2>&1
""")
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{w}:/w", "-v", f"{pathlib.Path.home()}/.volare:/pdk", IMG,
                        "sh", "/w/signoff_nomacro/run.sh"], capture_output=True, text=True)
    print(r.stdout.strip(), flush=True)
    if r.returncode:
        print(f"signoff_nomacro: GAGAL (exit {r.returncode}): {r.stderr[-400:]}", flush=True)
    xor, drc = _count(out / "xor.xml"), _count(out / "drc.xml")
    res = {"xor_nomacro": sum(xor.values()), "klayout_drc_nomacro": sum(drc.values()),
           "xor_nomacro_layer": dict(xor), "klayout_drc_nomacro_rule": dict(drc), "ok": r.returncode == 0}
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    print(f"signoff tanpa makro: XOR={res['xor_nomacro']} KLayout DRC={res['klayout_drc_nomacro']} "
          f"{dict(drc.most_common(5)) if drc else ''} (rincian: {out / 'summary.json'})", flush=True)
    return res


if __name__ == "__main__":
    run(pathlib.Path(sys.argv[1]), int(os.environ.get("KLAYOUT_THREADS", "6")))
