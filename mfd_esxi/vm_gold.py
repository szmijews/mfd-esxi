# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Virtual Machine: gold and created out of gold."""

import logging
import math
import os
import re
from textwrap import dedent
from time import sleep, time
from typing import TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level
from packaging.version import Version
from mfd_connect.local import LocalConnection
from mfd_connect.util.rpc_copy_utils import copy
from .exceptions import (
    ESXiNotFound,
    ESXiWrongParameter,
    ESXiVMCopyTimeout,
    ESXiVFUnavailable,
)
from .vm_base import ESXiVMBase

if TYPE_CHECKING:
    from mfd_esxi.host import ESXiHypervisor
    from mfd_network_adapter.network_interface.esxi import ESXiNetworkInterface

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)

ESXI_VM_ADAPTER_TYPES = ["vmxnet", "vmxnet3", "e1000", "e1000e", "vlance"]

vmx_template = dedent(
    """\
    .encoding = "UTF-8"
    RemoteDisplay.maxConnections = "-1"
    bios.bootRetry.delay = "10"
    config.version = "8"
    ehci.present = "TRUE"
    ethernet0.addressType = "generated"
    ethernet0.present = "TRUE"
    ethernet0.uptCompatibility = "TRUE"
    ethernet0.virtualDev = "vmxnet3"
    ethernet0.wakeOnPcktRcv = "FALSE"
    floppy0.present = "FALSE"
    hpet0.present = "TRUE"
    mks.enable3d = "TRUE"
    pciBridge0.present = "TRUE"
    pciBridge4.functions = "8"
    pciBridge4.present = "TRUE"
    pciBridge4.virtualDev = "pcieRootPort"
    pciBridge5.functions = "8"
    pciBridge5.present = "TRUE"
    pciBridge5.virtualDev = "pcieRootPort"
    pciBridge6.functions = "8"
    pciBridge6.present = "TRUE"
    pciBridge6.virtualDev = "pcieRootPort"
    pciBridge7.functions = "8"
    pciBridge7.present = "TRUE"
    pciBridge7.virtualDev = "pcieRootPort"
    powerType.powerOff = "default"
    powerType.reset = "default"
    powerType.suspend = "soft"
    sched.cpu.affinity = "all"
    sched.cpu.latencySensitivity = "normal"
    sched.cpu.min = "0"
    sched.cpu.shares = "normal"
    sched.cpu.units = "mhz"
    sched.mem.pin = "TRUE"
    sched.mem.shares = "normal"
    sched.scsi0:0.shares = "normal"
    sched.scsi0:0.throughputCap = "off"
    scsi0.present = "TRUE"
    scsi0:0.deviceType = "scsi-hardDisk"
    scsi0:0.present = "TRUE"
    svga.autodetect = "TRUE"
    svga.present = "TRUE"
    toolScripts.afterPowerOn = "TRUE"
    toolScripts.afterResume = "TRUE"
    toolScripts.beforePowerOff = "TRUE"
    toolScripts.beforeSuspend = "TRUE"
    tools.syncTime = "FALSE"
    tools.upgrade.policy = "manual"
    usb.present = "TRUE"
    virtualHW.version = "17"
    vmci0.present = "TRUE"
"""
)

