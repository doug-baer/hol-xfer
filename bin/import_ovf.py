#!/usr/bin/env python3

import os
from hol.xfer import read_hol_xfer_config, read_hol_xfer_auth, get_cloud_creds
import logging

logging.basicConfig(level=logging.INFO)


def perform_vcd_import(cloud_host,
                       cloud_org,
                       cloud_catalog,
                       vapp_template_name,
                       repository,
                       credentials,
                       machine_output):

    if not os.path.exists(ovftool_path):
        print(f"Failed to locate ovftool at {ovftool_path}")
        exit(1)

    if not os.path.isdir(repository):
        print(f"Failed to locate repository at {repository}")
        exit(1)

    user_name, vcd_password = get_cloud_creds(
        credentials, cloud_host, cloud_org)

    media_type = 'vappTemplate'
    ovf_file_name = f'{vapp_template_name}.ovf'
    full_source = os.path.join(repository, vapp_template_name, ovf_file_name)
    # TODO: I think the "&vdc={cloud_ovdc}" portion of the ovftool url is optional... check that!
    target = f"'vcloud://{user_name}:{vcd_password}@{cloud_host}:443/?org={cloud_org}" \
             f"&catalog={cloud_catalog}&{media_type}={vapp_template_name}'"
    options = '--X:skipContentLength --allowExtraConfig --X:vCloudTimeout=600 --X:connectionRetryCount=10'
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
    parser.add_argument("--vapp_template_name", required=True,
                        dest="vapp_template_name",
                        help="name of the vApp template (OVF base name)")
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
                       args.vapp_template_name,
                       args.repository,
                       creds,
                       args.machine_output)
