"""Render GDSII sky130 ke PNG dengan layer berlabel singkat + legenda. Dari ROOT repo:
  python target/asic/render_layout.py <gds> <png> [lebar_px] [judul]
Layer (GDS lapisan/tipe, nama pendek): nwell 64/20, diff 65/20, tap 65/44, poly 66/20, licon 66/44, li1 67/20, mcon 67/44,
met1 68/20, via1 68/44, met2 69/20, via2 69/44, met3 70/20, via3 70/44, met4 71/20, via4 71/44, met5 72/20. KLayout dijalankan di Docker.
"""
from __future__ import annotations
import os, pathlib, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

LAYERS = [  # nama, lapisan/tipe, warna RGB
    ("nwell", "64/20", (130, 130, 130)), ("diff", "65/20", (60, 180, 75)), ("tap", "65/44", (170, 255, 195)),
    ("poly", "66/20", (220, 40, 40)), ("licon", "66/44", (255, 150, 150)), ("li1", "67/20", (255, 130, 0)),
    ("mcon", "67/44", (255, 215, 0)), ("met1", "68/20", (0, 120, 255)), ("via1", "68/44", (120, 200, 255)),
    ("met2", "69/20", (180, 60, 220)), ("via2", "69/44", (220, 150, 255)), ("met3", "70/20", (0, 200, 200)),
    ("via3", "70/44", (130, 235, 235)), ("met4", "71/20", (230, 220, 40)), ("via4", "71/44", (250, 245, 150)),
    ("met5", "72/20", (255, 80, 160)),
]
IMG = "ghcr.io/efabless/openlane2:2.3.10"


def main(gds: pathlib.Path, png: pathlib.Path, px: int = 2400, title: str | None = None) -> None:
    rows = "\n".join(
        f'n=pya.LayerPropertiesNode(); n.name="{nm}"; n.source_layer={ly.split("/")[0]}; n.source_datatype={ly.split("/")[1]}; '
        f'n.fill_color=0x{r:02x}{g:02x}{b:02x}; n.frame_color=0x{r:02x}{g:02x}{b:02x}; n.dither_pattern=0; lv.insert_layer(lv.end_layers(), n)'
        for nm, ly, (r, g, b) in LAYERS)
    script = f'''import pya
lv = pya.LayoutView()
lv.load_layout("/in/{gds.name}", True)
lv.clear_layers()
{rows}
lv.max_hier(); lv.zoom_fit()
lv.save_image("/out/{png.name}", {px}, {px})
'''
    tmp = png.parent / (png.stem + "_k.py"); tmp.write_text(script)
    subprocess.run(["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "--memory", "2500m", "--memory-swap", "2500m", "-v", f"{gds.parent}:/in:ro", "-v", f"{png.parent}:/out",
                    IMG, "klayout", "-b", "-r", f"/out/{tmp.name}"], check=True)
    tmp.unlink()
    im = Image.open(png).convert("RGB"); d = ImageDraw.Draw(im)
    fs = max(14, px // 100)                                   # ukuran huruf mengikuti lebar gambar
    f = ImageFont.load_default(size=fs); ft = ImageFont.load_default(size=int(fs * 1.4))
    row = int(fs * 1.4); w, h = fs * 11, row * len(LAYERS) + fs
    d.rectangle([8, 8, 8 + w, 8 + h], fill=(20, 20, 20), outline=(200, 200, 200))
    for i, (nm, ly, c) in enumerate(LAYERS):
        y = 8 + fs // 2 + row * i
        d.rectangle([16, y, 16 + fs, y + fs], fill=c); d.text((24 + fs, y - 2), f"{nm} ({ly})", fill=(240, 240, 240), font=f)
    title = title or gds.stem
    d.text((px // 2, 12), title, fill=(255, 255, 255), font=ft, anchor="mt")
    im.save(png)


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve(), int(sys.argv[3]) if len(sys.argv) > 3 else 2400,
         sys.argv[4] if len(sys.argv) > 4 else None)
