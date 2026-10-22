"""Mode mic1: mikrofon INMP441, audio saja, sesi --n batuk (pembungkus axil_mic.py; butuh root).

    sudo python3 mic1.py [--n 10] [--ambang 35]
Bukan diagnosis.
"""
import sys

from axil_mic import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
