# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Host wrapper."""
import logging
from typing import Optional, Any, Generator, TYPE_CHECKING
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from .virtual_machine import VirtualMachine
from .virtual_switch.vswitch import VSwitch
from .datastore import Datastore
from .exceptions import VCenterResourceInUse
from .utils import get_obj_from_iter

if TYPE_CHECKING:
    from .cluster import Cluster
    from .datacenter import Datacenter
    from .vcenter import VCenter

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class Host(object):
    """Host wrapper."""

    def __init__(self, name: str, datacenter: "Datacenter", cluster: Optional["Cluster"] = None):
        """
        Initialize instance.

        :param name: Name of host.
        :param datacenter: Datacenter.
        :param cluster: Cluster.
        """
        self._name = name
        self._datacenter = datacenter
        self._cluster = cluster

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> "vim.HostSystem":
        """Get content of host in API."""
        return get_obj_from_iter(
            self.vcenter.create_view(self._datacenter.content.hostFolder, [vim.HostSystem], True),
            self.name,
        )

    @property
    def name(self) -> str:
        """Get name of host."""
        return self._name

    def destroy(self) -> None:
        """Remove host from datacenter of cluster."""
        try:
            if not self._cluster:
                self.vcenter.wait_for_tasks([self.content.parent.Destroy()])
            else:
                raise VCenterResourceInUse(self, "Can't remove host connected to cluster.")
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Host: {self.name} does not exist.",
            )

    @property
    def vcenter(self) -> "VCenter":
        """Get VCenter for this host."""
        return self._datacenter.vcenter

    @property
    def datastores(self) -> Generator["Datastore", Any, None]:
        """Get all datastores from host."""
        return (Datastore(datastore.name, self) for datastore in self.content.datastore)

    @property
    def datacenter(self) -> "Datacenter":
        """Get host datacenter."""
        return self._datacenter

    def get_datastore_by_name(self, name: str) -> "Datastore":
        """
        Get specific datastore from VCenter.

        :param name: Name of datastore.

        :return: Datastore.
        """
        return get_obj_from_iter(self.datastores, name)

    @property
    def vswitches(self) -> Generator["VSwitch", Any, None]:
        """Get all vSwitches from host."""
        return (
            VSwitch(vs.name, self)
            for vs in self.content.config.network.vswitch
            if isinstance(vs, vim.host.VirtualSwitch)
        )

    def get_vswitch_by_name(self, name: str) -> "VSwitch":
        """
        Get specific vSwitch from host.

        :param name: Name of vSwitch.

        :return: vSwitch.
        """
        return get_obj_from_iter(self.vswitches, name)

    def add_vswitch(self, name: str, mtu: int = 1500, ports: int = 64) -> "VSwitch":
        """
        Add new vSwitch to host.

        :param name: Name of vSwitch
        :param mtu: MTU size.
        :param ports: Number of ports in vSwitch.

        :return: New vSwitch.
        """
        spec = vim.host.VirtualSwitch.Specification()
        spec.numPorts = ports
        spec.mtu = mtu
        try:
            self.content.configManager.networkSystem.AddVirtualSwitch(name, spec)
        except vim.fault.AlreadyExists:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"VSwitch: {name} already exist return existing",
            )
        return VSwitch(name, self)

    @property
    def vms(self) -> Generator["VirtualMachine", Any, None]:
        """Get all VMs for host."""
        return (VirtualMachine(vm.name, self) for vm in self.vcenter.create_view(self.content, [vim.VirtualMachine]))

    def get_vm(self, name: str) -> "VirtualMachine":
        """
        Get specific VM from host.

        :param name: Name of VM.

        :return: Virtual machine.
        """
        return get_obj_from_iter(self.vms, name)

    def update_network_backing(self, config: "vim.host.NetworkConfig") -> None:
        """
        Update host network backing.

        :param config: Host network backing configuration.
        """
        self.content.configManager.networkSystem.UpdateNetworkConfig(config, "modify")

    def get_connection_state(self) -> str:
        """
        Get connection state of the host added to the Datacenter.

        :return: Connection state of the host.
        """
        return str(self.content.runtime.connectionState)
