import os
import yaml
import logging
import shutil
import requests
import base64
from pathlib import Path

BYTES_PER_MB = 1024 ** 2
BYTES_PER_GB = 1024 ** 3

logging.basicConfig(level=logging.DEBUG)


def read_hol_xfer_config(yaml_config_path: str):
    """
    Read the YAML configuration file and return as dictionary
    :param yaml_config_path: path to the YAML file containing the config options
    :return: dict
    """
    try:
        with open(yaml_config_path, mode='rt') as yaml_f:
            config_dict = yaml.safe_load(yaml_f)
        ovftool_path = config_dict['Tools']['ovftool']
        logging.debug(f'ovftool_path: {ovftool_path}')
        scripts_path = config_dict['Tools']['scripts']
        logging.debug(f'scripts_path: {scripts_path}')
        credentials_path = config_dict['Tools']['credentials']
        logging.debug(f'credentials_path: {credentials_path}')
        default_lib_path = config_dict['Library']['path']
        logging.debug(f'default_lib_path: {default_lib_path}')
        min_free_gb = config_dict['Library']['min_free_gb']
        logging.debug(f'min_free_gb: {min_free_gb} GB')
    except KeyError as e:
        logging.error(f'Expected item not found in config: {e}')
    except FileNotFoundError:
        logging.error(f'Missing configuration file: {yaml_config_path}')
    return config_dict


def read_hol_xfer_auth(credentials_path: str):
    """
    Read the YAML credentials file and return as dictionary
    :param credentials_path: path to the YAML file containing the auth information
    :return: dict
    """
    try:
        with open(credentials_path, mode='rt') as yaml_f:
            credentials_dict = yaml.safe_load(yaml_f)
            try:
                if credentials_dict['Default']['Type'] == 'API_TOKEN':
                    api_endpoint = credentials_dict['Default']['Endpoint']
                    logging.debug(f'api_endpoint: {api_endpoint}')
                    api_token = credentials_dict['Default']['Token']
                    logging.debug(f'api_token: {api_token}')
                else:
                    vcd_username = credentials_dict['Default']['Username']
                    logging.debug(f'vcd_username: {vcd_username}')
                    vcd_password = credentials_dict['Default']['Password']
                    logging.debug(f'vcd_password: {vcd_password}')
            except KeyError as e:
                logging.error(
                    f'Token or User/Password information not configured: {e}')
                return []
    except FileNotFoundError:
        logging.error(f'Unable to find credentials file: {credentials_path}.')
        return []
    return credentials_dict


def get_directory_size(directory: str):
    """
    returns space consumed by directory in bytes
    :param directory: full path to the directory you'd like the size of
    :return: int = amount of space consumed in BYTES
    """
    total_bytes = 0
    try:
        for elem in os.scandir(directory):
            total_bytes += os.path.getsize(elem)
    except NotADirectoryError:
        # if `directory` isn't a directory, just return the file size
        return os.path.getsize(directory)
    except PermissionError:
        # if we can't open the folder, return 0
        return 0
    return total_bytes


def get_free_space_bytes(directory: str):
    total, used, free = shutil.disk_usage(directory)
    return free


def cleanup_oldest(the_path: str, pattern: str, threshold_gb: int, really_delete=False):
    """
    using pattern and threshold_gb, free space on the_path by removing the oldest matching files/directories
    :param the_path: the full path to the directory to be cleaned up
    :param pattern: a substring that musty be contained in the top-level candidate items for cleanup
    :param threshold_gb: the minimum number of GB that should be free on the_path at function exit
    :param really_delete: REALLY perform the deletion? (there is no going back)
    :return:
    """
    total, used, free = shutil.disk_usage(the_path)
    free_gb = free / BYTES_PER_GB
    # list the directory, sorted by date (oldest creation date first)
    contents_by_created_date = sorted(
        Path(the_path).iterdir(), key=os.path.getmtime)

    for item in contents_by_created_date:
        if pattern in item.name and free_gb < threshold_gb:
            item_size = get_directory_size(item)
            item_size_gb = item_size / BYTES_PER_GB
            # TODO: should we ignore size 0 or attempt to remove it?
            try:
                if really_delete:
                    shutil.rmtree(item)
                else:
                    logging.info(f"not really removing {item}")
            except OSError as e:
                logging.error(f"BAD THINGS HAPPENED while removing {item}:")
                logging.error({e})
            else:
                free_gb += item_size_gb
                logging.info(
                    f'Free space after removing {item} of size {item_size_gb:.2f} = {free_gb:.2f}')
    # check it again!
    total, used, free = shutil.disk_usage(the_path)
    free_gb = free / BYTES_PER_GB
    if free_gb < threshold_gb:
        logging.warning(
            f'available free space ({free_gb:.2f} GB) is still less than threshold ({threshold_gb} GB)')


def fetch_credentials_from_hol_central(api_endpoint: str, vcd_instance: str, org: str, bearer_token: str):
    """
    (username, p) = fetch_credentials_from_hol_central(...)
    passwd = base64.b64decode(p).decode('utf-8')

    :param api_endpoint: url of the API endpoint (ends with /api/)
    :param vcd_instance: the cloud host's FQDN, e.g. 'vcore3-us04.oc.vmware.com'
    :param org: the cloud org, e.g. 'us04-3-hol-dev-d'
    :param bearer_token: the token used to grab the password
    :return: a tuple containing the username and base 64-encoded password
    """
    resource_name = vcd_instance.replace('.oc.vmware.com', '')
    resource_url = f"{api_endpoint}getCredentials?resourceName={resource_name}&resourceSubIdentifier={org}"
    try:
        response = requests.get(url=resource_url, headers={
                                'Authorization': 'Bearer ' + bearer_token})
        if response.status_code == 200:
            ret = response.json()
            return ret['received_credentials']['resourceUsername'], ret['received_credentials']['resourcePassword']
        else:
            return None, None
    except Exception as e:
        print(f'An Error occurred: {e}')
        return None, None


def get_cloud_creds(cred_dict, cloud_host, cloud_org):
    """
    pull the creds from the creds dictionary or the HOL central repo, depending on
    :param cred_dict: a dictionary from read_hol_xfer_auth
    :param cloud_host: the DNS name/IP of the VCD host
    :param cloud_org: the name of the org
    :return: user name, password for the VCD org
    """
    vcd_user_name = ''
    vcd_password = ''
    if cred_dict['Default']['Type'] != 'API_TOKEN':
        try:
            vcd_user_name = cred_dict['Default']['Username']
            vcd_password = cred_dict['Default']['Password']
        except KeyError:
            logging.error(f'unable to get credentials: user/pasword.')
            exit(1)
    else:
        try:
            endpoint = cred_dict['Default']['Endpoint']
            token = cred_dict['Default']['Token']
            (vcd_user_name, b64_password) = fetch_credentials_from_hol_central(api_endpoint=endpoint,
                                                                               vcd_instance=cloud_host,
                                                                               org=cloud_org,
                                                                               bearer_token=token)
            try:
                vcd_password = base64.b64decode(b64_password).decode('utf-8')
            except TypeError:
                logging.error(f"Failed to get credentials for {cloud_org}")
                exit(1)
        except KeyError as e:
            logging.error(f'unable to get credentials for {cloud_org}: {e}')
    return vcd_user_name, vcd_password
