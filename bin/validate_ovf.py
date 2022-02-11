#!/usr/bin/env python3
import os
from hol.ovf import validate_the_ovf
import logging

logging.basicConfig(level=logging.INFO)


def perform_ovf_validation(vapp_template_name, repository):
    ovf_file_name = f'{vapp_template_name}.ovf'
    full_file_target = os.path.join(
        repository, vapp_template_name, ovf_file_name)
    if os.path.isfile(full_file_target):
        if validate_the_ovf(full_file_target, verbose=True):
            print('SUCCESS')
            return 0
        else:
            logging.error(
                'missing or incorrectly-sized component file(s)')
    logging.error(f'unable to find OVF file: {full_file_target}')
    print('FAIL')
    return 99


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--vapp_template_name", required=True,
                        dest="vapp_template_name",
                        help="name of the vApp template (OVF base name)")
    parser.add_argument("--repository", required=False,
                        dest="repository", default='/hol/lib',
                        help="path to the local repository")
    args = parser.parse_args()

    ret = perform_ovf_validation(
        args.vapp_template_name,
        args.repository)
    exit(ret)
