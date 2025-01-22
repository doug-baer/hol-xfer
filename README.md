HOL Transfer / Catalog Node

Cloud Director out of band transit node: export and import functionality in
addition to the "validate_ovf" functionality to ensure that all component files have been
downloaded properly.

A system running these scripts will pull the files (export using ovftool) to the local
file system and then push them (import using ovftool) into the local VCD instance.

The idea is that a Linux VM running within the target VMware Cloud Director environment,
with external network connectivity via SSH and a direct HTTPS connection to the local VCD
instance is the most efficient model for getting content in and out of a VCD instance.
The Linux VM requires sufficient local storage to handle at least one exported template.
A minimum of 1 TB is recommended, depending on the on-disk sizes of your templates and how
long you'd like to keep them around.

REQUIRES: Broadcom/VMware ovftool compatible with your version(s) of Cloud Director.
Get it here https://developer.broadcom.com/tools/open-virtualization-format-ovf-tool/latest

Main configuration is performed in hol-xfer/config.yaml


EXAMPLE Workflow

`$ ssh catalog@CATALOG_HOST_NAME`

(suggestion to use something like tmux for virtual sessions -- these commands can take many hours to run)

`$ tmux new-session -A -s CONTENT-TRANSFER`

`$ cd /hol/hol-xfer`

Export a template from the source cloud

`$ bin/export_ovf.py  --config config.yaml --cloud_host VCD-CLOUD.vmware.com --cloud_org VCD-ORG --cloud_catalog HOL-Source-Catalog --vapp_template_name TEST_TEMPLATE`

Validate that the export has downloaded completely/successfully

`$ bin/validate_ovf.py --vapp_template_name TEST_TEMPLATE --repository /hol/lib`

(optional) "Scrub" the download to clean up the OVF file and prep it for clean import to another instance.
NOTE: Definitely requires changes based on VCD versions and your template structure. Specifically consider vApp Networks and names.
This version is very specific to VMware Hands-on Labs (HOL) template conventions up until 2021. Use at your own risk.

`$ bin/scrub_ovf.py --repository /hol/lib --vapp_template_name 2vm_blank`

Transfer all files to another catalog instance (log into the _remote_ node and pull), then validate again (if you want to)

`$ hol-xfer/bin/pull_template.py  --vapp_template_name ${pod} --repository /hol/lib --source_catalog MAIN-CATALOG --source_path /hol/lib  --config hol-xfer/config.yaml && hol-xfer/bin/validate_ovf.py --repository /hol/lib --vapp_template_name ${pod}`

Import the template to the target cloud -- the one local to the node that you pulled it to

`$ bin/import_ovf.py --config config.yaml --cloud_host VCD-CLOUD2.vmware.com --cloud_org VCD-ORG2 --cloud_catalog HOL-Target-Catalog --vapp_template_name TEST_TEMPLATE`

That's it.

Update 2025:

Due to a recent request, I have added a convenient function to import ISO files -- "media" in VCD parlance -- to a cloud. It assumes a directory named "ISO" exists in the repository path to contain the images. With that in place, you can use pull_template with a name of "ISO" to easily keep that sub-repository in sync between nodes.

Import an ISO image to Cloud Director

`$ bin/import_iso.py --config config.yaml --cloud_host VCD-CLOUD2.vmware.com --cloud_org VCD-ORG2 --cloud_catalog HOL-Target-Catalog --iso_name MY_ISO_FILE.iso`


-Doug Baer
22 January 2025
