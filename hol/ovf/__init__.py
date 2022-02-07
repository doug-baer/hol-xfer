import xml.etree.ElementTree as ET
import math
import os
from hashlib import sha256
import re

BYTES_PER_MB = 2 ** 20
BYTES_PER_GB = 2 ** 30
BYTES_PER_TB = 2 ** 40
EZT_BUG_TRIGGER_PERCENTAGE = 60


def get_sha256_hash(file_path):
    sha256_hash = sha256()
    block_size = 4096
    if os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(block_size), b""):
                sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()


def register_all_namespaces(filename):
    """
    read an XML file and register all found namespaces with xml.etree.ElementTree
    so they are preserved during XML parsing and export. This should be default behavior, IMO.
    :param filename: path to the XML file
    :return: the namespaces that can be passed to ElementTree commands that take the namespaces parameter
    """
    namespaces = dict(
        [node for _, node in ET.iterparse(filename, events=['start-ns'])])
    for ns in namespaces:
        ET.register_namespace(ns, namespaces[ns])
    return namespaces


def validate_the_ovf(ovf_file, verbose=False):
    """
    Ensure that the files listed in the OVF are present on disk and are of the indicated size
    :param ovf_file: full path to the OVF file
    :param verbose: boolean - verbose output?
    :return: boolean - is the OVF OK?
    """
    all_good = True
    parent_dir = os.path.dirname(ovf_file)
    # the_files = os.listdir(parent_dir)
    namespaces = register_all_namespaces(ovf_file)
    tree = ET.parse(ovf_file)
    root = tree.getroot()
    # TODO: get the disk files and their expected sizes
    disks = {}
    for files in root.findall('ovf:References', namespaces=namespaces):
        for f in files.findall('ovf:File', namespaces=namespaces):
            if 'file' in f.get('{http://schemas.dmtf.org/ovf/envelope/1}id'):
                disks[f.get('{http://schemas.dmtf.org/ovf/envelope/1}href')] = \
                    f.get('{http://schemas.dmtf.org/ovf/envelope/1}size')
    for disk_name in disks.keys():
        try:
            found_size = os.path.getsize(os.path.join(parent_dir, disk_name))
        except FileNotFoundError:
            found_size = 'NOT_FOUND'
            all_good = False
        except PermissionError:
            found_size = 'UNABLE_TO_READ'
            all_good = False
        finally:
            if verbose:
                print(
                    f"Expected Size: {disks[disk_name]}, found Size: {found_size}")
    return all_good


def update_the_manifest(ovf_file, manifest_file=None):
    """
    Update the SHA256 sum for the OVF file in the MF file
    :param ovf_file: full path to the OVF
    :param manifest_file: full path to the MF
    :return: None
    """
    if os.path.isfile(ovf_file):
        new_hash = get_sha256_hash(file_path=ovf_file)
        ovf_file_name = os.path.basename(ovf_file)
        if manifest_file is None:
            manifest_file = ovf_file.replace('.ovf', '.mf')
        if os.path.isfile(manifest_file):
            text_pattern = f'SHA256\({ovf_file_name}\)\= .*'
            replacement = f'SHA256({ovf_file_name})= {new_hash}'
            with open(manifest_file, 'r+') as f:
                text = f.read()
                text = re.sub(re.compile(text_pattern), replacement, text)
                f.seek(0)
                f.write(text)
                f.truncate()


