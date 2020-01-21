# 19.04 for sdcc>3.5.0 (on 18.04 it is still 3.5.0)
FROM ubuntu:19.04

# install system packages
RUN apt-get update && apt-get install -y \
        git \
        make sdcc \
        python3 python3-pip \
        libevent-dev libjson-c-dev verilator

# install python packages
RUN pip3 install intelhex
# fix wrong permissions for intelhex binaries (as they are not executable in 2.2.1)
RUN chmod a+x /usr/local/bin/*.py

# install Litex and all its dependencies
ADD https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py litex_setup.py
RUN python3 litex_setup.py init install


# build firmware .bin files
WORKDIR /fx2-sim
COPY firmware /fx2-sim/firmware
RUN make -C firmware clean && make -C firmware && \
        cp firmware/*/*.bin firmware/ && \
        make -C firmware clean

COPY fx2 /fx2-sim/fx2
