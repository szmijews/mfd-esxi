# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""VSwitch wrapper."""
import logging
from typing import Any, Generator, Union, TYPE_CHECKING
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from ..utils import get_obj_from_iter
from ..exceptions import VCenterResourceInUse
from ..virtual_adapter import VirtualAdapter

if TYPE_CHECKING:
    from ..host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class VSPortgroup(object):
    """VSwitch wrapper."""

    def __init__(self, name: str, host: "Host"):
        """
        Initialize instance.

        :param name: Name of portgroup.
        :param host: Host.
        """
        self._name = name
        self._host = host

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def name(self) -> str:
        """Name for portgroup."""
        return self._name

    def destroy(self) -> None:
        """Destroy VSPortgroup and remove virtual adapter connected to the portgroup."""
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Removing portgroup: {self.name}")
        try:
            for virtual_adapter in self.virtual_adapters:
                virtual_adapter.destroy()
            self._host.content.configManager.networkSystem.RemovePortGroup(self.name)
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Portgroup {self.name} destroyed")
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Portgroup: {self.name} does not exist.",
            )

    @property
    def virtual_adapters(self) -> Generator["VirtualAdapter", Any, None]:
        """
        Get all virtual adapters from vSwitch.

        :return: Generator with all adapters.
        """
        return (
            VirtualAdapter(virtual_nic.device, self._host)
            for virtual_nic in self._host.content.config.network.vnic
            if virtual_nic.portgroup == self.name
        )

    def get_virtual_adapter_by_name(self, name: str) -> "VirtualAdapter":
        """
        Get specific virtual adapter from vSwitch.

        :param name: Name of virtual adapter.

        :return: Virtual adapter.
        """
        return get_obj_from_iter(self.virtual_adapters, name)

    def add_virtual_adapter(self, mtu: int = 1500, ip: Union[str, int] = None, mask: str = None) -> "VirtualAdapter":
        """
        Add new virtual adapter to portgroup when ip is none and mask use DHCP.

        :param mtu: MTU size for virtual adapter.
        :param ip: IP address
        :param mask: Netmask for IP

        :return: Newly added virtual adapter.
        """
        ip_config = vim.host.IpConfig()

        if ip and mask:
            ip_config.dhcp = False
            ip_config.ipAddress = ip
            ip_config.subnetMask = mask
        elif not ip and not mask:
            ip_config.dhcp = True
        else:
            raise RuntimeError("Unknown config please set both IP and netmask or none.")

        virtual_nic_spec = vim.host.VirtualNic.Specification()
        virtual_nic_spec.ip = ip_config
        virtual_nic_spec.mtu = VirtualAdapter.get_mtu(mtu)

        name = self._host.content.configManager.networkSystem.AddVirtualNic(self.name, virtual_nic_spec)
        return self.get_virtual_adapter_by_name(name)
