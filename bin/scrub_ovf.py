#!/usr/bin/env python3

# EXAMPLE: scrub_ovf.py --repository /hol/lib --vapp_template_name 2vm_blank

import os
from hol.ovf import scrub_the_ovf
import logging

logging.basicConfig(level=logging.DEBUG)


def perform_ovf_scrubbing(vapp_template_name, repository):
    ovf_file_name = f'{vapp_template_name}.ovf'
    full_file_target = os.path.join(
        repository, vapp_template_name, ovf_file_name)
    backup_file_path = full_file_target.replace('.ovf', '.ovf.backup')
    if os.path.isfile(full_file_target):
        try:
            scrub_the_ovf(ovf_file=full_file_target,
                          backup_file=backup_file_path)
        except PermissionError as err:
            logging.error(f'unable to write backup file? {err}')
    else:
        logging.error(
            f'Unable to locate OVF file in library: {full_file_target}')


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

    perform_ovf_scrubbing(args.vapp_template_name, args.repository)
