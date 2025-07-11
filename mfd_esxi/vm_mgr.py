# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Virtual Machine Manager."""

import logging
import re
from itertools import cycle
from typing import Generator, List, Union, TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level
from .vm_base import ESXiVMBase
from .vm_gold import ESXiVMGold, ESXiVM

if TYPE_CHECKING:
    from .host import ESXiHypervisor
    from mfd_network_adapter.network_interface.esxi import ESXiNetworkInterface

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class ESXiVMMgr:
    """Class for VM manager."""

    def __init__(self, owner: "ESXiHypervisor"):
        """Initialize VM manager.

        :param owner: ESXi host
        """
        self.owner = owner
        self.vm: List[ESXiVMBase] = []
        self.gold: List[ESXiVMGold] = []

    def initialize(self) -> None:
        """Initialize VM list."""
        self.vm = ESXiVMBase.discover(self.owner)

    def refresh_ids(self) -> None:
        """Refresh IDs of VMs."""
        new_vms = ESXiVMBase.discover(self.owner)
        for vm in self.vm:
            for nvm in new_vms:
                if vm.name == nvm.name:
                    vm.id = nvm.id
                    break

    def clean(self, keep: str = "") -> None:
        """Clean VMs on host based on regex.

        :param keep: if not empty - regex to match VM names to keep
        """
        new = []
        for vm in self.vm:
            if keep and re.search(keep, vm.name):
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Keeping VM id: {vm.id} name: {vm.name}",
                )
                new.append(vm)
            else:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Removing VM id: {vm.id} name: {vm.name}",
                )
                if vm.connection:
                    vm.connection.disconnect()
                vm.stop()
                vm.unregister()
        self.vm = new

    def remove_old_images(self, datastore: str) -> None:
        """Remove stale VM images from local datastore.

        :param datastore: datastore to remove images
        """

        def get_all_vm_images() -> Generator[tuple, None, None]:
            """Get all images present on local datastore as well as their indexes.

            :return: generator of images present on local datastore as well as their indexes
            """
            regexp = r"Base_[0-9A-Z]+_VM(?P<guest_index>[0-9]{3})_[0-9]+"

            for entry in self.owner.connection.modules().os.scandir(f"/vmfs/volumes/{datastore}"):
                match = re.search(regexp, entry.name)
                if entry.is_dir() and match:
                    yield entry.name, int(match.group("guest_index"))

        for entry in filter(lambda img_info: img_info[1] > 3, get_all_vm_images()):
            image = entry[0]
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Image {image} will be removed")
            command = f"rm -rf /vmfs/volumes/{datastore}/{image}"
            self.owner.execute_command(command)

    def prepare_vms(
        self,
        gold_datastore: str,
        gold_name: str,
        count: int,
        suffix: str,
        mng: str = "VM Network",
        tag: str = "",
        datastore: str = None,
        cpu: int = 4,
        mem: int = 2048,
        iommu: bool = False,
        vmotion: bool = False,
    ) -> List["ESXiVM"]:
        """Prepare VMs based on Gold image.

        :param gold_datastore: gold datastore name
        :param gold_name: name of gold image
        :param count: number of VMs to prepare
        :param suffix: suffix to add to every name on host
        :param mng: name of management network
        :param tag: tag string
        :param datastore: destination datastore name
        :param cpu: number of vCPU on VM
        :param mem: amount of memory for VM
        :param iommu: enable IOMMU
        :param vmotion: prepare for vMotion
        """
        for gold in self.gold:
            if gold.name == gold_name:
                break
        else:
            gold = ESXiVMGold(owner=self.owner, datastore=gold_datastore, name=gold_name)
            gold.initialize()
            self.gold.append(gold)

        max_value = 0
        for vm in self.vm:
            if vm.name.startswith(f"{gold.name}_VM"):
                value = vm.name[len(gold.name) + 3 : len(gold.name) + 6]
                try:
                    value = int(value)
                except ValueError:
                    continue
                max_value = max(max_value, value)

        vms = []
        for i in range(count):
            vms.append(
                ESXiVM(
                    gold=gold,
                    name=f"{gold.name}_VM{i + max_value + 1:03}_{suffix}",
                    mng=mng,
                    tag=tag,
                    datastore=datastore,
                    cpu=cpu,
                    mem=mem,
                    iommu=iommu,
                    vmotion=vmotion,
                )
            )
        return vms

    @staticmethod
    def attach_network(
        vms: List[ESXiVM],
        portgroup: Union[str, List[str]],
        model: str = "vmxnet3",
        rss: bool = False,
        adapter: Union["ESXiNetworkInterface", List["ESXiNetworkInterface"]] = None,
    ) -> None:
        """Attach network adapter to VMs.

        :param vms: list of VMs
        :param portgroup: portgroup name
        :param model: type of adapter: sriov|vmxnet|vmxnet3|e1000|e1000e|vlance
        :param rss: enable RSS on VMXNET3 adapter
        :param adapter: PF adapter of SR-IOV adapter
        """
        if isinstance(portgroup, List):
            pg = cycle(portgroup)
        else:
            pg = cycle([portgroup])
        if isinstance(adapter, List):
            ad = cycle(adapter)
        else:
            ad = cycle([adapter])

        for vm in vms:
            vm.attach_network(portgroup=next(pg), model=model, rss=rss, pf=next(ad))

    def create_vms(self, vms: List["ESXiVM"], register: bool = True, start: bool = True) -> None:
        """Create VM files.

        :param vms: list of VMs
        :param register: register VMs
        :param start: start VMs after creation
        """
        for vm in vms:
            vm.create(register=register, start=start)
            self.vm.append(vm)

    @staticmethod
    def wait_for_start_vms(vms: List["ESXiVM"], timeout: int = 300) -> None:
        """Wait for VMs to start and create connection.

        :param vms: list of VMs
        :param timeout: time to wait for VM to start
        """
        for vm in vms:
            vm.get_guest_mng_ip(timeout=timeout)

    def find_vms(self, gold: str = None) -> List["ESXiVM"]:
        """Find VMs based on criteria.

        :param gold: gold image name
        """
        vms = []
        for vm in self.vm:
            if isinstance(vm, ESXiVM):
                if vm.gold.name == gold:
                    vms.append(vm)
        return vms
