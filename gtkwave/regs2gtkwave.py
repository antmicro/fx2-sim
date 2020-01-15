#!/usr/bin/env python

import re
import ast
import argparse

# named group
g = lambda name, regex: r'(?P<{name}>{regex})'.format(name=name, regex=regex)

# match e.g. these lines:
#  _SFR(0x80) IOA; ///< Register 0x80: Port A
#      _SBIT(0x80 + 0) PA0; ///< Register 0x80 bit 0: Port A bit PA0
pattern_str = r'\s*{macro}\({address}\)\s+{name};'.format(
    macro=g('macro', r'_SFR|_SFR16|_SBIT|_IOR|_IOR16'),
    address=g('address', r'[^)]+'),
    name=g('name', r'\S+'),
)
pattern = re.compile(pattern_str)


def parse_args():
    desc = 'Create GTKWave filter file from libfx2 register description'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('fx2regs', help='Path to fx2regs.h file')
    parser.add_argument('-w', '--width', default='4',
                        help='Width (in characters) of the hex value')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    matches = []
    with open(args.fx2regs) as f:
        for line in f:
            match = pattern.match(line)
            if match:
                matches.append(match)

    lines = []
    for m in matches:
        fmt = '{val:0%dx} {name}' % int(args.width)
        # avoid eval() assuming we always have hex or hex + dec
        adr = m.group('address')
        if '+' in adr:
            h, d = adr.split('+')
            adr_val = int(h, 16) + int(d)
        else:
            adr_val = int(adr, 16)
        name = m.group('name').replace(' ', '_')

        # expand arrays
        arr_m = re.match('([^]]*)\[(\d+)\]$', name)
        if arr_m:
            for i in range(int(arr_m.group(2))):
                line = fmt.format(val=adr_val + i, name='%s[%d]' % (arr_m.group(1), i))
                lines.append(line)
        else:  # one entry
            line = fmt.format(val=adr_val, name=m.group('name').replace(' ', '_'))
            lines.append(line)

    contents = '\n'.join(lines)
    print(contents)
