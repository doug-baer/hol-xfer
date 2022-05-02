#!/usr/bin/env python3

# EXAMPLE: time_bubble.py --repository /hol/lib --vapp_template_name 2vm_blank --rtc_start_time 1702666800

import os
from hol.ovf import bubble_the_ovf, update_the_manifest, unbubble_the_ovf
from time import ctime

import logging

logging.basicConfig(level=logging.INFO)


def time_bubble_ovf(rtc_start_time, vapp_template_name, repository):
    ovf_file_name = f'{vapp_template_name}.ovf'
    full_file_target = os.path.join(
        repository, vapp_template_name, ovf_file_name)
    backup_file_path = full_file_target.replace('.ovf', '.ovf.backup')
    if os.path.isfile(full_file_target):
        try:
            if rtc_start_time > 0:
                bubble_the_ovf(
                    rtc_start_time=rtc_start_time,
                    ovf_file=full_file_target,
                    backup_file=backup_file_path)
            else:
                unbubble_the_ovf(
                    ovf_file=full_file_target,
                    backup_file=backup_file_path)
            update_the_manifest(ovf_file=full_file_target)
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
    parser.add_argument("--rtc_start_time", required=True,
                        dest="rtc_start_time", type=int,
                        help="epoch value for time bubble start")
    args = parser.parse_args()

    print(f'Bubble date/time: {ctime(args.rtc_start_time)}')
    time_bubble_ovf(args.rtc_start_time,
                    args.vapp_template_name, args.repository)
