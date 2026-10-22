#!/usr/bin/env bash
# Kemas bitstream KV260 menjadi aplikasi xmutil (Ubuntu Kria): <nama>.bit.bin + <nama>.dtbo + shell.json.
# Dari ROOT repo: target/kv260/axi/flow/make_app.sh [P]     (default P=32; masukan $SUARATB_DATA/build/kv260/full_P<P>/kv260_top_P<P>.bit)
# Keluaran: $SUARATB_DATA/build/kv260/app/suaratb/  -> salin foldernya ke /lib/firmware/xilinx/ di papan, lalu
#           sudo xmutil unloadapp && sudo xmutil loadapp suaratb
# Overlay: muat bitstream ke region fpga_full, nyalakan PL0_REF (zynqmp_clk 71) ~100 MHz lewat driver xlnx,fclk,
#          dan toggle reset PL (zynqmp_reset 116 = pl_resetn0). Desain tidak memakai AXI, jadi tidak ada node perangkat.
# Varian AXI: BITFILE=$SUARATB_DATA/build/kv260/axil_P32/suaratb_axil_P32.bit NAME=suaratb_axil (bitstream mana pun).
# Env: VIVADO_BIN (folder bin Vivado; berisi bootgen dan dtc), NAME (nama aplikasi, default suaratb), SUARATB_DATA,
#      TAG (akhiran folder build, mis. _distill -> full_P32_distill; sama dengan TAG di run.sh).
set -euo pipefail
P=${1:-32}
D=${SUARATB_DATA:-/data/suaratb}
VB=${VIVADO_BIN:-/data/tools/Xilinx/2026.1/Vivado/bin}
NAME=${NAME:-suaratb}
BIT=${BITFILE:-$D/build/kv260/full_P$P${TAG:-}/kv260_top_P$P.bit}
OUT=$D/build/kv260/app/$NAME
PL0_HZ=99999001   # pl_clk0 aktual dari block design (create_bd.tcl, log build)

[ -f "$BIT" ] || { echo "tidak ada $BIT"; exit 1; }
rm -rf "$OUT"; mkdir -p "$OUT"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

# 1) .bit -> .bit.bin (tanpa header, urutan byte untuk FPGA Manager Linux)
cp "$BIT" "$W/$NAME.bit"
printf 'all:\n{\n  [destination_device = pl] %s.bit\n}\n' "$NAME" > "$W/$NAME.bif"
(cd "$W" && "$VB/bootgen" -image "$NAME.bif" -arch zynqmp -process_bitstream bin -w on > bootgen.log 2>&1) \
  || { cat "$W/bootgen.log"; exit 1; }
cp "$W/$NAME.bit.bin" "$OUT/"

# 2) device tree overlay
cat > "$W/$NAME.dts" <<EOF
/dts-v1/;
/plugin/;
/ {
	fragment@0 {
		target = <&fpga_full>;
		__overlay__ {
			#address-cells = <2>;
			#size-cells = <2>;
			firmware-name = "$NAME.bit.bin";
			resets = <&zynqmp_reset 116>;
		};
	};
	fragment@1 {
		target = <&amba>;
		__overlay__ {
			suaratb_fclk0: suaratb_fclk0 {
				compatible = "xlnx,fclk";
				clocks = <&zynqmp_clk 71>;
				assigned-clocks = <&zynqmp_clk 71>;
				assigned-clock-rates = <$PL0_HZ>;
				clock-output-names = "fabric_clk";
				#clock-cells = <0>;
			};
		};
	};
};
EOF
"$VB/dtc" -@ -q -I dts -O dtb -o "$OUT/$NAME.dtbo" "$W/$NAME.dts"
cp "$W/$NAME.dts" "$OUT/$NAME.dts"   # sumber overlay, untuk dibaca/diubah di papan bila perlu

# 3) label aplikasi untuk xmutil/dfx-mgr
cat > "$OUT/shell.json" <<EOF
{
  "shell_type" : "XRT_FLAT",
  "num_slots": "1"
}
EOF

echo "P=$P -> $OUT"
ls -l "$OUT"
sha256sum "$OUT"/*
