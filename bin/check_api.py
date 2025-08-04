#!/usr/bin/env python3
#
#  2025 August 3 - A simple check of the VCD API versions supported by the cloud
#

import os
from hol.xfer import read_hol_xfer_config, read_hol_xfer_auth, get_cloud_creds
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
import logging

logging.basicConfig(level=logging.INFO, force=True)


def perform_vcd_check(cloud_host, cloud_org, credentials):

    user_name, vcd_password = get_cloud_creds(
        credentials, cloud_host, cloud_org)

    # Create a client instance (using v37.0 API because pyvcloud doesn't know how to log out of a v38.0+ yet and I haven't patched it here)
    #api_version = "37.0"
    #client = Client(cloud_host, api_version=api_version, verify_ssl_certs=True)
    logging.info("Logging in")
    client = Client(cloud_host, verify_ssl_certs=True)
    client.set_highest_supported_version()
    client.set_credentials(BasicLoginCredentials(
        user=user_name, org=cloud_org, password=vcd_password))
    # Get the organization
    logging.info("Fetching Org...")
    org_resource = client.get_org()

    # Debugging a weird logout issue -- suspect it is related to long-running tasks like imports or exports where the session is not repeatedly renewed
    logging.info("logging out")
    result = client.logout()
    logging.info("Log out result: {result}")


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--cloud_host", required=True,
                        dest="cloud_host",
                        help="the hostname of the cloud")
    parser.add_argument("--cloud_org", required=True,
                        dest="cloud_org",
                        help="the org name within the cloudhost")
    parser.add_argument("--config", required=False, default='../config.yaml',
                        dest="yaml_config_path",
                        help='path to the config file (YAML)')
    args = parser.parse_args()

    # Read the configuration / environment settings
    config = read_hol_xfer_config(args.yaml_config_path)
    creds = read_hol_xfer_auth(config['Tools']['credentials'])

    perform_vcd_check(args.cloud_host,
                      args.cloud_org,
                      creds)
