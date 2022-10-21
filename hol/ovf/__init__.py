import xml.etree.ElementTree as ET
import math
import os
from hashlib import sha256
import re
import logging
import shutil
from time import ctime
from prettytable import PrettyTable

BYTES_PER_MB = 2 ** 20
BYTES_PER_GB = 2 ** 30
BYTES_PER_TB = 2 ** 40
EZT_BUG_TRIGGER_PERCENTAGE = 60

logging.basicConfig(level=logging.INFO)


class OvfDisk:
    vm_name = ''
    file_name = ''
    disk_id = ''
    file_ref = ''
    vm_disk_id = ''


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
    tree.write(
        backup_file_path,
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
            # TODO: find out why this is not always present in the OVF!
            populated_size_bytes = 0
            populated_size = d.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}populatedSize')
            try:
                populated_size_bytes = int(populated_size)
            except TypeError:
                logging.warning(
                    'populatedSize is not present in this OVF. No EZT mitigations performed. ')
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
                    print(
                        f'Disk is {disk_size_difference} bytes too small for contents, increasing from '
                        f'{specified_capacity} to {new_capacity_size_mb} MB')
                    d.set(
                        '{http://schemas.dmtf.org/ovf/envelope/1}capacity',
                        str(new_capacity_size_mb))
            elif 'byte * 2^30' in d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacityAllocationUnits'):
                # work around "60% full means EZT" issue
                specified_capacity_bytes = int(
                    specified_capacity * BYTES_PER_GB)
                new_size = math.ceil(
                    populated_size_bytes / (EZT_BUG_TRIGGER_PERCENTAGE/100) / BYTES_PER_GB)
                if new_size < 1 and populated_size_bytes != 0:
                    print(
                        f"WARNING: MINIMALLY USED DISK!! {d.get('{http://schemas.dmtf.org/ovf/envelope/1}fileRef')}")
                    new_size = 1
                if new_size > 0:
                    new_full_percent = 100 * populated_size_bytes / \
                        (new_size * BYTES_PER_GB)
                else:
                    # not the cleanest, but do something when we have no data to act upon
                    new_full_percent = EZT_BUG_TRIGGER_PERCENTAGE + 10
                percent_full = 100 * populated_size_bytes / specified_capacity_bytes
                print(
                    f'Populated data is {populated_size_bytes} / {specified_capacity_bytes} = '
                    f'{percent_full:.2f}% ')
                if percent_full > EZT_BUG_TRIGGER_PERCENTAGE:
                    print(
                        f'Disk is too small for thin. Increased from {specified_capacity} '
                        f'to {new_size} GB ({new_full_percent:.2f}%) full')
                    d.set(
                        '{http://schemas.dmtf.org/ovf/envelope/1}capacity',
                        str(new_size))

            elif 'byte * 2^40' in d.get('{http://schemas.dmtf.org/ovf/envelope/1}capacityAllocationUnits'):
                specified_capacity_bytes = int(
                    specified_capacity * BYTES_PER_TB)
                # TODO: not sure what else to do here: future?
            else:
                print("ERROR: Unable to get disk size")
                specified_capacity_bytes = '0'

    tree.write(
        ovf_file,
        encoding='utf-8',
        xml_declaration=True,
        method='xml')


