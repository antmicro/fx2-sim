#!/usr/bin/env python3

import os
import sys
import pprint
import difflib
import argparse
import itertools

import vcdvcd

import ucsim


def vcd_convert(data, signals):
    """
    `data` obtained from .get_signals() has a form of a dictionary with strange
    key names (e.g. '7#'), then, for each key, it has a dictionary with keys:
      'references' - here we will have the actual signal name
      'size' - N bytes
      'var_type' - e.g. 'wire'
      'tv' - actual data stored as list of tuples (time: int, value: str)
             each `value` is a binary number as a string
    This function converts that to a dictionary that we can reference by normal names.
    """
    conv = {}
    for sig in signals:
        # check
        for data_key in data.keys():
            if sig in data[data_key]['references']:
                conv[sig] = data[data_key]
                break
        assert sig in conv, 'Signal "%s" not found' % sig
    return conv


def get_vcd_data(file, signals):
    all_signals = vcdvcd.VCDVCD(file, only_sigs=True).get_signals()
    for sig in signals:
        assert sig in all_signals, 'Signal %s not found in file %s' % (sig, file)
    data = vcdvcd.VCDVCD(file, signals=signals).get_data()
    return vcd_convert(data, signals)


def show_signals(file):
    signals = vcdvcd.VCDVCD(file, only_sigs=True).get_signals()
    pprint.pprint(signals)


def parse_args():
    desc = """
    Compare execution in ucsim with VCD dump from another simulation by comparing PC.
    Produces diff in text form or in side-by-side html form.
    WARNING: html diff from python's difflib takes ages for more steps!
    (implementation is recursive? use max ~300 steps)
    """
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('intel_hex',
                        help='Intel hex file with program to be run on simulator')
    parser.add_argument('vcd',
                        help='VCD dump from another simulation')
    parser.add_argument('diff_out',
                        help='Output diff file. If it has .html extension, HTML diff will be produced')
    parser.add_argument('--show-signal-names', action='store_true',
                        help='Only show signal names from VCD file, don\'t do anything else')
    parser.add_argument('-n', '--steps', default=None, help='Number of steps to analyse')
    parser.add_argument('-o', '--output-raw', nargs=2, required=False,
                        help='Output reference (1) and simulation (2) values to the given files.'
                        + ' This can be used to later diff values using, e.g. vimdiff or diff2html')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    assert os.path.isfile(args.intel_hex), args.intel_hex
    assert os.path.isfile(args.vcd), args.vcd

    # special case to ease identification of signal names
    if args.show_signal_names:
        show_signals(args.vcd)
        sys.exit(0)

    print('Analyzing VCD file ...')
    pc_signal = 'TOP.dut.oc8051_top.pc[15:0]'
    vcd_data = get_vcd_data(args.vcd, [pc_signal])
    # extract PC values, ignore the timing data
    vcd_pc = [int(tv[1], 2) for tv in vcd_data[pc_signal]['tv']]

    # run simulation for whole length of PC changes or as long as requested
    n_steps = int(args.steps) if args.steps is not None else len(vcd_pc)
    print('Running %d simulation steps ...' % n_steps)
    sim_results = ucsim.run_sim(args.intel_hex, n_steps)
    sim_pc = sim_results['pc']

    # convert each integer value to a line for difflib, take only as much as needed
    pc_to_line = lambda pc: hex(pc) + '\n'
    pc_tested = list(itertools.islice(map(pc_to_line, vcd_pc), n_steps))
    pc_ref = list(itertools.islice(map(pc_to_line, sim_pc), n_steps))

    # this could be used to ignore some wrong PC values at simulation start
    # but it can easily fail and diff should pick it up anyway and put at the begining
    #  # ignore first few PCs from siulation up to first matching sequence
    #  match_len = 3
    #  i = 0
    #  ignored = None
    #  while i < n_steps and not ignored:
    #      if pc_tested[i:i + match_len] == pc_ref[:match_len]:
    #          found = True
    #          ignored = pc_tested[:i]
    #          pc_tested = pc_tested[i:]
    #      i += 1
    #  assert ignored, 'Could not find any matching sequence of %d values' % match_len
    #
    #  if ignored is not None:
    #      print('Ignored first %d values: %s' % (len(ignored), ignored))
    #
    #  # unify lengths if one was longer
    #  pc_ref = pc_ref[:len(pc_tested)]

    if args.output_raw:
        print('Saving ref to %s ...' % args.output_raw[0])
        with open(args.output_raw[0], 'w') as f:
            f.writelines(pc_ref)
        print('Saving dut to %s ...' % args.output_raw[1])
        with open(args.output_raw[1], 'w') as f:
            f.writelines(pc_tested)
    else:
        if args.diff_out.lower().endswith('.html'):
            # html diff
            print('Saving html diff to %s ...' % args.diff_out)
            # TODO: this is so slow for longer diffs...
            diff = difflib.HtmlDiff().make_file(pc_ref, pc_tested, fromdesc='ucsim reference', todesc='simulation vcd file')
            with open(args.diff_out, 'w') as f:
                f.writelines(diff)
        else:
            # text diff
            print('Saving context diff to %s ...' % args.diff_out)
            diff = difflib.unified_diff(pc_tested, pc_ref)
            with open(args.diff_out, 'w') as f:
                f.writelines(diff)
