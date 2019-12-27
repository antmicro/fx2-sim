#include <stdint.h>

__xdata __at(0xe000) uint8_t scratch[512];
__xdata __at(0x3000) uint8_t reg;

int main()
{
  while (1)  {
    reg++;
    scratch[0]++;
  }
}