def scrub_the_ovf(ovf_file, backup_file=None):
    """
    perform various 'cleanup' operations on an OVF file
    :param ovf_file: full path to OVF file
    :param backup_file: full path to backup file (default replaces ".ovf" with ".ovf.backup")
    :return:
    """
    fixed_network_name = False
    network_names = {'none': 'none'}

    if backup_file is None:
        backup_file_path = ovf_file.replace('.ovf', '.ovf.backup')
    else:
        backup_file_path = backup_file

    namespaces = register_all_namespaces(ovf_file)
    tree = ET.parse(ovf_file)
    root = tree.getroot()

    # create the backup
    tree.write(backup_file_path,
               encoding='utf-8',
               xml_declaration=True,
               method='xml')

    # No CustomizeOnInstantiate!
    print(f'=== CustomizeOnInstantiate ===')
    for elem in root:
        for sub in elem.findall('vcloud:CustomizeOnInstantiate', namespaces=namespaces):
            if sub.text != 'false':
                print(
                    f'CustomizeOnInstantiate... Current: {sub.tag} => {sub.text}')
                sub.text = 'false'
                set_no_customize = True
            else:
                print('OK')

    # I know we're going through this repeatedly, but it is more modular this way

    # Passwords
    print(f'\n=== Passwords ===')
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name}')
            for prod_sec in vs.findall('ovf:ProductSection', namespaces=namespaces):
                for prop in prod_sec.findall('ovf:Property', namespaces=namespaces):
                    if prop.get('{http://schemas.dmtf.org/ovf/envelope/1}password') == 'true' \
                            and prop.get('{http://schemas.dmtf.org/ovf/envelope/1}value') != '':
                        # TODO: deal with 'ovf:qualifiers="MinLen(##)"' ?
                        print(
                            f"\tSetting password in ProductSection for "
                            f"{prop.get('{http://schemas.dmtf.org/ovf/envelope/1}key')}")
                        prop.set(
                            '{http://schemas.dmtf.org/ovf/envelope/1}value', 'VMware1!VMware1!')
                        set_ovf_password = True

    # GuestInfo
    print(f'\n=== GuestInfo ===')
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name} - GuestInfo')
            for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                if vhs.get('{http://schemas.dmtf.org/ovf/envelope/1}transport') != 'com.vmware.guestInfo':
                    vhs.set(
                        '{http://schemas.dmtf.org/ovf/envelope/1}transport', 'com.vmware.guestInfo')
                    print("\tSetting OVF transport")
                    set_ovf_transport = True

    print(f'\n=== Network isolation and vApp Network Name ===')
    # fixing the network name is a giant pain!
    for ncs in root.findall('vcloud:NetworkConfigSection', namespaces=namespaces):
        for net_cfg in ncs.findall('vcloud:NetworkConfig', namespaces=namespaces):
            net_name = net_cfg.get('networkName')
            if net_name != 'none':
                print(f'{net_name}')
                for net_configuration in net_cfg.findall('vcloud:Configuration', namespaces=namespaces):
                    for fence_mode in net_configuration.findall('vcloud:FenceMode', namespaces=namespaces):
                        if fence_mode.text != 'isolated':
                            print('\tSetting isolated mode')
                            fence_mode.text = 'isolated'
                            set_fence_mode = True
                    # Unwire the pod
                    for parent_network in net_configuration.findall('vcloud:ParentNetwork', namespaces=namespaces):
                        print('\tRemoving parent network attachment')
                        net_configuration.remove(parent_network)
                        unwired_the_pod = True
                    for features in net_configuration.findall('vcloud:Features', namespaces=namespaces):
                        for nat_service_feature in features.findall('vcloud:NatService', namespaces=namespaces):
                            print('\tRemoving configured NAT rules')
                            features.remove(nat_service_feature)
                            removed_stuck_nat_rules = True
                # clean up the VCD netName bug by removing duplicate "vAppNet-" parts
                new_net_name = '-'.join(list(dict.fromkeys((net_name.split('-')))))
                if net_name != new_net_name:
                    print(f"\tfixing network name: {new_net_name}")
                    net_cfg.set('networkName', new_net_name)
                    for net_section in root.findall('ovf:NetworkSection', namespaces=namespaces):
                        for network in net_section.findall('ovf:Network', namespaces=namespaces):
                            if network.get('{http://schemas.dmtf.org/ovf/envelope/1}name') != 'none':
                                network.set(
                                    '{http://schemas.dmtf.org/ovf/envelope/1}name', new_net_name)
                    fixed_network_name = True
                network_names[net_name] = new_net_name

    print(f'\n=== Network Connections ===')
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name}')
            for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                for item in vhs.findall('ovf:Item', namespaces=namespaces):
                    for connection in item.findall('rasd:Connection', namespaces=namespaces):
                        if connection.get('{http://www.vmware.com/vcloud/v1.5}ipAddressingMode') == 'POOL':
                            connection.set(
                                '{http://www.vmware.com/vcloud/v1.5}ipAddressingMode', 'DHCP')
                        print("\tSetting network connection to DHCP")
                        set_connection_to_dhcp = True
                        old_net_name = connection.text
                        if fixed_network_name:
                            connection.text = network_names[connection.text]
                    # if fixed_network_name and old_net_name != 'none':
                    # actually need to do this because of VCD's issue with quotation marks in the Description
                    for description in item.findall('rasd:Description', namespaces=namespaces):
                        if "ethernet adapter" in description.text:
                            if old_net_name != 'none' and fixed_network_name:
                                print("\tupdating description")
                                description.text = description.text.replace(
                                    old_net_name, network_names[old_net_name])
                        # handle the STUPID quoting that VCD adds (I refuse to replace with '&quot;')
                        description.text = description.text.replace('"', '')
    if fixed_network_name:
        print(f'\n=== vcloud:NetworkConnectionSection ===')
        for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
            for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
                vm_name = vs.attrib.get(
                    '{http://schemas.dmtf.org/ovf/envelope/1}id')
                print(f'=== {vm_name} - Network Name ===')
                for ncs in vs.findall('vcloud:NetworkConnectionSection', namespaces=namespaces):
                    for net_connection in ncs.findall('vcloud:NetworkConnection', namespaces=namespaces):
                        if net_connection.get('network') != 'none':
                            net_connection.set(
                                'network', network_names[net_connection.get('network')])
                            print(
                                f"\tUpdating network name to {net_connection.get('network')}")

    print(f'\n=== Hard Disks ===')
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name}')
            for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                for item in vhs.findall('ovf:Item', namespaces=namespaces):
                    for resource in item.findall('rasd:Description', namespaces=namespaces):
                        if resource.text.upper() == 'HARD DISK':
                            cfg = item.find(
                                'vmw:Config', namespaces=namespaces)
                            if cfg.get('{http://www.vmware.com/schema/ovf}key') != 'backing.writeThrough':
                                cfg.set(
                                    '{http://www.vmware.com/schema/ovf}key', 'backing.writeThrough')
                                cfg.set(
                                    '{http://www.vmware.com/schema/ovf}value', 'false')
                                print("\tSetting hard disks to writeThrough")
                                set_disk_to_persistent = True

    # If disk capacities are present ... what do we do if they're not? The bug is still there and WILL cause problems.
    disks = {}
    for files in root.findall('ovf:References', namespaces=namespaces):
        for f in files.findall('ovf:File', namespaces=namespaces):
            if 'file' in f.get('{http://schemas.dmtf.org/ovf/envelope/1}id'):
                disks[f.get('{http://schemas.dmtf.org/ovf/envelope/1}id')] = f.get(
                    '{http://schemas.dmtf.org/ovf/envelope/1}size')
    for disk in root.findall('ovf:DiskSection', namespaces=namespaces):
        for d in disk.findall('ovf:Disk', namespaces=namespaces):
            specified_capacity = int(
                d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacity'))
            populated_size_bytes = int(
                d.get('{http://schemas.dmtf.org/ovf/envelope/1}populatedSize'))
            file_size_bytes = int(
                disks[d.get('{http://schemas.dmtf.org/ovf/envelope/1}fileRef')])

            # check for KB 2094271 rounding errors (data on disk exceeds size of disk specified in OVF)
            if 'byte * 2^20' in d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacityAllocationUnits'):
                specified_capacity_bytes = int(
                    specified_capacity * BYTES_PER_MB)
                disk_size_difference = file_size_bytes - specified_capacity_bytes
                if disk_size_difference > 0:
                    increase_mb = math.ceil(
                        disk_size_difference / BYTES_PER_MB)
                    new_capacity_size_mb = specified_capacity + increase_mb
                    print(f'Disk is {disk_size_difference} bytes too small for contents, increasing from '
                          f'{specified_capacity} to {new_capacity_size_mb} MB')
                    d.set('{http://schemas.dmtf.org/ovf/envelope/1}capacity',
                          str(new_capacity_size_mb))
            elif 'byte * 2^30' in d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacityAllocationUnits'):
                # work around "60% full means EZT" issue
                specified_capacity_bytes = int(
                    specified_capacity * BYTES_PER_GB)
                new_size = math.ceil(
                    populated_size_bytes / (EZT_BUG_TRIGGER_PERCENTAGE/100) / BYTES_PER_GB)
                if new_size < 1:
                    print(
                        f"WARNING: MINIMALLY USED DISK!! {d.get('{http://schemas.dmtf.org/ovf/envelope/1}fileRef')}")
                    new_size = 1
                new_full_percent = 100 * populated_size_bytes / \
                    (new_size * BYTES_PER_GB)
                percent_full = 100 * populated_size_bytes / specified_capacity_bytes
                print(f'Populated data is {populated_size_bytes} / {specified_capacity_bytes} = '
                      f'{percent_full:.2f}% ')
                if percent_full > EZT_BUG_TRIGGER_PERCENTAGE:
                    print(f'Disk is too small for thin. Increased from {specified_capacity} '
                          f'to {new_size} GB ({new_full_percent:.2f}%) full')
                    d.set(
                        '{http://schemas.dmtf.org/ovf/envelope/1}capacity', str(new_size))

            elif 'byte * 2^40' in d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacityAllocationUnits'):
                specified_capacity_bytes = int(
                    specified_capacity * BYTES_PER_TB)
                # TODO: not sure what else to do here: future?
            else:
                print("ERROR: Unable to get disk size")
                specified_capacity_bytes = '0'

    tree.write(ovf_file,
               encoding='utf-8',
               xml_declaration=True,
               method='xml')
