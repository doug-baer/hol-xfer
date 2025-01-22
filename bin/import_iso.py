#!/usr/bin/env python3

import os
from hol.xfer import read_hol_xfer_config, read_hol_xfer_auth, get_cloud_creds
import logging

logging.basicConfig(level=logging.INFO)


def perform_vcd_import(cloud_host,
                       cloud_org,
                       cloud_catalog,
                       iso_name,
                       repository,
                       credentials,
                       machine_output):

    if not os.path.exists(ovftool_path):
        print(f"Failed to locate ovftool at {ovftool_path}")
        exit(1)

    if not os.path.isdir(repository):
        print(f"Failed to locate repository at {repository}")
        exit(1)

    iso_directory_in_repo = "ISO"
    iso_path = os.path.join(repository, iso_directory_in_repo)
    if not os.path.isdir(iso_path):
        print(f"Failed to locate ISO directory in repository at {iso_path}.")
        exit(1)

    user_name, vcd_password = get_cloud_creds(
        credentials, cloud_host, cloud_org)

    # this is the type for ISOs in the vcloud:// locator
    media_type = 'media'
    # the filename should have an ".iso" suffix
    iso_file_name = iso_name if iso_name.endswith(
        ".iso") else f"{iso_name}.iso"
    # the catalog item does not need an ".iso" suffix
    iso_catalog_item_name = iso_name if not iso_name.endswith(
        ".iso") else iso_name[:-4]

    full_source = os.path.join(
        repository, iso_directory_in_repo, iso_file_name)
    target = f"'vcloud://{user_name}:{vcd_password}@{cloud_host}:443/?org={cloud_org}" \
             f"&catalog={cloud_catalog}&{media_type}={iso_catalog_item_name}'"
    options = '--X:skipContentLength --X:vCloudTimeout=600 --X:connectionRetryCount=10'
    if machine_output:
        options = f'--machineOutput {options}'
    cmd = f'{ovftool_path} {options} {full_source} {target}'
    os.system(cmd)


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
    parser.add_argument("--iso_name", required=True,
                        dest="iso_name",
                        help="name of the ISO file")
    parser.add_argument("--repository", required=False,
                        dest="repository", default='/hol/lib',
                        help="path to the local repository")
    parser.add_argument("--config", required=False, default='../config.yaml',
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

    perform_vcd_import(args.cloud_host,
                       args.cloud_org,
                       args.cloud_catalog,
                       args.iso_name,
                       args.repository,
                       creds,
                       args.machine_output)
