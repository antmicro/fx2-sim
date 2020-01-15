#!/usr/bin/env bash
# example commands to compare reults

HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
cd "$HERE/../.." || exit 1  # go to fx2 level directory

if (( $# < 1 )); then
  base_name="simple"
else
  base_name="$1"
fi

echo "Using base program name: $base_name"

# be sure to make our file
make -C test/ $base_name.bin

# run simulation, cancel with Ctrl+C as soon as it starts to speed up
# VCD file parsing in pc_compare.py
# (i.e. quit when it prints "[ethernet] loaded (0x55765ddf3190)")
python sim.py "test/$base_name.bin"

# compare results
test/pc-compare/pc_compare.py \
  "test/$base_name.ihx" "build/dut.vcd" "diff.html" -n 200

# results are in diff.html
# they won't be the same as in verilator simulation pc will e.g. increment after a jump
