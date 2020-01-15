import re
import sys
import argparse
import subprocess


def run_sim(intel_hex_file, n_steps):
    commands_in = '\n'.join(['step'] * n_steps) + '\n'
    sim = subprocess.run(['s51', '-t', '8051', intel_hex_file],
                         input=commands_in, text=True, check=True,
                         stdout=subprocess.PIPE)
    results = {
        'pc': parse_pc(sim.stdout)
    }
    return results


def parse_pc(stdout):
    pc_pattern = r'Stop at 0x([0-9a-fA-F]+):'
    matches = re.findall(pc_pattern, stdout, re.MULTILINE)
    pcs = [int(m, 16) for m in matches]
    return pcs


def parse_args():
    desc = 'Run ucsim 8051 simulation using given program'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('intel_hex', help='Program file in Intel Hex format')
    parser.add_argument('steps', type=int, help='Number of simulation steps')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    results = run_sim(args.intel_hex, args.steps)
    print(' '.join([hex(pc) for pc in results['pc']]))
