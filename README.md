> [!IMPORTANT]  
> This project is under development. All source code and features on the main branch are for the purpose of testing or evaluation and not production ready.

# MFD ESXI
Library to access and manipulate VMware products: ESXi, VCSA and NSX.

> [!IMPORTANT]
> This module requires `vsphere-automation-sdk` to work.\
> Please add `vsphere-automation-sdk` to your requirements file or install it manually:
> ```bash
> pip install vsphere-automation-sdk @ git+https://github.com/vmware/vsphere-automation-sdk-python@v8.0.3.0
> ```

## API - vswitch (ESXivSwitch)
* `set_forged_transmit(self, name: str, enable: bool = True) -> None` - set forged transmit policy on portgroup
* `change_ens_fpo_support(self, enable: bool, vds: str | None = None) -> None` - enable or disable FPO support
* `set_mac_change_policy(self, portgroup_name: str, enable: bool = True) -> None` - set MAC change policy on portgroup

## OS supported:

ESXi >= 7.0
NSX >= 3.2, INFRA api only

## Issue reporting

If you encounter any bugs or have suggestions for improvements, you're welcome to contribute directly or open an issue [here](https://github.com/intel/mfd-esxi/issues).