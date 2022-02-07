#!/usr/bin/env python3

# NOTE: requires rsync, lftp

import os
import sys
import time
from hol.xfer import read_hol_xfer_config
import logging

logging.basicConfig(level=logging.DEBUG)

dry_run = '--dry-run'
no_lftp_ok = True


def check_requirements(configuration):
    try:
        rsync_path = configuration['Tools']['rsync']
        lftp_path = configuration['Tools']['lftp']
        if os.path.exists(rsync_path) and (os.path.exists(lftp_path) or no_lftp_ok):
            return True
        else:
            logging.error(
                f"Failed to locate rsync or lftp at specified locations.")
            return False
    except KeyError as e:
        logging.error(f'Prerequisites not met in config file: {e}')
        return False


def pull_and_verify(configuration, vapp_template_name, repository,
                    source_catalog, source_path):
    rsync_path = configuration['Tools']['rsync']
    lftp_path = configuration['Tools']['lftp']
    ssh_user = configuration['Infrastructure']['ssh_username']
    parallel_segments = configuration['Infrastructure']['parallel_segments']
    parallel_files = configuration['Infrastructure']['parallel_files']

    source_template_path = os.path.join(source_path, vapp_template_name)

    # Any preflight checks needed?

    transfer_start = time.time()
    # run the lftp -- uses key-based SSH (passwords not supported)
    fast_download_command = f'{lftp_path} -c "mirror --use-pget-n={parallel_segments} ' \
                            f'--no-perms --parallel={parallel_files} --delete-first {dry_run} ' \
                            f'sftp://{ssh_user}:xxx@{source_catalog}:{source_template_path} ' \
                            f'${repository}/"'
    logging.info(f'LFTP command: {fast_download_command}')
    # Call the download
    # TODO: what is the best way to call this?
    logging.debug('NOT ACTUALLY RUNNING COMMAND YET')
    # os.system(fast_download_command)
    # WAIT
    transfer_end = time.time() - transfer_start

    # run the rsync
    rsync_start = time.time()
    # -ItvPrh short switches.... expanded here for clarity (except removing the --partial aspect of -P)
    verify_command = f'{rsync_path} --times --ignore-times --recursive --progress --human-readable ' \
                     f'{ssh_user}@{source_catalog}:{source_template_path}/ ' \
                     f'{repository}/{vapp_template_name}/"'
    logging.info(f'RSYNC command: {verify_command}')
    # TODO: what is the best way to call this?
    logging.debug('NOT ACTUALLY RUNNING COMMAND YET')
    # os.system(fast_download_command)
    # WAIT
    rsync_end = time.time() - rsync_start

    logging.info(f'Copy complete, {str(round(transfer_end,2))} seconds to copy and '
                 f'{str(round(rsync_end,2))} to verify the copy.')


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--vapp_template_name", required=True,
                        dest="vapp_template_name",
                        help="name of the vApp template (OVF base name)")
    parser.add_argument("--repository", required=False,
                        dest="repository", default='/hol/lib',
                        help="path to the local repository")
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
    if check_requirements(config):
        pull_and_verify(
            config,
            args.vapp_template_name,
            args.repository,
            args.source_catalog,
            args.source_path)
    else:
        exit(99)