vmotion_template = dedent(
    """\
    featMask.vm.cpuid.AES = "Val:1"
    featMask.vm.cpuid.AVX = "Val:1"
    featMask.vm.cpuid.CMPXCHG16B = "Val:1"
    featMask.vm.cpuid.DS = "Val:1"
    featMask.vm.cpuid.FAMILY = "Val:6"
    featMask.vm.cpuid.FCMD = "Val:1"
    featMask.vm.cpuid.IBPB = "Val:1"
    featMask.vm.cpuid.IBRS = "Val:1"
    featMask.vm.cpuid.Intel = "Val:1"
    featMask.vm.cpuid.LAHF64 = "Val:1"
    featMask.vm.cpuid.LM = "Val:1"
    featMask.vm.cpuid.MDCLEAR = "Val:1"
    featMask.vm.cpuid.MODEL = "Val:0x2d"
    featMask.vm.cpuid.MWAIT = "Val:1"
    featMask.vm.cpuid.NUMLEVELS = "Val:0xd"
    featMask.vm.cpuid.NUM_EXT_LEVELS = "Val:0x80000008"
    featMask.vm.cpuid.NX = "Val:1"
    featMask.vm.cpuid.PCID = "Val:1"
    featMask.vm.cpuid.PCLMULQDQ = "Val:1"
    featMask.vm.cpuid.POPCNT = "Val:1"
    featMask.vm.cpuid.RDTSCP = "Val:1"
    featMask.vm.cpuid.SS = "Val:1"
    featMask.vm.cpuid.SSBD = "Val:1"
    featMask.vm.cpuid.SSE3 = "Val:1"
    featMask.vm.cpuid.SSE41 = "Val:1"
    featMask.vm.cpuid.SSE42 = "Val:1"
    featMask.vm.cpuid.SSSE3 = "Val:1"
    featMask.vm.cpuid.STEPPING = "Val:2"
    featMask.vm.cpuid.STIBP = "Val:1"
    featMask.vm.cpuid.VMX = "Val:1"
    featMask.vm.cpuid.XCR0_MASTER_SSE = "Val:1"
    featMask.vm.cpuid.XCR0_MASTER_YMM_H = "Val:1"
    featMask.vm.cpuid.XSAVE = "Val:1"
    featMask.vm.hv.capable = "Val:1"
    featMask.vm.vt.realmode = "Val:1"
    featureCompat.vm.completeMasks = "TRUE"
"""
)


class ESXiVMGold:
    """Class for discovering Gold image of VM."""

    def __init__(self, owner: "ESXiHypervisor", datastore: str, name: str):
        """
        Initialize Gold image.

        :param owner: ESXi host
        :param datastore: datastore
        :param name: name of image (folder and files)
        """
        self.owner = owner
        self.datastore = datastore
        self.name = name
        self.firmware = None
        self.guestOS = None
        self.scsi_dev = None
        self.primary_vmdk = None
        self.parent_vmdk = None
        self.primary_flat = None
        self.parent_flat = None

    def initialize(self) -> None:
        """Initialize GOLD image based on VMX and VMDK files."""
        path = f"/vmfs/volumes/{self.datastore}/{self.name}"
        output = self.owner.execute_command(f"cat {path}/*.vmx", shell=True).stdout

        regex = re.search(r"firmware\s*=\s*(\"efi\")", output)
        self.firmware = "efi" if regex else ""

        regex = re.search(r"guestOS\s*=\s*(\")(?P<name>.*)(\")", output)
        self.guestOS = regex.group("name") if regex else ""

        regex = re.search(r"scsi0\.virtualDev\s*=\s*(\")(?P<name>.*)(\")", output)
        if not regex:
            raise ESXiNotFound("Cannot fetch disk device from base image")
        self.scsi_dev = regex.group("name")

        regex = re.search(r"scsi0:0\.fileName\s*=\s*(\")(?P<name>.*)(\")", output)
        if not regex:
            raise ESXiNotFound("Cannot fetch disk file name from base image")
        self.primary_vmdk = regex.group("name")

        output = self.owner.execute_command(f"cat {path}/{self.primary_vmdk}").stdout

        regex = re.search(r"parentFileNameHint\s*=\s*(\")(?P<name>.*)(\")", output)
        if not regex:
            raise ESXiNotFound("Cannot fetch parent disk file name from base image")
        self.parent_vmdk = regex.group("name")

        regex = re.search(r"SPARSE\s*(\")(?P<name>.*)(\")", output)
        if not regex:
            raise ESXiNotFound("Cannot fetch disk image file name from base image")
        self.primary_flat = regex.group("name")

        output = self.owner.execute_command(f"cat {path}/{self.parent_vmdk}").stdout

        regex = re.search(r"VMFS\s*(\")(?P<name>.*)(\")", output)
        if not regex:
            raise ESXiNotFound("Cannot fetch disk image file name from base image")
        self.parent_flat = regex.group("name")


