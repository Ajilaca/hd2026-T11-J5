# Lanjutan eco6.py di lingkungan langkah OpenROAD.ResizerTimingPostGRT (hasil eject): baca ODB berisi sel ECO,
# terapkan perbesaran sel dari RESIZE_LST (replace_cell butuh liberty), cek legalitas penempatan, cek pin sel yang
# diperbesar masih di dalam guide net-nya, lalu tulis view (write_views memasang global connect power untuk sel baru).
# Tanpa dpl/grt, sehingga route guide (termasuk jumper) tetap seperti di ODB masukan.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set ::env(CURRENT_ODB) $::env(ECO_ODB)
read_current_odb
set block [ord::get_db_block]

set f [open $::env(RESIZE_LST)]
foreach line [split [read $f] "\n"] {
    if { [llength $line] < 4 } { continue }
    lassign $line name master x y
    set inst [$block findInst $name]
    if { $inst == "NULL" } { puts "ECO6 resize: $name tidak ditemukan"; exit 1 }
    replace_cell [get_cells $name] $master
    $inst setLocation $x $y
    foreach it [$inst getITerms] {
        set net [$it getNet]
        if { $net == "NULL" || [$it getSigType] != "SIGNAL" } { continue }
        set bb [$it getBBox]
        set cx [expr {([$bb xMin] + [$bb xMax]) / 2}]; set cy [expr {([$bb yMin] + [$bb yMax]) / 2}]
        set ok 0
        foreach g [$net getGuides] {
            set r [$g getBox]
            if { [$r xMin] <= $cx && $cx <= [$r xMax] && [$r yMin] <= $cy && $cy <= [$r yMax] } { set ok 1; break }
        }
        puts "ECO6 resize: $name -> [[$inst getMaster] getName] pin [[$it getMTerm] getName] di dalam guide: $ok"
    }
}
close $f

check_placement -verbose
set n 0
foreach net [$block getNets] { incr n [llength [$net getGuides]] }
puts "ECO6 guide total: $n"
write_views
