#!/usr/bin/env python3

import os
from hol.xfer import read_hol_xfer_config, read_hol_xfer_auth, get_cloud_creds, \
    cleanup_oldest, get_free_space_bytes
from hol.ovf import BYTES_PER_GB
import logging

logging.basicConfig(level=logging.DEBUG)


def perform_vcd_export(cloud_host,
                       cloud_org,
                       cloud_catalog,
                       vapp_template_name,
                       repository,
                       credentials,
                       machine_output):

    if not os.path.isdir(repository):
        logging.error(f"Failed to locate repository at {repository}")
        exit(1)

    user_name, vcd_password = get_cloud_creds(
        credentials, cloud_host, cloud_org)

    media_type = 'vappTemplate'
    ovf_file_name = f'{vapp_template_name}.ovf'
    full_file_target = os.path.join(
        repository, vapp_template_name, ovf_file_name)
    # TODO: I think the "&vdc={cloud_ovdc}" portion of the ovftool url is optional... check that!
    cloud_source = f"'vcloud://{user_name}:{vcd_password}@{cloud_host}:443/?org={cloud_org}" \
                   f"&catalog={cloud_catalog}&{media_type}={vapp_template_name}'"
    options = '--X:skipContentLength --allowExtraConfig --X:vCloudTimeout=600 --X:connectionRetryCount=10'
    if machine_output:
        options = f'--machineOutput {options}'
    cmd = f'{ovftool_path} {options} {cloud_source} {full_file_target} '
    os.system(cmd)
    # ovftool still has a bug that it generates NAME/NAME/NAME.ovf when you provide NAME/NAME.ovf as the destination
    bad_source = os.path.join(
        repository, vapp_template_name, vapp_template_name)
    if os.path.exists(bad_source):
        print("working around OVFTOOL bug...")
        bad_source_files = os.path.join(bad_source, '*.*')
        good_source = os.path.join(repository, vapp_template_name)
        os.system(f'mv {bad_source_files} {good_source} && rmdir {bad_source}')


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--cloud_host", required=True,
                        dest="cloud_host",
                        help="the hostname of the cloud")
    parser.add_argument("--cloud_org", required=True,
                        dest="cloud_org",
                        help="the org name within the cloudhost")
    parser.add_argument("--cloud_catalog", required=True,
                        dest="cloud_catalog",
                        help="name of VCD catalog containing vApp templates")
    parser.add_argument("--vapp_template_name", required=True,
                        dest="vapp_template_name",
                        help="name of the vApp template (OVF base name)")
    parser.add_argument("--repository", required=False,
                        dest="repository", default='/hol/lib',
                        help="path to the local repository")
    parser.add_argument("--cleanup_pattern", required=False,
                        dest="cleanup_pattern", default='HOL-',
                        help='pattern used to identify "cleanup-able" items')
    parser.add_argument("--config", required=False, default='config.yaml',
                        dest="yaml_config_path",
                        help='path to the config file (YAML)')
    parser.add_argument("--machine_output", required=False, action="store_true",
                        dest="machine_output", default=False,
                        help="use ovftool machineOutput option")
    args = parser.parse_args()

    # Read the configuration / environment settings
    config = read_hol_xfer_config(args.yaml_config_path)
    ovftool_path = config['Tools']['ovftool']
    # this one is fatal
    if not os.path.exists(ovftool_path):
        logging.error(f"Failed to locate ovftool at {ovftool_path}")
        exit(1)

    creds = read_hol_xfer_auth(config['Tools']['credentials'])
    min_free_gb = config['Library']['min_free_gb']
    if os.path.isdir(args.repository):
        cleanup_oldest(args.repository, args.cleanup_pattern,
                       min_free_gb, really_delete=False)
        # we should have "enough" (estimated?) free space and can proceed with the export
        requested_free_bytes = min_free_gb * BYTES_PER_GB
        requested_free_gb = requested_free_bytes / BYTES_PER_GB
        available_bytes = get_free_space_bytes(args.repository)
        available_gb = available_bytes / BYTES_PER_GB
        if available_gb > requested_free_gb:
            perform_vcd_export(args.cloud_host,
                               args.cloud_org,
                               args.cloud_catalog,
                               args.vapp_template_name,
                               args.repository,
                               creds,
                               args.machine_output)
        else:
            logging.error(f'Unable to begin export: inadequate space able to be freed: '
                          f'{requested_free_gb} GB requested, {available_gb} GB available after cleanup'
                          f'using "{args.cleanup_pattern}"')
    else:
        logging.error(f'Repository "{args.repository}" is not a directory!')
