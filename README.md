HOL Transfer / Catalog Node

Cloud Director out of band transit node: export and import functionality in
addition to the "validate_ovf" functionality to ensure that all component files have been
downloaded properly.

A system running these scripts will pull the files (export using ovftool) to the local
file system and then push them (import using ovftool) into the local VCD instance.

The idea is that a Linux VM running within the target VCD environment, with external
network connectivity on port 22 and a direct connection to the local VCD instance is the most
efficient model for getting content in and out of a VCD instance. The Linux VM requires sufficient
local storage to handle at least one exported template, though more is better!


EXAMPLE Workflow

`$ ssh catalog@CATALOG_HOST_NAME`

```
$ tmux ls
1: 1 windows (created Thu Nov 18 22:18:07 2021)
CONTENT: 1 windows (created Wed Dec 22 21:55:31 2021)
```

`$ tmux attach -t CONTENT`


`$ cd /hol`

`$ bin/export_ovf.py  --cloud_host VCD-CLOUD.vmware.com --cloud_org VCD-ORG --cloud_catalog HOL-Source-Catalog --vapp_template_name TEST_TEMPLATE`

`$ bin/validate_ovf.py --vapp_template_name TEST_TEMPLATE --repository /hol/lib`

`$ bin/scrub_ovf.py lib/2vm_blank/2vm_blank.ovf`

`$ bin/import_ovf.py --cloud_host VCD-CLOUD2.vmware.com --cloud_org VCD-ORG2 --cloud_catalog HOL-Target-Catalog --vapp_template_name TEST_TEMPLATE`


TODO:
	o "pull and verify" to grab a template from another node rather than a VCD instance
	o "scrub_ovf" to clean up an OVF for succesful import (remove "objectionable" settings, adjust disks, networking, etc.)

-Doug Baer
04 February 2022
