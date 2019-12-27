#!/usr/bin/env bash

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

set -e


if ! [[ -v VIRTUAL_ENV ]]; then
    echo 'Run this from inside python virtual environment'
    exit 1
fi

if ! command -v sdcc >/dev/null 2>&1; then
    echo 'You will need sdcc to compile software, see:'
    echo '  http://sdcc.sourceforge.net/'
    exit 1
fi


# install other required packages outside the repo
install_dir="$INSTALL_DIR"
if ! [[ -v INSTALL_DIR ]]; then  # default path
    dir_name="$(basename $SCRIPT_DIR)"
    install_dir="$SCRIPT_DIR/../${dir_name}-env"
fi

echo "Installing additional packages to $install_dir ..."
[[ -d "$install_dir" ]] && { echo "Directory already exists!"; exit 1; }
mkdir "$install_dir"


# install Litex using litex_setup.py script
pushd "$install_dir" > /dev/null || exit 1
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
chmod +x litex_setup.py
./litex_setup.py init install
popd > /dev/null || exit 1


# create simple binary file (requires sdcc)
pip install IntelHex

# fix wrong permissions for IntelHex binaries (as they are not executable in 2.2.1)
[[ -f "$VIRTUAL_ENV/bin/hex2bin.py" ]] || { echo "Cannot find hex2bin.py!"; exit 1; }
pushd "$VIRTUAL_ENV/bin" > /dev/null || exit 1
chmod u+x bin2hex.py hex2bin.py hex2dump.py hexdiff.py hexinfo.py hexmerge.py || true
popd > /dev/null || exit 1


cat <<EOF
Make sure to install requred system packages, on Ubuntu:
    sudo apt install libevent-dev libjson-c-dev

Now you can run the simulation:
    cd fpga-ecosystem-litex/fx2/
    make -C test
    python fx2/sim.py test/simple.bin
    gtkwave fx2/build/dut.vcd
EOF
