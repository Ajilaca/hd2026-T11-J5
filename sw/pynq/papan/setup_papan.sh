#!/usr/bin/env bash
# Pintasan terminal di papan KV260 (Ubuntu). Muat sekali:   source ~/suaratb10/setup_papan.sh
# Permanen (tiap login):                                    echo 'source ~/suaratb10/setup_papan.sh' >> ~/.bashrc
# Konsol serial dari laptop:  sudo picocom -b 115200 --logfile ~/kv260_console.log /dev/ttyUSB1   (keluar: Ctrl+A lalu Ctrl+X)
# Perintah:  axil1 | axil2 [--n N]   mic1 | mic2 [--n N]   cough1 [--n N] | cough_mic   papan_status   papan_bantuan
# Aplikasi PL (suaratb_axil atau suaratb_cough) dimuat otomatis oleh skripnya. Hasil dataset ditulis ke hasil_<mode>_<jam>.txt/.csv di folder paket.
# Folder paket bisa diganti: SUARATB_TBC=~/suaratb6 SUARATB_COUGH=~/cough. Alat triase, bukan diagnosis.
export SUARATB_TBC="${SUARATB_TBC:-$HOME/suaratb10}"
export SUARATB_COUGH="${SUARATB_COUGH:-$HOME/cough}"

_jalan() {   # _jalan <folder> <perintah...>: jalankan sebagai root di folder paket tanpa mengubah folder kerja Anda
  local dir="$1"; shift
  [ -d "$dir" ] || { echo "Folder $dir tidak ada"; return 1; }
  ( cd "$dir" && sudo "$@" )
}
axil1()     { _jalan "$SUARATB_TBC"   python3 axil1.py clips "hasil_axil1_$(date +%H%M%S)" "$@"; }
axil2()     { _jalan "$SUARATB_TBC"   python3 axil2.py clips "hasil_axil2_$(date +%H%M%S)" "$@"; }
mic1()      { _jalan "$SUARATB_TBC"   python3 mic1.py "$@"; }
mic2()      { _jalan "$SUARATB_TBC"   python3 mic2.py "$@"; }
cough1()    { _jalan "$SUARATB_COUGH" python3 cough1.py clips "hasil_cough_$(date +%H%M%S)" "$@"; }
cough_mic() { _jalan "$SUARATB_COUGH" python3 cough_mic.py "$@"; }
papan_status() {
  sudo xmutil listapps
  free -m | sed -n 2p
  df -h / | tail -1
}
papan_bantuan() {
  cat <<'TXT'
Model TBC (folder $SUARATB_TBC)
  axil1 [--n N]    klip dataset, audio saja       (N = 20, 50, atau kosong untuk 100 peserta)
  axil2 [--n N]    klip dataset + gejala peserta
  mic1  [--n N]    mikrofon INMP441, sesi N batuk (bawaan 10), audio saja
  mic2  [--n N]    mikrofon, 6 pertanyaan gejala lalu N batuk
Model batuk vs bukan batuk (folder $SUARATB_COUGH)
  cough1 [--n N]   klip uji (50 batuk, 50 bukan batuk)
  cough_mic        mikrofon: satu keputusan per suara (Ctrl+C berhenti)
Lain-lain
  papan_status     aplikasi PL aktif, memori, ruang disk
TXT
}
echo "SuaraTB siap. Ketik papan_bantuan untuk daftar perintah."
