"""Mode axil1: klip dataset lewat AXI4-Lite, audio saja (pembungkus axil_batch.py; butuh root).

    sudo python3 axil1.py clips hasil [--n 20]
Sama dengan: sudo python3 axil_batch.py clips hasil manifest.csv [--n 20]. Bukan diagnosis.
"""
import sys

from axil_batch import main

if __name__ == "__main__":
    a = sys.argv[1:]
    if "manifest.csv" not in a:
        a = a[:2] + ["manifest.csv"] + a[2:]
    sys.exit(main(a))
