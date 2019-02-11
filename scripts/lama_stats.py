#! /usr/bin/env python3

"""
Usage
-----
This script should be run from the root directory (one up from this script)


todo: This bit
$ cd lama_phenotype_detection
$ scripts/lama_stats.py -c <path to stats config> -w <Path to wild type diretory>
"""


import sys
import argparse
from pathlib import Path
from lama import common
from lama.stats.standard_stats.lama_stats_new import run

sys.excepthook = common.excepthook_overide

parser = argparse.ArgumentParser("Stats component of the phenotype detection pipeline")
parser.add_argument('-c', '--config', dest='config', help='path to config', required=True)
parser.add_argument('-w', '--wildtype_dir', dest='wt_dir', help='wild wegistration output root directory', required=True)
parser.add_argument('-m', '--mutant_dir', dest='mut_dir', help='mutant registration output root directory', required=True)
parser.add_argument('-o', '--output_dir', dest='out_dir', help='Output directory to put collated results from all lines', required=True)
parser.add_argument('-t', '--target_dir', dest='target_dir', help="Directory containing all the ", required=True)
parser.add_argument('-l', '--lines', dest='lines_to_process', help="Space-separated line_ids to exclusivley process", nargs='*', required=False, default=False)

args = parser.parse_args()

# Jst for testing. Work out a way to add specific lines to the analysis
# lines_to_run = ['fgf9', 'nras']

# In case there are any '~' in the paths
resolved_paths = [Path(x).expanduser() for x in [args.config, args.wt_dir, args.mut_dir, args.out_dir, args.target_dir]]


run(*resolved_paths, args.lines_to_process)
