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
A minimum of 1 TB is recommended, depending on the on-disk sizes of your templates, though more is better!


EXAMPLE Workflow

`$ ssh catalog@CATALOG_HOST_NAME`

(suggestion to use something like tmux for virtual sessions -- these commands can take many hours to run)

`$ tmux attach -t CONTENT`

`$ cd /hol`

Export from the source cloud

`$ bin/export_ovf.py  --cloud_host VCD-CLOUD.vmware.com --cloud_org VCD-ORG --cloud_catalog HOL-Source-Catalog --vapp_template_name TEST_TEMPLATE`

Validate that the export has downloaded completely/successfully

`$ bin/validate_ovf.py --vapp_template_name TEST_TEMPLATE --repository /hol/lib`

"Scrub" the download to clean up the OVF file and pre pit for clean import to another instance.

`$ bin/scrub_ovf.py lib/2vm_blank/2vm_blank.ovf`

Import the file to another cloud

`$ bin/import_ovf.py --cloud_host VCD-CLOUD2.vmware.com --cloud_org VCD-ORG2 --cloud_catalog HOL-Target-Catalog --vapp_template_name TEST_TEMPLATE`


TODO:
o "pull and verify" to grab a template from another node rather than a VCD instance
o "scrub_ovf" to clean up an OVF for succesful import (remove "objectionable" settings, adjust disks, networking, etc.)
o "mailbox" and daemon to watch for work to do

-Doug Baer
07 February 2022
