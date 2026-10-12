#!/usr/bin/env bash
# run_all.sh — 一键 RTL2GDS (Linux + OpenROAD 环境)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
NETLIST="${1:?usage: run_all.sh <mapped.v>}"
TECH_LEF="${2:?usage: ... <tech.lef>}"
LIB="${3:?usage: ... <typical.lib>}"

cat > "$ROOT/env.tcl" << ENV
set TECH_LEF  "$TECH_LEF"
set MACRO_LEF "$(dirname "$TECH_LEF")/NangateOpenCellLibrary.macro.lef"
set LIB       "$LIB"
set NETLIST   "$NETLIST"
set TOP       "Vortex"
set SDC       "$(dirname "$NETLIST")/project.resolved.sdc"
set SPEF      "$(dirname "$NETLIST")/Vortex.spef"
set SAIF      "$(dirname "$NETLIST")/activity.saif"
set DEF_IN    "$ROOT/run/in.def"
set DEF_OUT   "$ROOT/run/out.def"
set GDS_OUT   "$ROOT/run/design.gds"
ENV

mkdir -p "$ROOT/run" "$ROOT/signoff"
echo "== 1. floorplan =="; openroad -exit "$ROOT/01_floorplan.tcl"
echo "== 2. place    =="; openroad -exit "$ROOT/02_place.tcl"
echo "== 3. CTS      =="; openroad -exit "$ROOT/03_cts.tcl"
echo "== 4. route    =="; openroad -exit "$ROOT/04_route.tcl"
echo "== 5. STA      =="; openroad -exit "$ROOT/05_sta_signoff.tcl"
echo "== 6. PV       =="; openroad -exit "$ROOT/06_pv.tcl"
echo "== 7. IREM     =="; openroad -exit "$ROOT/07_irem.tcl"
echo "RTL2GDS DONE. 报告目录: $ROOT/signoff/"