def get_disk_map_from_ovf(the_ovf):
    """
    Read an OVF file and return a mapping of the disk file(s) to VMs
    :param the_ovf: full opath to the OVF
    :return: list of OvfDisk objects
    """
    if os.path.isfile(the_ovf):
        namespaces = register_all_namespaces(the_ovf)
        tree = ET.parse(the_ovf)
        root = tree.getroot()

        # Read the disks from the References section
        disks = {}
        for files in root.findall('ovf:References', namespaces=namespaces):
            for f in files.findall('ovf:File', namespaces=namespaces):
                if 'file' in f.get('{http://schemas.dmtf.org/ovf/envelope/1}id'):
                    new_disk = OvfDisk()
                    new_disk.file_ref = f.get(
                        '{http://schemas.dmtf.org/ovf/envelope/1}id')
                    new_disk.file_name = f.get(
                        '{http://schemas.dmtf.org/ovf/envelope/1}href')
                    disks[f.get(
                        '{http://schemas.dmtf.org/ovf/envelope/1}id')] = new_disk

        logging.debug(
            '*** VMDK file IDs ("file-") and Local File Names from References Section')
        for disk_key in disks.keys():
            disk_obj = disks[disk_key]
            logging.debug(f'{disk_obj.file_name} => {disk_obj.file_ref}')

        # a table of OvfDisks, indexed by a different key to facilitate lookups in the next section
        disks_by_vmdisk = {}
        for disk in root.findall('ovf:DiskSection', namespaces=namespaces):
            for d in disk.findall('ovf:Disk', namespaces=namespaces):
                ref = d.get('{http://schemas.dmtf.org/ovf/envelope/1}fileRef')
                try:
                    disks[ref].disk_id = d.get(
                        '{http://schemas.dmtf.org/ovf/envelope/1}diskId')
                    disks_by_vmdisk[disks[ref].disk_id] = disks[ref]
                except KeyError as e:
                    logging.error(
                        f'BAD OVF? This should not be happening: {e}')

        logging.debug('*** Disk ID ("vmdisk-") from DiskSection')
        for disk_key in disks.keys():
            disk_obj = disks[disk_key]
            logging.debug(f'{disk_obj.file_name} => {disk_obj.disk_id}')

        for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
            for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
                vm_name = vs.attrib.get(
                    '{http://schemas.dmtf.org/ovf/envelope/1}id')
                logging.debug(f'{vm_name}')
                for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                    for item in vhs.findall('ovf:Item', namespaces=namespaces):
                        for resource in item.findall('rasd:Description', namespaces=namespaces):
                            if resource.text.upper() == 'HARD DISK':
                                hard_disk_name = (item.findall(
                                    'rasd:ElementName', namespaces=namespaces))[0].text
                                hard_disk_file = (item.findall(
                                    'rasd:HostResource', namespaces=namespaces))[0].text[10:]
                                logging.debug(
                                    f"\t{hard_disk_name} => {hard_disk_file}")
                                disks[disks_by_vmdisk[hard_disk_file].file_ref].vm_name = vm_name
                                disks[disks_by_vmdisk[hard_disk_file].file_ref].vm_disk_id = \
                                    hard_disk_name
        # print an intermediate disk map
        for key in disks.keys():
            disk_obj = disks[key]
            logging.debug(
                f'{disk_obj.file_name} => {disk_obj.vm_name} : {disk_obj.vm_disk_id}')

        # Create a map that uses "vm_name:disk_id" as the key and the filename as the value
        vm_hd_file_map = {}
        for key in disks.keys():
            disk_obj = disks[key]
            new_key = f"{disk_obj.vm_name}:{disk_obj.vm_disk_id}"
            vm_hd_file_map[new_key] = disk_obj.file_name
        return vm_hd_file_map


def remap_ovf_for_rsync(source_file,
                        target_file,
                        lib_dir,
                        seed_dir):
    """
    Read target OVF to obtain file names and disk-to-VM mappings, read source OVF for the same and map files on disk
    from the original to the matching target names to facilitate efficient delta rsyncing
    :param source_file: OVF describing existing/old file mappings (full path)
    :param target_file: OVF describing target/new file mappings (full path)
    :param lib_dir: the path containing the existing OVF library
    :param seed_dir: the temporary path used for remapping
    :return: ??
    """

    # TODO - Set the stage:
    #  Old OVF is in full_path_lib/TEMPLATE/TEMPLATE.OVF
    #  New OVF is in full_path_seed/TEMPLATE2/TEMPLATE2.OVF
    #  The process involves renaming/moving the LIB to the SEED while renaming files
    #  DROPPING the RENAMED_INVALID flag so that the rsync process can be run (not deleting any files from SEED)
    #  REMOVING the full_path_lib/TEMPLATE directory upon successful move of SEED files
    #  Once rsync is done (not part of this function), the RENAMED_INVALID flag is removed

    print('=============  READING OVFs ==============')
    old_vm_disk_file_map = get_disk_map_from_ovf(source_file)
    new_vm_disk_file_map = get_disk_map_from_ovf(target_file)
    print('=============  REMAPPING ==============')
    # compare the maps and build a "work list: rename file X to file Y"
    t = PrettyTable(['VM', 'Disk', 'Old File Name', 'New File Name'])
    old_file_name = ''
    new_file_name = ''
    for vm_disk in old_vm_disk_file_map.keys():
        try:
            old_file_name = old_vm_disk_file_map[vm_disk]
            new_file_name = new_vm_disk_file_map[vm_disk]
            (vm, disk) = vm_disk.split(':')
            table_line = [vm, disk, old_file_name, new_file_name]
            t.add_row(table_line)
            # TODO: I think this works (rename during move?)
            shutil.move(os.path.join(seed_dir, old_file_name),
                        os.path.join(lib_dir, new_file_name))
        except KeyError:
            logging.error(
                f'*** {vm_disk} in OLD {old_file_name} is not present in NEW')
            # TODO: remove the excess file?
        except OSError:
            logging.error(
                f'error renaming {old_file_name} to {new_file_name} in {lib_dir}')
    print(t)