class ESXiVM(ESXiVMBase):
    """Class for handling VMs created out of golden image."""

    def __init__(
        self,
        gold: "ESXiVMGold",
        name: str,
        mng: str,
        tag: str = "",
        datastore: str = None,
        cpu: int = 4,
        mem: int = 2048,
        iommu: bool = False,
        vmotion: bool = False,
    ):
        """Initialize VM created out of Gold image.

        :param gold: gold image object
        :param name: name of new VM
        :param mng: portgroup for management network
        :param tag: tag string
        :param datastore: datastore to create file on
        :param cpu: number of cpus
        :param mem: amount of memory
        :param iommu: enable IOMMU
        :param vmotion: prepare machine for vMotion
        """
        super().__init__(owner=gold.owner)
        self.gold = gold
        self.datastore = datastore if datastore is not None else gold.datastore
        self.folder = name
        self.name = name
        self.tag = tag
        self.mng = mng
        self.cpu = cpu
        self.mem = mem
        self.iommu = iommu
        self.vmotion = vmotion
        self.ethernet = []
        self.pciPassthru = []

    def write_vmx(self) -> None:
        """Write VMX file to VM folder."""
        with open(os.path.join(os.getcwd(), f"{self.name}.vmx"), mode="w", newline="\n") as file:
            lines = vmx_template.splitlines()
            lines = [line + "\n" for line in lines]
            file.writelines(lines)
            if self.vmotion:
                lines = vmotion_template.splitlines()
                lines = [line + "\n" for line in lines]
                file.writelines(lines)

            file.write(f'displayName = "{self.name}"\n')
            file.write(f'nvram = "{self.name}.nvram"\n')

            file.write(f'ethernet0.networkName = "{self.mng}"\n')
            if self.iommu:
                cpu = math.ceil(self.cpu / 2) * 2
                file.write(f'cpuid.coresPerSocket = "{int(cpu / 2)}"\n')
                file.write(f'numvcpus = "{self.cpu}"\n')
                file.write('vvtd.enable = "TRUE"\n')
            else:
                file.write(f'cpuid.coresPerSocket = "{self.cpu}"\n')
                file.write(f'numvcpus = "{self.cpu}"\n')
            file.write(f'memSize = "{self.mem}"\n')
            file.write(f'sched.mem.min = "{self.mem}"\n')
            file.write(f'sched.mem.minSize = "{self.mem}"\n')

            if self.gold.firmware:
                file.write('firmware = "efi"\n')
            file.write(f'guestOS = "{self.gold.guestOS}"\n')
            file.write(f'scsi0.virtualDev = "{self.gold.scsi_dev}"\n')
            file.write(f'scsi0:0.fileName = "{self.gold.primary_vmdk}"\n')

            for nr, data in enumerate(self.ethernet):
                for k, v in data.items():
                    file.write(f'ethernet{nr + 1}.{k} = "{v}"\n')

            for nr, data in enumerate(self.pciPassthru):
                for k, v in data.items():
                    file.write(f'pciPassthru{nr}.{k} = "{v}"\n')

        copy(
            src_conn=LocalConnection(),
            dst_conn=self.owner.connection,
            source=os.path.join(os.getcwd(), file.name),
            target=f"/vmfs/volumes/{self.datastore}/{self.name}/{self.name}.vmx",
        )
        os.remove(f"{self.name}.vmx")

    def create(self, register: bool = True, start: bool = True) -> None:
        """Create VM files.

        :param register: register VM
        :param start: start VM after creation
        """
        vm_folder = f"/vmfs/volumes/{self.datastore}/{self.name}"
        gold_folder = f"/vmfs/volumes/{self.gold.datastore}/{self.gold.name}"

        self.owner.execute_command(f"rm -rf {vm_folder}")
        self.owner.execute_command(f"mkdir -p {vm_folder}")
        self.owner.execute_command(f"cp {gold_folder}/{self.gold.primary_flat} {vm_folder}")
        self.owner.execute_command(f"cp {gold_folder}/{self.gold.primary_vmdk} {vm_folder}")
        if self.vmotion:
            src = self.owner.execute_command(f"ls -l {gold_folder}/{self.gold.parent_flat}").stdout
            src_len = int(src.split()[4])

            self.owner.connection.start_process(f"cp {gold_folder}/{self.gold.parent_flat} {vm_folder}")

            start_time = time()
            while True:
                sleep(15)
                dst = self.owner.execute_command(f"ls -l {vm_folder}/{self.gold.parent_flat}").stdout
                dst_len = int(dst.split()[4])
                if src_len == dst_len:
                    break

                if time() > start_time + 900:
                    raise ESXiVMCopyTimeout("Copying of VM disk file took too long")

            self.owner.execute_command(f"cp {gold_folder}/{self.gold.parent_vmdk} {vm_folder}")
        else:
            self.owner.execute_command(f"ln -s {gold_folder}/{self.gold.parent_flat} {vm_folder}")
            self.owner.execute_command(f"ln -s {gold_folder}/{self.gold.parent_vmdk} {vm_folder}")

        self.write_vmx()

        file = f"/vmfs/volumes/{self.datastore}/{self.folder}/{self.name}.vmx"
        if register:
            self.register(file)
            if start:
                self.start()

    def attach_network(
        self,
        portgroup: str,
        model: str = "vmxnet3",
        rss: bool = False,
        pf: "ESXiNetworkInterface" = None,
    ) -> None:
        """Attach network adapter to VM.

        :param portgroup: portgroup name
        :param model: type of adapter: sriov|ptp|vmxnet|vmxnet3|e1000|e1000e|vlance
        :param rss: enable RSS on VMXNET3 adapter
        :param pf: PF of SR-IOV interface
        """
        if model == "sriov":
            pci_address = pf.pci_address.lspci_short
            bus, dev, fun = re.split("[.:]+", pci_address)
            pci = f"{int(bus, 16):04d}:{int(dev, 16):02d}.{int(fun, 16):02d}"
            add_adapter = {
                "networkName": portgroup,
                "pfId": pci,
                "deviceId": "0",
                "vendorId": "0",
                "systemId": "BYPASS",
                "id": pci,
                "allowMTUChange": "TRUE",
                "present": "True",
            }
            self.pciPassthru.append(add_adapter)
        elif model == "ptp":
            output = self.owner.execute_command(
                f"esxcli network sriovnic vf list -n {pf.name} | grep false | head -n 1",
                shell=True,
            ).stdout
            pattern = r"(?P<domain>[a-f0-9]+):(?P<bus>[a-f0-9]+):(?P<slot>[a-f0-9]+).(?P<func>\d)"
            match = re.search(pattern=pattern, string=output)
            if not match:
                raise ESXiVFUnavailable(f"No VF from {pf.name} available for testing")
            is_8_0_3_or_newer = self.owner.esxi_version.version >= Version("8.0.3")
            # ESXi 8.0u3 displays in hex - no need to convert for lspci command which needs PCI in hex format
            bus = match.group("bus") if is_8_0_3_or_newer else f'{int(match.group("bus")):0{2}x}'
            slot = match.group("slot") if is_8_0_3_or_newer else f'{int(match.group("slot")):0{2}x}'
            func = match.group("func")
            output = self.owner.execute_command(f"lspci -p | grep :{bus}:{slot}.{func}", shell=True).stdout
            dev_ven = output.split()[1].split(":")
            # .vmx file still needs PCI address in decimal format, need to convert to decimal for ESXi 8.0u3
            if is_8_0_3_or_newer:
                pci_pass_id = (
                    f'{int(match.group("domain"), 16):0{5}}:{int(match.group("bus"), 16):0{3}}:'
                    f'{int(match.group("slot"), 16):0{2}}.{int(match.group("func"), 16):0{1}}'
                )
            else:
                pci_pass_id = match.group(0)
            add_adapter = {
                "enablePTP": "TRUE",
                "systemId": "BYPASS",
                "deviceId": f"0x{dev_ven[1]}",
                "vendorId": f"0x{dev_ven[0]}",
                "id": f"{pci_pass_id}",
                "present": "True",
            }
            self.pciPassthru.append(add_adapter)
        elif model in ESXI_VM_ADAPTER_TYPES:
            add_adapter = {
                "virtualDev": model,
                "networkName": portgroup,
                "present": "TRUE",
            }
            # needed for RSS, 4 is max queues for RSS engine, 3 is secondary queues
            if rss:
                rss_settings = {"pNicFeatures": "4", "ctxPerDev": "3"}
                add_adapter.update(rss_settings)
            self.ethernet.append(add_adapter)
        else:
            raise ESXiWrongParameter(f"Wrong parameter {model} provided for adapter type")
