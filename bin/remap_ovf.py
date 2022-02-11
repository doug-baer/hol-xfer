#!/usr/bin/env python3

import os
from hol.ovf import remap_ovf_for_rsync
from hol.xfer import read_hol_xfer_config
import logging
import shutil

logging.basicConfig(level=logging.INFO)


def obtain_new_ovf(template_name, local_ovf_path, catalog_host, catalog_user, remote_lib_path):
    return


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--vapp_template_name", required=True,
                        dest="vapp_template_name",
                        help="name of the vApp template (OVF base name)")
    parser.add_argument("--vapp_template_name_old", required=True,
                        dest="vapp_template_name_old",
                        help="name of the old/existing vApp template (OVF base name)")
    parser.add_argument("--repository", required=False,
                        dest="repository", default='/hol/lib',
                        help="path to the local repository")
    parser.add_argument("--seeds", required=False,
                        dest="seed_dir", default='/hol/seeds',
                        help="path to the local seeds (temp) directory on the same file system as the repository")
    parser.add_argument("--source_catalog", required=True,
                        dest="source_catalog",
                        help="name or IP of the source catalog node")
    parser.add_argument("--source_path", required=False,
                        dest="source_path", default='/hol/lib',
                        help="repository root path on source catalog node")
    parser.add_argument("--config", required=False, default='../config.yaml',
                        dest="yaml_config_path",
                        help='path to the config file (YAML)')
    args = parser.parse_args()

    # Read the configuration / environment settings
    config = read_hol_xfer_config(args.yaml_config_path)
    ssh_username = config['Infrastructure']['ssh_username']

    # root path sanity check (don't want to copy hundreds of GB across file systems)
    if os.path.split(args.repository)[0] != os.path.split(args.seed_dir)[0]:
        logging.error(
            f'Not efficient to have lib and seeds on different file systems!')
        exit(99)
    else:
        root_path = os.path.split(args.repository)[0]

    # the location of the "current" version
    old_ovf_dir = os.path.join(args.repository, args.vapp_template_name_old)
    old_ovf = os.path.join(old_ovf_dir, f'{args.vapp_template_name}.ovf')

    # the new version (we only have the OVF)
    new_ovf_dir = os.path.join(args.repository, args.vapp_template_name)
    new_ovf = os.path.join(new_ovf_dir, f'{args.vapp_template_name}.ovf')

    # ensure old_ovf exists and new_ovf does not
    if os.path.isfile(old_ovf) and not os.path.exists(new_ovf):
        # create the new_ovf_dir in repository
        try:
            os.makedirs(new_ovf_dir)
        except PermissionError as pe:
            logging.error(pe)
        else:
            # obtain the new OVF file (rsync from catalog, remote library to new_ovf_dir)
            if obtain_new_ovf(args.vapp_template_name, new_ovf_dir,
                              args.source_catalog, ssh_username, args.source_path):
                # TODO: check that the seed_dir exists before firing off the move?
                # move the old_ovf_dir into seed_dir to prep for remapping operation
                old_ovf_seed_dir = shutil.move(old_ovf_dir, args.seed_dir)
                old_ovf_seed = os.path.join(
                    old_ovf_seed_dir, f'{args.vapp_template_name_old}.ovf')
                remap_ovf_for_rsync(source_file=old_ovf_seed, target_file=new_ovf,
                                    lib_dir=args.repository, seed_dir=args.seed_dir)
            else:
                logging.error(
                    f'Unable to download new OVF for {args.vapp_template_name} from {args.source_catalog}')
