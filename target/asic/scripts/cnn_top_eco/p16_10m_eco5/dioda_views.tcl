# Lanjutan dioda_eco.py di lingkungan langkah OpenROAD.ResizerTimingPostGRT (hasil eject): baca ODB berisi dioda,
# cek legalitas penempatan, lalu tulis view (write_views memasang global connect power untuk sel baru).
# Tanpa dpl/grt, sehingga route guide (termasuk jumper) tetap seperti di ODB masukan.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set ::env(CURRENT_ODB) $::env(ECO_ODB)
read_current_odb
check_placement -verbose
set n 0
foreach net [[ord::get_db_block] getNets] { incr n [llength [$net getGuides]] }
puts "DIODA guide total: $n"
write_views
