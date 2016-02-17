#!/usr/bin/env python

import yaml
from os.path import relpath, join, dirname, basename
import sys
import os
import numpy as np
import csv

from _phenotype_statistics import DeformationStats, GlcmStats, IntensityStats, JacobianStats, OrganVolumeStats
from _stats import TTest, LinearModelR

# Hack. Relative package imports won't work if this module is run as __main__
sys.path.insert(0, join(os.path.dirname(__file__), '..'))
import common
import gc
import logging
import subprocess as sub


# Map the stats name and analysis types specified in stats.yaml to the correct class
STATS_METHODS = {
    'LM': LinearModelR,
    'ttest': TTest
}

ANALYSIS_TYPES = {
    'intensity': IntensityStats,
    'deformations': DeformationStats,
    'jacobians': JacobianStats,
    'glcm': GlcmStats,
    'organ_volumes': OrganVolumeStats
}

DEFAULT_FORMULA = 'data ~ genotype'
DEFAULT_HAEDER = ['volume_id', 'genotype']


class LamaStats(object):
    """
    Takes a stats.yaml config file and creates appropriate PhenotypeStatitics subclasses based on which analysis is to
    be performed
    """
    def __init__(self, config_path):
        self.config_dir = dirname(config_path)
        self.config_path = config_path
        self.config = self.get_config(config_path)
        self.setup_logging()
        self.mask_path = self.make_path(self.config['fixed_mask'])
        self.r_installed = self.check_for_r_installation()
        self.run_stats_from_config()

    @staticmethod
    def check_for_r_installation():

        installed = True

        FNULL = open(os.devnull, 'w')
        try:
            sub.call(['Rscript'], stdout=FNULL, stderr=sub.STDOUT)
        except sub.CalledProcessError:
            installed = False
        except OSError:
            installed = False
            logging.warn('R or Rscript not installed. Will not be able to use linear model')
        return installed

    def setup_logging(self):
        """
        If there is a log file specified in the config, use that path. Otherwise log to the stats folder
        """
        logpath = self.config.get('log')
        if not logpath:
            logpath = join(self.config_dir, 'stats.log')

        common.init_logging(logpath)
        logging.info('##### Stats started #####')
        logging.info(common.git_log())

    def make_path(self, path):
        """
        All paths are relative to the config file dir.
        Return relative paths to the config dir
        """
        return join(self.config_dir, path)

    def get_config(self, config_path):
        """
        Get the config and check for paths
        """
        with open(config_path) as fh:
            config = yaml.load(fh)
        try:
            data = config['data']
        except KeyError:
            raise Exception("stats config file need a 'data' entry")

        return config

    def get_groups(self, wt_subset, mut_subset):
        """
        Combine group info from both the wildtype and mutants. Write out a combined groups csv file.
        If wt file basenames not specified in wt_subset_file, remove them

        Returns
        -------
        None: if no file can be found
        Dict: if file can be found {volume_id: {groupname: grouptype, ...}...}
        """
        wt_groups = mut_groups = None

        wt_g = self.config.get('wt_groups')
        mut_g = self.config.get('mut_groups')
        if all((wt_g, mut_g)):

            wt_groups = join(self.config_dir, self.config['wt_groups'])
            mut_groups = join(self.config_dir, self.config['mut_groups'])

            if not all((os.path.isfile(wt_groups), os.path.isfile(mut_groups))):
                wt_groups = mut_groups = None
                logging.warn("Can't find the wild type groups file, using default")

        combined_groups_file = os.path.abspath(join(self.config_dir, 'combined_groups.csv'))

        if all((wt_groups, mut_groups)):  # Generate the combined groups file from the given wt and mut files
            with open(wt_groups, 'r') as wr, open(mut_groups, 'r') as mr, open(combined_groups_file, 'w') as cw:
                wt_reader = csv.reader(wr)
                first = True
                for row in wt_reader:
                    if first:
                        header = row
                        first = False
                        cw.write(','.join(header) + '\n')
                    else:
                        cw.write(','.join(row) + '\n')

                reader_mut = csv.reader(mr)
                first = True
                for row in reader_mut:
                    if first:
                        header_mut = row
                        if header != header_mut:
                            logging.warn("The header for mutant and wildtype group files is not identical. Creating default groups file")
                            return None
                        first = False
                    else:
                        cw.write(','.join(row) + '\n')
        else:  # Create default combined groups file. This is needed for running RScript for the linear model
            # Find an extry in stats.yaml to find data name
            for s in ANALYSIS_TYPES:
                if s in self.config['data']:
                    wt_data_dir = join(self.config_dir, self.config['data'][s]['wt'])
                    mut_data_dir = join(self.config_dir, self.config['data'][s]['mut'])
                    wt_file_list = common.GetFilePaths(wt_data_dir)
                    mut_file_list = common.GetFilePaths(mut_data_dir)
                    if not all((wt_file_list, mut_file_list)):
                        logging.error('Cannot find data files for {}. Check the paths in stats.yaml'.format(s))
                        continue
                    wt_basenames = [basename(x) for x in common.GetFilePaths(wt_data_dir)]
                    mut_basenames = [basename(x) for x in common.GetFilePaths(mut_data_dir)]
                    with open(combined_groups_file, 'w') as cw:
                        cw.write(','.join(DEFAULT_HAEDER) + '\n')
                        for volname in wt_basenames:
                            if wt_subset:
                                if os.path.splitext(volname)[0] in wt_subset:
                                    cw.write('{},{}\n'.format(volname, 'wildtype'))
                            else:
                                cw.write('{},{}\n'.format(volname, 'wildtype'))
                        for volname in mut_basenames:
                            if mut_subset:
                                if os.path.splitext(volname)[0] in mut_subset:
                                    cw.write('{},{}\n'.format(volname, 'mutant'))
                            else:
                                cw.write('{},{}\n'.format(volname, 'mutant'))
                    break

        return combined_groups_file

    def get_formulas(self):
        """
        Extract the linear/mixed model from the stasts config file. Just extract the independent varibale names for now

        Returns
        -------
        str: the independent variables/fixed effects
            or
        None: if no formulas can be found
        """
        parsed_formulas = []
        formulas = self.config.get('formulas')
        if not formulas:
            return None
        else:
            for formula_string in formulas:
                formula_elements = formula_string.split()[0::2][1:]  # extract all the effects, miss out the dependent variable
                parsed_formulas.append(','.join(formula_elements))
            return parsed_formulas

    def get_subset_list(self, subset_file):
        """
        Trim the files found in the wildtype input directory to thise in the optional subset list file
        """
        wt_vol_ids_to_use = []
        with open(subset_file, 'r') as reader:
            for line in reader:
                vol_name = line.strip()
                wt_vol_ids_to_use.append(vol_name)
        return wt_vol_ids_to_use

    def get_subset_ids(self):
        """
        Get the subset list of vol ids to do stats with

        Returns
        -------
        tuple
            None if no subset file specified
            list of ids
        """
        wt_subset_file = self.config.get('wt_subset_file')
        mut_subset_file = self.config.get('mut_subset_file')
        wt_subset_ids = mut_subset_ids = None
        if wt_subset_file:
            wt_subset_file = join(self.config_dir, wt_subset_file)
            wt_subset_ids = self.get_subset_list(wt_subset_file)
            if len(wt_subset_ids) < 1:
                wt_subset_ids = None
        if mut_subset_file:
            mut_subset_file = join(self.config_dir, mut_subset_file)
            mut_subset_ids = self.get_subset_list(mut_subset_file)
            if len(mut_subset_ids) < 1:
                mut_subset_ids = None

        return wt_subset_ids, mut_subset_ids


    def run_stats_from_config(self):
        """
        Build the required stats classes for each data type
        """

        wt_subset_ids, mut_subset_ids = self.get_subset_ids()

        mask = self.config.get('fixed_mask')
        if not mask:
            logging.warn('No mask specified in stats config file. Stats will take longer, and FDR correction might be too strict')
        fixed_mask = self.make_path(self.config.get('fixed_mask'))
        if not os.path.isfile(fixed_mask):
            logging.warn("Can't find mask {}. Stats will take longer, and FDR correction might be too strict".format(fixed_mask))
            fixed_mask = None

        voxel_size = self.config.get('voxel_size')
        if not voxel_size:
            voxel_size = 28.0
            logging.warn("Voxel size not set in config. Using a default of 28")
        voxel_size = float(voxel_size)

        groups = self.get_groups(wt_subset_ids, mut_subset_ids)
        formulas = self.get_formulas()
        project_name = self.config.get('project_name')
        if not project_name:
            project_name = '_'
        do_n1 = self.config.get('n1')

        mask_array = common.img_path_to_array(fixed_mask)
        mask_array_flat = mask_array.ravel().astype(np.bool)

        invert_config = self.config.get('invert_config_file')
        invert_config_path = self.make_path(invert_config)

        # loop over the types of data and do the required stats analysis
        for analysis_name, analysis_config in self.config['data'].iteritems():
            stats_tests = analysis_config['tests']
            mut_data_dir = self.make_path(analysis_config['mut'])
            wt_data_dir = self.make_path(analysis_config['wt'])
            outdir = join(self.config_dir, analysis_name)
            gc.collect()

            logging.info('#### doing {} stats ####'.format(analysis_name))
            stats_obj = ANALYSIS_TYPES[analysis_name](outdir, wt_data_dir, mut_data_dir, project_name, mask_array_flat,
                                                      groups, formulas, do_n1, voxel_size, wt_subset_ids, mut_subset_ids)
            for test in stats_tests:
                if test == 'LM' and not self.r_installed:
                    logging.warn("Could not do linear model test for {}. Do you need to install R?".format(analysis_name))
                    continue
                stats_obj.run(STATS_METHODS[test], analysis_name)
                if invert_config:
                    stats_obj.invert(invert_config_path)
            del stats_obj
            #
            # if analysis_name == 'glcm':
            #     logging.info('#### doing GLCM texture stats ####')
            #     glcm_feature_types = analysis_config.get('glcm_feature_types')
            #     if not glcm_feature_types:
            #         logging.warn("'glcm_feature_types' not specified in stats config file")
            #         continue
            #     for feature_type in glcm_feature_types:
            #         glcm_out_dir = join(outdir, feature_type)
            #         wt_glcm_input_dir = join(wt_data_dir, feature_type)
            #         mut_glcm_input_dir = join(mut_data_dir, feature_type)
            #         glcm_stats = GlcmStats(glcm_out_dir, wt_glcm_input_dir, mut_glcm_input_dir, project_name, mask_array, groups, formulas, do_n1, voxel_size)
            #         for test in stats_tests:
            #             if test == 'lmR' and not self.r_installed:
            #                 logging.warn("Could not do linear model test for {}. Do you need to install R?".format(analysis_name))
            #                 continue
            #             glcm_stats.run(STATS_METHODS[test], analysis_name)
            #         del glcm_stats

    def run_stats_method(self):
        pass

if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser("Stats component of the phenotype detection pipeline")
    parser.add_argument('-c', '--config', dest='config', help='yaml config file contanign stats info', required=True)
    args = parser.parse_args()
    LamaStats(args.config)
