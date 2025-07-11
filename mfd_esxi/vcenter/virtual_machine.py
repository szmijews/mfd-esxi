# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""VirtualMachine wrapper."""
import logging
from typing import Optional, Any, Generator, Union, TYPE_CHECKING
from pyVmomi import vim
from time import sleep

from mfd_common_libs import log_levels, add_logging_level
from .utils import get_obj_from_iter
from .distributed_switch.portgroup import DSPortgroup
from .virtual_switch.portgroup import VSPortgroup

if TYPE_CHECKING:
    from .datastore import Datastore
    from .host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


INTERVAL_TIMEOUT = 5
INTERVAL_POWER_OFF = 30

HEARTBEAT_TIMEOUT = 300
POWER_STATE_TIMEOUT = 60


class VirtualMachine(object):
    """VirtualMachine wrapper."""

    def __init__(self, name: str, host: "Host"):
        """
        Initialize instance.

        :param name: Name of VM.
        :param host: Host.
        """
        self._name = name
        self._host = host

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> "vim.VirtualMachine":
        """Get content of VM in API."""
        return get_obj_from_iter(
            self._host.vcenter.create_view(self._host.content, [vim.VirtualMachine]),
            self.name,
        )

    @property
    def name(self) -> str:
        """Get name of VM."""
        return self._name

    def unregister(self) -> None:
        """Unregister VM from host."""
        self.power_off()
        self.content.Unregister()

    @property
    def power_state(self) -> "vim.VirtualMachine.PowerState":
        """Get power stat for virtual machine."""
        return self.content.runtime.powerState

    def power_off(self, wait: bool = True) -> Optional["vim.Task"]:
        """
        Power off virtual machine.

        :param wait: If true method will wait for powered off.

        :return: Task if operation is in progress otherwise None.
        """
        if self.power_state == vim.VirtualMachine.PowerState.poweredOn:
            task = self.content.PowerOff()
            if not wait:
                return task
            self._host.vcenter.wait_for_tasks([task])

    def power_on(self, wait: bool = True) -> Optional["vim.Task"]:
        """
        Power on virtual machine.

        :param wait: If true method will wait for powered on.

        :return: Task if operation is in progress otherwise None.
        """
        if self.power_state == vim.VirtualMachine.PowerState.poweredOff:
            task = self.content.PowerOn()
            if not wait:
                return task
            self._host.vcenter.wait_for_tasks([task])

    def restart(self, wait: bool = True) -> Optional["vim.Task"]:
        """
        Restart virtual machine.

        :param wait: If true method will wait for restart.

        :return: Task if operation is in progress otherwise None.
        """
        if self.power_state == vim.VirtualMachine.PowerState.poweredOff:
            return self.power_on(wait)
        task = self.content.Reset()
        if not wait:
            return task
        self._host.vcenter.wait_for_tasks([task])

    def shutdown(self) -> bool:
        """
        Shutdown guest.

        :return: True if shutdown success otherwise False.
        """
        if self._wait_for_heartbeat():
            self.content.ShutdownGuest()
            return self._wait_for_power_state(vim.VirtualMachine.PowerState.poweredOff)
        return False

    def reboot(self) -> bool:
        """
        Reboot guest.

        :return: True if reboot success otherwise False.
        """
        if self._wait_for_heartbeat():
            self.content.RebootGuest()
            sleep(INTERVAL_POWER_OFF)
            return self._wait_for_heartbeat()
        return False

    def relocate(
        self,
        datastore: "Datastore",
        priority: "vim.VirtualMachine.MovePriority" = vim.VirtualMachine.MovePriority.defaultPriority,
        wait: bool = True,
    ) -> vim.Task:
        """
        Relocate a virtual machine's specific host.

        :param datastore: Datastore that all vm disks will be moved.
        :param priority: The task priority (defaultPriority, highPriority, lowPriority).
        :param wait: If true method will wait for migrate.

        :return: Task.
        """
        relocate_spec = vim.vm.RelocateSpec()
        relocate_spec.host = datastore.host.content
        relocate_spec.pool = datastore.host.content.parent.resourcePool
        relocate_spec.datastore = datastore.content
        task = self.content.Relocate(spec=relocate_spec, priority=priority)
        if wait:
            self._host.vcenter.wait_for_tasks([task])
        return task

    @property
    def network_adapters(
        self,
    ) -> Generator[vim.vm.device.VirtualEthernetCard, Any, None]:
        """Get all adapters attached to VM."""
        return (
            adapter
            for adapter in self.content.config.hardware.device
            if isinstance(adapter, vim.vm.device.VirtualEthernetCard)
        )

    @property
    def sriov_adapters(
        self,
    ) -> Generator[vim.vm.device.VirtualSriovEthernetCard, Any, None]:
        """Get all SR-IOV adapters attached to VM."""
        return (
            adapter
            for adapter in self.content.config.hardware.device
            if isinstance(adapter, vim.vm.device.VirtualSriovEthernetCard)
        )

    def add_vmxnet3_adapter(self, portgroup: Union["DSPortgroup", "VSPortgroup"]) -> None:
        """
        Add new vmxnet3 adapter to VM.

        :param portgroup: Portgroup where adapter should be assigned.
        """
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        nic.device = vim.vm.device.VirtualVmxnet3()

        if isinstance(portgroup, VSPortgroup):
            nic.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            nic.device.backing.network = portgroup.content
            nic.device.backing.deviceName = portgroup.name
        elif isinstance(portgroup, DSPortgroup):
            nic.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            nic.device.backing.port = vim.dvs.PortConnection()
            nic.device.backing.port.portgroupKey = portgroup.content.key
            nic.device.backing.port.switchUuid = portgroup.content.config.distributedVirtualSwitch.uuid

        nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.device.connectable.startConnected = True
        nic.device.connectable.allowGuestControl = True

        config = vim.vm.ConfigSpec(deviceChange=[nic])
        self._host.vcenter.wait_for_tasks([self.content.ReconfigVM_Task(config)])

    def add_sriov_adapter(self, portgroup: Union["DSPortgroup", "VSPortgroup"], adapter_name: str) -> None:
        """
        Add new sriov adapter to VM.

        :param portgroup: Portgroup where adapter should be assigned.
        :param adapter_name: Adapter name.
        """
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        nic.device = vim.vm.device.VirtualSriovEthernetCard()

        if isinstance(portgroup, VSPortgroup):
            nic.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            nic.device.backing.network = portgroup.content
            nic.device.backing.deviceName = portgroup.name
        elif isinstance(portgroup, DSPortgroup):
            nic.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            nic.device.backing.port = vim.dvs.PortConnection()
            nic.device.backing.port.portgroupKey = portgroup.content.key
            nic.device.backing.port.switchUuid = portgroup.content.config.distributedVirtualSwitch.uuid

        nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.device.connectable.startConnected = True

        nic.device.sriovBacking = vim.vm.device.VirtualSriovEthernetCard.SriovBackingInfo()
        nic.device.sriovBacking.physicalFunctionBacking = vim.vm.device.VirtualPCIPassthrough.DeviceBackingInfo()
        pnic = [x for x in self.content.summary.runtime.host.config.network.pnic if x.device == adapter_name]
        nic.device.sriovBacking.physicalFunctionBacking.id = pnic[0].pci
        nic.device.allowGuestOSMtuChange = True

        config = vim.vm.ConfigSpec(deviceChange=[nic])
        self._host.vcenter.wait_for_tasks([self.content.ReconfigVM_Task(config)])

    def remove_adapter(self, adapter: vim.vm.device.VirtualEthernetCard) -> None:
        """
        Remove adapter from VM.

        :param adapter: Adapter to remove.
        """
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        nic.device = adapter

        config = vim.vm.ConfigSpec(deviceChange=[nic])
        self._host.vcenter.wait_for_tasks([self.content.ReconfigVM_Task(config)])

    def _wait_for_heartbeat(self, timeout: int = HEARTBEAT_TIMEOUT, interval: int = INTERVAL_TIMEOUT) -> bool:
        """
        Wait for os guest heartbeat.

        :param timeout: Timeout for heartbeat.
        :param interval: Interval between checks.

        :return: True if guest is running otherwise False.
        """
        heartbeat_time = 0
        while heartbeat_time < timeout:
            if self.content.guestHeartbeatStatus == vim.ManagedEntity.Status.green:
                break
            sleep(interval)
            heartbeat_time += interval
        return self.content.guestHeartbeatStatus == vim.ManagedEntity.Status.green

    def _wait_for_power_state(
        self,
        state: vim.VirtualMachine.PowerState,
        timeout: int = POWER_STATE_TIMEOUT,
        interval: int = INTERVAL_TIMEOUT,
    ) -> bool:
        """
        Wait for power state.

        :param state: Power state.
        :param timeout: Timeout for power state.
        :param interval: Interval between checks.

        :return: True if machine is in expected power state.
        """
        power_state_time = 0
        while power_state_time < timeout:
            if self.power_state == state:
                break
            sleep(interval)
            power_state_time += interval
        return self.power_state == state
