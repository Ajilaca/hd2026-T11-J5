#!/usr/bin/env bash
# Membuat struktur $SUARATB_DATA dan symlink repo (data/raw, model/out, target/build, ...). Aman dijalankan berulang.
set -eu
cd "$(dirname "$0")/.."
D="${SUARATB_DATA:-$HOME/suaratb-data}"
mkdir -p "$D"/{raw,processed,features,runs,build} data model target
ln -sfn "$D/raw" data/raw
ln -sfn "$D/processed" data/processed
ln -sfn "$D/features" data/features
ln -sfn "$D/runs" model/out
ln -sfn "$D/build" target/build
for l in data/raw data/processed data/features model/out target/build; do printf "%-18s -> %s\n" "$l" "$(readlink "$l")"; done
