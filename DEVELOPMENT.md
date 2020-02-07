# Development

While initially the main idea was to implement the simulation in Migen/Litex, a big part of the simulation has been implemented using [cocotb](https://github.com/cocotb/cocotb) in the [USB test suite](https://github.com/antmicro/usb-test-suite-cocotb-usb/tree/jboc/fx2/cocotb_usb/fx2).
The motivation to move to *cocotb* was simplicity.
The reason why the development of the FX2 simulator has been started in the first place, was to allow users to test their FX2 firmware (its logic) in a simulation.
This means that we do not need a full simulation of the SoC and we will not synthesise our model.
*cocotb* allows to develop some features much faster, so it seems as a good choice here.

## Relevant repositories/branches

* https://github.com/antmicro/fx2-sim
* https://github.com/antmicro/usb-test-suite-build/tree/jboc/fx2
* https://github.com/antmicro/usb-test-suite-testbenches/tree/jboc/fx2
* https://github.com/antmicro/usb-test-suite-cocotb-usb/tree/jboc/fx2

## Current state

At the moment, a minimal demo has been implemented.
It uses the firmware in *firmware/fx2usb/main.c* to handle USB control transfers by polling SUDAV interrupt flag and manually calling `isr_SUDAV`.

- implemented CSRs realted to endpoint 0
- implemented usb control transfers handling
- added data bit synchronisation checks and generation
- FX2 features:
    - automatic copying of of descriptors data using SUDPTR
    - automatic handling of SET_ADDRESS requests
    - autopointers for faster data copying
- modified CSR implementation to support clear-on-write and read-only access
- able to run simulation with simple firmware that uses libfx2
- passes tests:
    - test-basic - simple request and response
    - test-sequence - multiple IN/OUT transactions
    - test-enum - enumeration process
- Travis runs linter and tests (test-basic, test-sequence, test-enum) in [usb-test-suite-build](https://github.com/antmicro/usb-test-suite-build/tree/jboc/fx2)

When running all tests (some are not relevant as are only for specific IPs):

* test-basic.py       [3/3]
* test-cdc.py         [0/1]
* test-clocks.py      [0/3]
* test-enum.py        [1/1]
* test-eptri.py       [1/17]
* test-macOSenum.py   [1/1]
* test-sequence.py    [3/3]
* test-sof.py         [1/2]
* test-valenty-cdc.py [0/1]
* test-w10enum.py     [1/1]

## USB state machine

To mimic behaviour of FX2 we have to implement its USB state machine.
This has been done basing on USB 2.0 specification and FX2 TRM in [usb.py](https://github.com/antmicro/usb-test-suite-cocotb-usb/tree/jboc/fx2/cocotb_usb/fx2/usb.py).
The current implementation is quite chaotic.
The [comment](https://github.com/antmicro/usb-test-suite-cocotb-usb/blob/jboc/fx2/cocotb_usb/fx2/usb.py#L16) in that file describes the problem with current implementation.
Basically, it is probably best to rewrite the simulation of FX2 internals into separate coroutine.
These issues should be addressed before continuing with development.

## USB/IP

As the FX2 simulator should help when developing FX2 firmware, it would be good if we could create a virtual USB device in our system that is connected to the simulation.
This way one could transparently work with FX2, regardless of whether it is being simulated or not.

To achieve this we could use [USB/IP protocol](http://usbip.sourceforge.net/).
This has been [already used in Renode](https://renode.readthedocs.io/en/latest/tutorials/usbip.html) for the same purpose.
What's more, we could make this feature a little bit more general by extending the capabilities of USB test suite.
USB/IP allows to transfer data through a socket, so we could do this for any of the IPs simulated in USB test suite to test them on real system.
This would require implementing "separate mode" in the test suite where USB host would just transfer the data between the socket and IP.
