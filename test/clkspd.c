#include <stdint.h>

__xdata __at(0xe600) uint8_t CPUCS;

#define _CLKSPD_OFFSET (3)
#define _CLKSPD0 (1U << _CLKSPD_OFFSET)
#define _CLKSPD1 (1U << (_CLKSPD_OFFSET + 1))
#define _CLKSPD_MASK (_CLKSPD0 | _CLKSPD1)

int main()
{
  int i = 0;
  uint8_t cpuspd = 0;

  while (1) {

    i = 0;
    while (i < 10) {
      i++;
    }

    // modify clock frequency
    cpuspd = (CPUCS & _CLKSPD_MASK) >> _CLKSPD_OFFSET;
    cpuspd++;
    if (cpuspd > 2) {
      cpuspd = 0;
    }
    CPUCS = cpuspd << _CLKSPD_OFFSET;

  }
}
