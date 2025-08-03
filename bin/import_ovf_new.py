#!/usr/bin/env python3
#
#  2025 August 2 - Transition from OVFTOOL to pyvcloud for uploads (permits changing DSB_CHUNK_SIZE to work through public cloud limitations)
#

import os
from hol.xfer import read_hol_xfer_config, read_hol_xfer_auth, get_cloud_creds
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from hol.ovf import BYTES_PER_GB
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)

DSB_CHUNK_SIZE = 50 * 1024 * 1024

progress_bar = 0  # to show status of file downloads
prev_transfer_btyes = 0  # used to track for progress bar update across callback calls


# Define a progress reporter to track upload, since it take a while.
def progress_reporter(transferred, total):
    print("{:,} of {:,} bytes, {:.0%}".format(
        transferred, total, transferred / total))


def better_progress_reporter(transferred, total):

    # who sends sizes as strings???
    int_total = int(total)
    total_gb = int_total / BYTES_PER_GB

    global progress_bar
    global prev_transfer_btyes

    if not progress_bar:
        progress_bar = tqdm(total=int_total,
                            desc=f"Upload",
                            unit="B",
                            unit_scale=True
                            )
    else:
        # update by the amount transferred
        progress_bar.update(transferred - prev_transfer_btyes)
        # TODO: a way to fill the bar once it is all done... for small files?

    prev_transfer_btyes = transferred


# this is the new one
def perform_vcd_import(cloud_host, cloud_org, cloud_catalog, vapp_template_name, repository, credentials):
    user_name, vcd_password = get_cloud_creds(
        credentials, cloud_host, cloud_org)

    # Create a client instance (using v37.0 API because pyvcloud doesn't know how to log out of a v38.0+ yet and I haven't patched it here)
    #api_version = "37.0"
    #client = Client(cloud_host, api_version=api_version, verify_ssl_certs=True)
    client = Client(cloud_host, verify_ssl_certs=True)
    client.set_highest_supported_version()
    client.set_credentials(BasicLoginCredentials(
        user=user_name, org=cloud_org, password=vcd_password))
    # Get the organization
    print("Fetching Org...")
    org_resource = client.get_org()
    #org = Org(client, resource=org_resource)

    org = Org(client, resource=client.get_org_by_name(cloud_org))

    # Path to the OVF file
    ovf_file_path = os.path.join(
        repository, vapp_template_name, f'{vapp_template_name}.ovf')

    # Upload the OVF file
    try:
        org.upload_ovf(catalog_name=cloud_catalog, file_name=ovf_file_path,
                       item_name=vapp_template_name, chunk_size=DSB_CHUNK_SIZE,
                       callback=better_progress_reporter)
        print("OVF uploaded successfully.")
    except Exception as e:
        print(f"Error uploading OVF: {e}")

    # Clean up  -- this still needs to be updated to work properly (DB - Jul 25)
    client.logout()


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
    args = parser.parse_args()

    # Read the configuration / environment settings
    config = read_hol_xfer_config(args.yaml_config_path)
    creds = read_hol_xfer_auth(config['Tools']['credentials'])

    perform_vcd_import(args.cloud_host,
                       args.cloud_org,
                       args.cloud_catalog,
                       args.vapp_template_name,
                       args.repository,
                       creds)
