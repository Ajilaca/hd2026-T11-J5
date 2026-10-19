# source setup/env.sh   (dari ROOT repo)
# Lokasi data besar (dataset, build, hasil layout). Di WSL2 gunakan folder di dalam filesystem Linux, bukan /mnt/c.
export SUARATB_DATA="${SUARATB_DATA:-$HOME/suaratb-data}"
# sv2v: bila tidak ada di PATH, isi path binernya di sini
[ -z "${SV2V:-}" ] && command -v sv2v >/dev/null && export SV2V="$(command -v sv2v)"
[ -d .venv ] && . .venv/bin/activate
echo "SUARATB_DATA=$SUARATB_DATA  SV2V=${SV2V:-tidak ada}"
