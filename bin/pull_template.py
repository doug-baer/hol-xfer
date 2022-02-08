#!/usr/bin/env python3

# NOTE: requires rsync, lftp

import os
import time
from hol.xfer import read_hol_xfer_config
import logging
import subprocess

logging.basicConfig(level=logging.INFO)

dry_run = ''  # '--dry-run'


def check_requirements(configuration):
    try:
        rsync_path = configuration['Tools']['rsync']
        lftp_path = configuration['Tools']['lftp']
        if os.path.exists(rsync_path) and os.path.exists(lftp_path):
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
                            f'{repository}/"'
    logging.debug(f'LFTP command: {fast_download_command}')
    # Call the download
    # TODO: what is the best way to call this?  this one does not like subprocess.run()
    transfer_start = time.time()
    os.system(fast_download_command)
    transfer_end = time.time() - transfer_start
    logging.info("=== LFTP complete, running RSYNC to validate ===")
    # using subprocess.run here... is this "better" ?
    source = f'{ssh_user}@{source_catalog}:{source_template_path}/'
    target = f'{repository}/{vapp_template_name}/'
    verify_command_list = [rsync_path, '--times', '--ignore-times', '--recursive',
                           '--human-readable', '--stats', source, target]
    rsync_start = time.time()
    verify_result = subprocess.run(
        verify_command_list, capture_output=True, text=True)
    rsync_end = time.time() - rsync_start
    print(verify_result.stdout)

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
