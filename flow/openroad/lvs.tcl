# lvs.tcl — Magic LVS 脚本 (Linux: magic -dnull -noconsole lvs.tcl)
gds read design.gds
load design
extract all
ext2spice lvs
ext2spice
quit
