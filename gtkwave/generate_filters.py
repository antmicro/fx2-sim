#!/usr/bin/env python3

import os
import re
import itertools


with open('oc8051_defines.v') as f:
    contents = f.read()

splitter = r'^/// '
define_groups = re.split(splitter, contents, flags=re.MULTILINE)

# remove empty groups
define_groups = map(lambda x: x.strip(), define_groups)
define_groups = filter(None, define_groups)

# split into lines
define_groups = map(lambda x: x.split('\n'), define_groups)
define_groups = list(define_groups)

# remove everything after first empty line in each group
empty_line = r'^$'
def remove_others(group_lines):
    new = []
    for line in group_lines:
        if re.match(empty_line, line):
            break
        new.append(line)
    return new
define_groups = map(remove_others, define_groups)
# remove nones
define_groups = list(define_groups)

# remove regular comments at line start
comment = r'^//[^/]'
filter_comments = lambda lines: filter(lambda x: not re.match(comment, x), lines)
define_groups = map(lambda x: list(filter_comments(x)), define_groups)
define_groups = list(define_groups)


for group in define_groups:
    filename = group[0].replace(' ', '_') + '.txt'
    defs = group[1:]

    print()
    print('FILE:', os.path.join('filters', filename))
    __import__('pprint').pprint(group)

    header = '# ' + group[0]
    lines = []

    for define in defs:
        parts = define.split()
        name = parts[1].replace(' ', '_')
        value = parts[2]
        comment = ' '.join(parts[3:]).lstrip('//').strip() if len(parts) > 3 else ''
        # parse value to hex
        n, v = value.split('\'')
        v = v.replace('_', '')

        # handle masks, e.g. 0b10111xxx
        v_versions = []
        if 'x' in v[1:]:
            assert v[0] == 'b', 'only for binary data'
            pat = r'x+'
            match = re.search(pat, v[1:])
            assert match, v
            n_versions = match.end() - match.start()
            all_versions = itertools.product('01', repeat=n_versions)

            for ver_in in all_versions:
                ver = v[:match.start()+1] + ''.join(ver_in) + v[match.end()+1:]
                v_versions.append(ver)
        else:
            v_versions.append(v)

        for v in v_versions:
            if v.startswith('h'):
                val = int('0x' + v[1:], 16)
            elif v.startswith('b'):
                val = int('0b' + v[1:], 2)
            else:
                assert False, value
            new_name = comment or name
            # n can be wrong, use length
            if int(n) >= 8:
                val = ('{:0%dx}' % int(int(n) // 4)).format(val)
                lines.append('{val} {name}'.format(name=new_name.replace(' ', '_'), val=val))
            else:
                # use string length,n may be wrong
                n = len(v) - 1
                val_bin = ('{:0%db}' % int(n)).format(val)
                lines.append('{val} {name}'.format(name=new_name.replace(' ', '_'), val=val_bin))

    with open(os.path.join('filters', filename), 'w') as f:
        f.write('\n'.join([header, *sorted(lines)]))
        f.write('\n')