def build_extra_config_item(required: str, key: str, value: str):
    extra = ET.Element('vmw:ExtraConfig')
    # this controls the newline and spacing after the element... it is suboptimal
    extra.tail = '\n                '
    extra.set('ovf:required', required)
    extra.set('vmw:key', key)
    extra.set('vmw:value', value)
    return extra


def bubble_the_ovf(rtc_start_time: int, ovf_file: str, backup_file=None):
    """
    stuff all VMs into a "time bubble": the clock is set to the specified time at each boot
    :param ovf_file: full path to OVF file
    :param backup_file: full path to backup file (default replaces ".ovf" with ".ovf.backup")
    :param rtc_start_time: epoch time for Time Bubble start
    :return:
    """
    if backup_file is None:
        backup_file_path = ovf_file.replace('.ovf', '.ovf.backup')
    else:
        backup_file_path = backup_file

    namespaces = register_all_namespaces(ovf_file)
    tree = ET.parse(ovf_file)
    root = tree.getroot()

    # create the backup
    tree.write(backup_file_path, encoding='utf-8',
               xml_declaration=True, method='xml')

    # Time Bubble
    print(
        f'\n=== Time Bubble: {rtc_start_time} => {ctime(rtc_start_time)} ===')
    found_existing_rtc = False
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name}')
            for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                for item in vhs.findall('vmw:ExtraConfig', namespaces=namespaces):
                    if item.get('{http://www.vmware.com/schema/ovf}key') == 'rtc.startTime':
                        found_existing_rtc = True
                        epoch = item.get(
                            '{http://www.vmware.com/schema/ovf}value')
                        print(
                            f'Found existing bubble config: {epoch} => Date: {ctime(int(epoch))}')
                # add the bubble properties
                if not found_existing_rtc:
                    vhs.append(build_extra_config_item(
                        'true', 'time.synchronize.tools.enable', '0'))
                    vhs.append(build_extra_config_item(
                        'true', 'time.synchronize.tools.startup', '0'))
                    vhs.append(build_extra_config_item(
                        'true', 'rtc.startTime', str(rtc_start_time)))
                # TODO: why do these append without a newline? Does it matter aside from aesthetics?
                # TODO: future - if rtc_start_time is 0, remove the bubble?
    tree.write(ovf_file, encoding='utf-8', xml_declaration=True, method='xml')


def unbubble_the_ovf(ovf_file: str, backup_file=None):
    """
    undo a "time bubble"
    :param ovf_file: full path to OVF file
    :param backup_file: full path to backup file (default replaces ".ovf" with ".ovf.backup")
    :return:
    """
    if backup_file is None:
        backup_file_path = ovf_file.replace('.ovf', '.ovf.backup')
    else:
        backup_file_path = backup_file

    namespaces = register_all_namespaces(ovf_file)
    tree = ET.parse(ovf_file)
    root = tree.getroot()

    # create the backup
    tree.write(backup_file_path, encoding='utf-8',
               xml_declaration=True, method='xml')

    # UNDO a Time Bubble
    bubble_keys = ('rtc.startTime', 'time.synchronize.tools.enable',
                   'time.synchronize.tools.startup')
    for vsc in root.findall('ovf:VirtualSystemCollection', namespaces=namespaces):
        for vs in vsc.findall('ovf:VirtualSystem', namespaces=namespaces):
            vm_name = vs.attrib.get(
                '{http://schemas.dmtf.org/ovf/envelope/1}id')
            print(f'{vm_name}')
            for vhs in vs.findall('ovf:VirtualHardwareSection', namespaces=namespaces):
                for item in vhs.findall('vmw:ExtraConfig', namespaces=namespaces):
                    item_key = item.get(
                        '{http://www.vmware.com/schema/ovf}key')
                    if item_key in bubble_keys:
                        if item_key == 'rtc.startTime':
                            epoch = item.get(
                                '{http://www.vmware.com/schema/ovf}value')
                            print(
                                f'Scrubbing existing bubble config: {epoch} => Date: {ctime(int(epoch))}')
                        vhs.remove(item)
    tree.write(ovf_file, encoding='utf-8', xml_declaration=True, method='xml')
