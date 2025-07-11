# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
# pylint: disable=protected-access
"""VirtualAdapter wrapper."""
import logging
from pyVmomi import vim
from typing import Union, TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level
from .exceptions import VCenterResourceMissing, VCenterResourceInUse

if TYPE_CHECKING:
    from .host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class VirtualAdapter(object):
    """VirtualAdapter wrapper."""

    _MTU_LOOKUP = {"default": 1500, "4k": 4074, "9k": 9000}

    def __init__(self, name: str, host: "Host"):
        """
        Initialize instance.

        :param name: Virtual adapter name.
        :param host: Host.
        """
        self._name = name
        self._host = host
        self.eth = name
        self.portgroup = None

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}') in {self._host}"

    def set_vlan(self, vlan_id: int) -> None:
        """
        Set vlan on portgroup associated with the Virtual Adapter.

        :param vlan_id: vlan number
        """
        self.portgroup.set_vlan(vlan_id)

    @property
    def content(self) -> "vim.host.VirtualNic":
        """Get content of VirtualNetworkAdapter."""
        for virtual_nic in self._host.content.config.network.vnic:
            if virtual_nic.device == self.name:
                return virtual_nic
        raise VCenterResourceMissing(self)

    @property
    def name(self) -> str:
        """Get name for VirtualAdapter."""
        return self._name

    def destroy(self) -> None:
        """Destroy vnic."""
        try:
            self._host.content.configManager.networkSystem.RemoveVirtualNic(self.name)
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Virtual Adapter: {self.name} does not exist.",
            )

    @property
    def mac(self) -> str:
        """MAC value for virtual adapter."""
        return self.content.spec.mac

    @property
    def ip(self) -> str:
        """Get IP value for virtual adapter."""
        if self.content.spec.ip.ipAddress and not self.content.spec.ip.ipAddress.startswith("169."):
            return self.content.spec.ip.ipAddress
        elif self.content.spec.ip.ipV6Config.ipV6Address:
            ips = self.content.spec.ip.ipV6Config.ipV6Address
            for ipv6 in ips:
                if not ipv6.ipAddress.lower().startswith("fe80"):
                    return ipv6.ipAddress
            return ""
        else:
            return ""

    @property
    def mask(self) -> Union[int, str]:
        """Get MASK for IPv4 or prefixLenght for IPv6 for virtual adapter."""
        if self.content.spec.ip.ipAddress and not self.content.spec.ip.ipAddress.startswith("169."):
            return self.content.spec.ip.subnetMask
        elif self.content.spec.ip.ipV6Config.ipV6Address:
            ips = self.content.spec.ip.ipV6Config.ipV6Address
            for ipv6 in ips:
                if not ipv6.ipAddress.lower().startswith("fe80"):
                    return ipv6.prefixLength
            return ""
        else:
            return ""

    @property
    def mtu(self) -> int:
        """Get MTU value for virtual adapter."""
        return self.content.spec.mtu

    @mtu.setter
    def mtu(self, value: Union[int, str]) -> None:
        """
        Set MTU value for virtual adapter.

        :param value: MTU value.
        """
        spec = self.content.spec
        spec.mtu = self._MTU_LOOKUP.get(value) if value in self._MTU_LOOKUP.keys() else int(value)
        self._host.content.configManager.networkSystem.UpdateVirtualNic(self.name, spec)

    @property
    def tso(self) -> bool:
        """
        Get TSO value for virtual adapter.

        :rtype: bool
        """
        return self.content.spec.tsoEnabled

    @tso.setter
    def tso(self, value: bool) -> None:
        """
        Set TSO value for virtual adapter.

        :param value: TSO value True or False.
        """
        spec = self.content.spec
        spec.tsoEnabled = value
        self._host.content.configManager.networkSystem.UpdateVirtualNic(self.name, spec)

    @property
    def vmotion(self) -> bool:
        """Get value vmotion for virtual adapter."""
        return self._get_property(vim.host.VirtualNicManager.NicType.vmotion)

    @vmotion.setter
    def vmotion(self, value: bool) -> None:
        """
        Set vmotion for virtual adapter.

        :param value: True or False.
        """
        self._set_property(vim.host.VirtualNicManager.NicType.vmotion, value)

    @property
    def management(self) -> bool:
        """Get management value for virtual adapter."""
        return self._get_property(vim.host.VirtualNicManager.NicType.management)

    @management.setter
    def management(self, value: bool) -> None:
        """
        Set management for virtual adapter.

        :param value: True or False.
        """
        self._set_property(vim.host.VirtualNicManager.NicType.management, value)

    @property
    def vsan(self) -> bool:
        """Get vsan value for virtual adapter."""
        return self._get_property(vim.host.VirtualNicManager.NicType.vsan)

    @vsan.setter
    def vsan(self, value: bool) -> None:
        """
        Set vsan for virtual adapter.

        :param value: True or False.
        """
        self._set_property(vim.host.VirtualNicManager.NicType.vsan, value)

    @property
    def provisioning(self) -> bool:
        """Get provisioning value for virtual adapter."""
        return self._get_property(vim.host.VirtualNicManager.NicType.vSphereProvisioning)

    @provisioning.setter
    def provisioning(self, value: bool) -> None:
        """Set provisioning for virtual adapter.

        :param value: True or False.
        """
        self._set_property(vim.HostVirtualNicManagerNicType.vSphereProvisioning, value)

    def _get_property(self, nic_type: vim.host.VirtualNicManager.NicType) -> bool:
        """
        Get property value from virtual adapter.

        :param nic_type: Type of property that we want to get.

        :return: Return True if is enabled otherwise false.
        """
        nic_type = str(nic_type)
        query = self._host.content.configManager.virtualNicManager.QueryNetConfig(nic_type)
        vnic = f"{nic_type}.key-vim.host.VirtualNic-{self.name}"
        return vnic in set(query.selectedVnic)

    def _set_property(self, nic_type: vim.host.VirtualNicManager.NicType, value: bool) -> None:
        """
        Set the property value for virtual adapter.

        :param nic_type: Type of property that we want to set.
        :param value: True or False.
        """
        if value:
            self._host.content.configManager.virtualNicManager.SelectVnic(str(nic_type), self.name)
        else:
            self._host.content.configManager.virtualNicManager.DeselectVnic(str(nic_type), self.name)

    @classmethod
    def get_mtu(cls: "VirtualAdapter", mtu: Union[str, int]) -> int:
        """
        Get MTU as int. Legacy method, to be deprecated.

        :param mtu: MTU.

        :return: MTU.
        """
        return cls._MTU_LOOKUP.get(mtu) if mtu in cls._MTU_LOOKUP.keys() else int(mtu)
