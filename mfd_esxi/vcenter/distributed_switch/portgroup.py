# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""DSPorgroup wrapper."""
import logging
from typing import List, Union, Dict, Tuple

from pyVmomi import vim
from ipaddress import IPv4Network, IPv6Network
from typing import TYPE_CHECKING

from ..virtual_adapter import VirtualAdapter

from mfd_esxi.vcenter.exceptions import (
    VCenterResourceInUse,
    VCenterDSPortgroupMissingHostMember,
    VCenterResourceMissing,
)
from time import time, sleep
from mfd_common_libs import log_levels, add_logging_level

if TYPE_CHECKING:
    from .dswitch import DSwitch
    from .uplink import DSUplink
    from ..host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)

DSP_EARLY_BINDING = "earlyBinding"
DSP_LATE_BINDING = "lateBinding"
DSP_EPHEMERAL = "ephemeral"


class DSPortgroup(object):
    """DSPorgroup wrapper."""

    def __init__(self, name: str, dswitch: "DSwitch"):
        """
        Initialize instance.

        :param name: Name of portgroup.
        :param dswitch: DSwitch.
        """
        self._name = name
        self._dswitch = dswitch

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> vim.dvs.DistributedVirtualPortgroup:
        """Get content of DSPortgroup in API."""
        for pg in self._dswitch.content.portgroup:
            if pg.name == self._name and isinstance(pg, vim.dvs.DistributedVirtualPortgroup):
                return pg
        raise VCenterResourceMissing(self)

    @property
    def name(self) -> str:
        """Name for DSPortgroup."""
        return self._name

    def destroy(self) -> None:
        """Remove DSPortgroup from DSwitch."""
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Removing portgroup: {self.name}")
        try:
            for host in self._dswitch.hosts:
                for virtual_adapter in self.get_virtual_adapters(host):
                    virtual_adapter.destroy()
            self._dswitch.vcenter.wait_for_tasks([self.content.Destroy()])
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Portgroup {self.name} destroyed")
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Portgroup: {self.name} does not exist.",
            )

    def get_virtual_adapters(self, host: "Host") -> list[VirtualAdapter]:
        """
        Get all virtual adapters from DS created on spec host.

        :param host: Host where virtual adapters was created.

        :return: List of virtual adapters.
        """
        virtual_adapters = []
        for virtual_nic in host.content.config.network.vnic:
            dvp = virtual_nic.spec.distributedVirtualPort
            if dvp and dvp.portgroupKey == self.content.key:
                virtual_adapters.append(VirtualAdapter(virtual_nic.device, host))
        return virtual_adapters

    def get_virtual_adapter_by_name(self, host: "Host", name: str) -> VirtualAdapter:
        """
        Get virtual adapter from DS created on spec host.

        :param host: Host where virtual adapter was created.
        :param name: Name of virtual adapter.

        :return: Virtual adapter.
        """
        for virtual_adapter in self.get_virtual_adapters(host):
            if virtual_adapter.name == name:
                return virtual_adapter
        raise RuntimeError(f"Virtual adapter {name} does not exist.")

    def add_virtual_adapter(  # noqa: C901
        self,
        host: "Host",
        mtu: Union[str, int] = "default",
        ip_ver: str = "4",
        ip: str = None,
        mask: str = None,
    ) -> VirtualAdapter:
        """
        Add new virtual adapter to portgroup.If ip and mask is None use DHCP.

        :param host: Host to which add adapter.
        :param mtu: MTU size for virtual adapter.
        :param ip_ver: IP version 4|6.
        :param ip: IP address.
        :param mask: Netmask for IP.

        :return: New Virtual adapter.
        """
        ip_ver = int(ip_ver)
        ip_config = vim.host.IpConfig()
        ipv6_config = vim.host.IpConfig.IpV6AddressConfiguration()

        if ip and mask:
            ip_net = IPv4Network(f"{ip}/{mask}") if ip_ver == 4 else IPv6Network(f"{ip}/{mask}")
            if ip_ver == 4 and mask:
                ip_config.dhcp = False
                ip_config.ipAddress = ip
                ip_config.subnetMask = f"{ip_net.netmask}"
            elif ip_ver == 6 and mask:
                ip_config.ipV6Config = ipv6_config
                ipv6_config.autoConfigurationEnabled = False
                ipv6_config.dhcpV6Enabled = False
                ipv6_address = vim.host.IpConfig.IpV6Address()
                ipv6_address.ipAddress = ip
                ipv6_address.prefixLength = int(mask)
                ipv6_config.ipV6Address = [ipv6_address]
        elif not ip and not mask:
            if ip_ver == 4:
                ip_config.dhcp = True
            elif ip_ver == 6:
                ip_config.dhcp = False
                ip_config.ipV6Config = ipv6_config
                ipv6_config.autoConfigurationEnabled = True
                ipv6_config.dhcpV6Enabled = False
        else:
            raise RuntimeError("Unknown config please set both IP and netmask or none.")

        port_connection = vim.dvs.PortConnection()
        port_connection.portgroupKey = self.content.key
        port_connection.switchUuid = self.content.config.distributedVirtualSwitch.uuid

        virtual_nic_spec = vim.host.VirtualNic.Specification()
        virtual_nic_spec.ip = ip_config
        virtual_nic_spec.mtu = VirtualAdapter.get_mtu(mtu)
        virtual_nic_spec.distributedVirtualPort = port_connection

        for host_member in self._dswitch.content.config.host:
            if host_member.config.host.name == host.name:
                name = host.content.configManager.networkSystem.AddVirtualNic("", virtual_nic_spec)
                adapter = self.get_virtual_adapter_by_name(host, name)
                start = time()
                while time() - start < 60:
                    if adapter.ip:
                        return self.get_virtual_adapter_by_name(host, name)
                    logger.log(level=log_levels.MODULE_DEBUG, msg="Adapter has not assigned IP")
                    sleep(5)
                raise RuntimeError("Adapter has not assigned IP")
        raise VCenterDSPortgroupMissingHostMember()

    @property
    def uplinks(self) -> Dict[str, List["DSUplink"]]:
        """
        Get all uplinks assigned to portgroup.

        Sample output:
        'active': [DSUplink('Uplink 0'), DSUplink('Uplink 1')],
        'standby': DSUplink('Uplink 2'), DSUplink('Uplink 3')
        """
        uplink_port_order = self.content.config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder
        return {
            "active": [
                uplink for uplink in self._dswitch.uplinks if uplink.name in uplink_port_order.activeUplinkPort
            ],
            "standby": [
                uplink for uplink in self._dswitch.uplinks if uplink.name in uplink_port_order.standbyUplinkPort
            ],
        }

    @uplinks.setter
    def uplinks(self, value: Dict[str, List["DSUplink"]]) -> None:
        """
        Set uplinks for the portgrup.

        Sample input:
        {'active': [DSUplink('Uplink 0'), DSUplink('Uplink 1')],
        'standby': DSUplink('Uplink 2'), DSUplink('Uplink 3')}

        :param value: Dict of list with uplink.
        """
        dsp_config = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
        dsp_config.configVersion = self.content.config.configVersion

        dsp_config.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()

        dsp_config.defaultPortConfig.uplinkTeamingPolicy = (
            vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortTeamingPolicy()
        )

        dsp_config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder = (
            vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortOrderPolicy()
        )

        active = value.get("active", [])
        standby = value.get("standby", [])
        uplink_port_order = dsp_config.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder

        uplink_port_order.activeUplinkPort = [uplink.name for uplink in active]
        uplink_port_order.standbyUplinkPort = [uplink.name for uplink in standby]
        self._dswitch.vcenter.wait_for_tasks([self.content.ReconfigureDVPortgroup_Task(dsp_config)])

    @property
    def vlan(self) -> Union[int, vim.NumericRange]:
        """VLAN setting on portgroup."""
        return self.content.config.defaultPortConfig.vlan.vlanId

    @vlan.setter
    def vlan(self, value: Union[int, str, List[int], Tuple[int]]) -> None:
        """
        Set VLAN on portgroup. If value is int or str - set vlan tag. If value is tuple or list - set trunking vlan.

        :param value: VLAN.
        """
        dsp_config = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
        dsp_config.configVersion = self.content.config.configVersion
        dsp_config.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
        if isinstance(value, list) or isinstance(value, tuple):
            dsp_config.defaultPortConfig.vlan = vim.dvs.VmwareDistributedVirtualSwitch.TrunkVlanSpec()
            vlanId = [vim.NumericRange(start=int(start), end=int(end)) for start, end in value]
            dsp_config.defaultPortConfig.vlan.vlanId = vlanId
        else:
            dsp_config.defaultPortConfig.vlan = vim.dvs.VmwareDistributedVirtualSwitch.VlanIdSpec()
            dsp_config.defaultPortConfig.vlan.vlanId = int(value)
        self._dswitch.vcenter.wait_for_tasks([self.content.ReconfigureDVPortgroup_Task(dsp_config)])

    def set_vlan(self, value: Union[int, str, List[int], Tuple[int]]) -> None:
        """
        Set VLAN on portgroup. Method created to keep compatibility between standard portgroup and ds portgroup.

        :param value: Vlan to set.
        """
        if value == 4095:
            self.vlan = [(0, 4094)]
        else:
            self.vlan = value

    def set_forged_transmit(self, status: bool) -> None:
        """
        Set Forged transmit parameter on Distributed portgroup.

        :param status: Desired status of DS Forged transmits parameter, True - Accept, False - Deny.
        """
        dsp_config = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
        dsp_config.configVersion = self.content.config.configVersion
        dsp_config.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
        dsp_config.defaultPortConfig.securityPolicy = vim.dvs.VmwareDistributedVirtualSwitch.SecurityPolicy()
        dsp_config.defaultPortConfig.securityPolicy.forgedTransmits = vim.BoolPolicy()
        dsp_config.defaultPortConfig.securityPolicy.forgedTransmits.value = status

        self._dswitch.vcenter.wait_for_tasks([self.content.ReconfigureDVPortgroup_Task(dsp_config)])
