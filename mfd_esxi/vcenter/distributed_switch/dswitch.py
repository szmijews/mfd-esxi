# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""DSwitch wrapper."""
import logging
from pyVmomi import vim
from typing import Iterator, Optional, Union, Any, Generator, List, TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level

from .uplink import DSUplink
from .portgroup import DSPortgroup, DSP_EARLY_BINDING
from ..exceptions import VCenterResourceInUse, VCenterResourceMissing
from ..utils import get_obj_from_iter
from ...const import ESXI_UPLINK_FORMAT

if TYPE_CHECKING:
    from ..datacenter import Datacenter
    from ..host import Host
    from ..vcenter import VCenter

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class DSwitch(object):
    """DSwitch wrapper."""

    _MTU_LOOKUP = {"default": 1500, "4k": 4074, "9k": 9000}

    def __init__(self, name: str, datacenter: "Datacenter"):
        """
        Initialize instance.

        :param name: Name of dswitch.
        :param datacenter: Datacenter.
        """
        self._name = name
        self._datacenter = datacenter

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> vim.dvs.VmwareDistributedVirtualSwitch:
        """Get content of DS in API."""
        return get_obj_from_iter(
            self._datacenter.vcenter.create_view(
                self._datacenter.network_folder,
                [vim.dvs.VmwareDistributedVirtualSwitch],
            ),
            self.name,
        )

    @property
    def name(self) -> str:
        """Get name of DSwitch."""
        return self._name

    @property
    def uuid(self) -> str:
        """Get UUID of DSwitch."""
        return self.content.uuid

    def destroy(self) -> None:
        """Remove DSwitch from datacenter."""
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Destroying DSwitch: {self.name}")
        try:
            for pg in self.portgroups:
                pg.destroy()
            for uplink in self.uplinks:
                uplink.del_all_nics()
            for host in self.hosts:
                self.remove_host(host)
            self.vcenter.wait_for_tasks([self.content.Destroy()])
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"DSwitch: {self.name} destroyed")
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except VCenterResourceMissing:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. DSwitch: {self.name} does not exist.",
            )

    @property
    def vcenter(self) -> "VCenter":
        """Get VCenter for this dswitch."""
        return self._datacenter.vcenter

    @property
    def mtu(self) -> int:
        """MTU value from vSwitch."""
        return self.content.config.maxMtu

    @mtu.setter
    def mtu(self, value: Union[str, int]) -> None:
        """
        Set MTU value for DSwitch.

        :param value: MTU value.
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Set MTU {value} on {self.name}")
        ds_spec = self.get_ds_config_spec()
        max_mtu = self._MTU_LOOKUP.get(value) if value in self._MTU_LOOKUP.keys() else int(value)
        ds_spec.maxMtu = max_mtu
        self.vcenter.wait_for_tasks([self.content.ReconfigureDvs_Task(ds_spec)])

    def discovery_protocol_type(self, name: str) -> None:
        """
        Set Discovery Protocol type on DSwitch.

        :param name: Name of DSwitch.
        """
        dvswitch = self._datacenter.get_dswitch_by_name(name)
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"DSwitch: {name} already exist return existing: Dswitch:{dvswitch}",
        )
        protocol_config = vim.host.LinkDiscoveryProtocolConfig()
        protocol_config.protocol = vim.host.LinkDiscoveryProtocolConfig.ProtocolType.lldp
        self._enable_link_discovery_advertise(protocol_config)

    def _enable_link_discovery_advertise(self, protocol_config: vim.host.LinkDiscoveryProtocolConfig) -> None:
        """
        Enable Link Discovery Protocol advertising settings on a Distributed vSwitch.

        :param protocol_config: Configuration specifying the selected Link Discovery Protocol to use for this switch.
        """
        protocol_config.operation = vim.host.LinkDiscoveryProtocolConfig.OperationType.listen

        config_spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec(
            configVersion=self.content.config.configVersion,
            linkDiscoveryProtocolConfig=protocol_config,
        )
        self.vcenter.wait_for_tasks([self.content.ReconfigureDvs_Task(config_spec)])

    @property
    def portgroups(self) -> Generator["DSPortgroup", Any, None]:
        """Get all portgroups from DS."""
        return (
            DSPortgroup(pg.name, self)
            for pg in self.content.portgroup
            if isinstance(pg, vim.dvs.DistributedVirtualPortgroup) and len(pg.tag) == 0
        )

    def get_portgroup(self, name: str) -> "DSPortgroup":
        """
        Get specific portgroup from DS.

        :param name: Name of portgroup.

        :return: Portgroup.
        """
        return get_obj_from_iter(self.portgroups, name)

    def add_portgroup(self, name: str, num_ports: int = 8, port_binding: str = DSP_EARLY_BINDING) -> "DSPortgroup":
        """
        Add new portgroup to DS.

        :param name: Name of portgroup.
        :param num_ports: Number of ports.
        :param port_binding: Type of port binding early binding/late binding/ephemeral.

        :return: Portgroup.
        """
        dsp = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
        dsp.name = name
        dsp.numPorts = num_ports
        dsp.type = port_binding
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"New portgroup: {name} for DSwitch {self.name} spec\n{dsp}",
        )
        try:
            self.vcenter.wait_for_tasks([self.content.AddDVPortgroup_Task([dsp])])
        except vim.fault.DuplicateName:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Portgroup: {name} already exist return existing.",
            )
        return DSPortgroup(name, self)

    @property
    def uplinks(self) -> Generator["DSUplink", Any, None]:
        """Get all uplinks."""
        return (
            DSUplink(name, nr, self) for nr, name in enumerate(self.content.config.uplinkPortPolicy.uplinkPortName)
        )

    def get_uplink(self, name: str) -> "DSUplink":
        """
        Get specific uplink from DS.

        :param name: Name of uplink.

        :return: Uplink.
        """
        return get_obj_from_iter(self.uplinks, name)

    @property
    def hosts(self) -> Generator["Host", Any, None]:
        """Get all assigned hosts to DS."""
        return (
            host
            for host in self._datacenter.hosts
            for dvs_host in self.content.config.host
            if host.name == dvs_host.config.host.name
        )

    def get_host(self, name: str) -> Optional["Host"]:
        """
        Get specific host from DS.

        :param name: Name of host.

        :return: Host.
        :raise ObjectNotFoundInIter: Host was not found
        """
        return get_obj_from_iter(self.hosts, name)

    def assign_host(self, host: "Host") -> None:
        """
        Assign to DSwitch new host.

        :param host: Host that should be assigned to DS.
        """
        try:
            self._remove_add_host(host, vim.ConfigSpecOperation.add)
        except vim.fault.AlreadyExists:
            pass

    def remove_host(self, host: "Host") -> None:
        """
        Remove from DSwitch host.

        :param host: Host that should be removed from DS.
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Remove host: {host} from DVSwitch: {self.name}",
        )
        self._remove_add_host(host, vim.ConfigSpecOperation.remove)

    def _remove_add_host(self, host: "Host", operation: str) -> None:
        """
        Remove or add host to DSwitch.

        :param host: Host.
        :param operation: Operation type (add/remove).
        """
        ds_spec = self.get_ds_config_spec()
        ds_spec.host = [self.get_ds_host_config_spec(host, operation)]
        self.vcenter.wait_for_tasks([self.content.ReconfigureDvs_Task(ds_spec)])

    def get_ds_config_spec(self) -> vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec:
        """
        Return DSwitch config spec.

        :return: DSwitch config spec.
        """
        ds_spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
        ds_spec.configVersion = self.content.config.configVersion
        return ds_spec

    @staticmethod
    def get_ds_host_config_spec(host: "Host", operation: str) -> vim.dvs.HostMember.ConfigSpec:
        """
        Return DSwitch host config spec.

        :param host: Host.
        :param operation: Operation type (add/remove).

        :return: Host member config spec.
        """
        host_spec = vim.dvs.HostMember.ConfigSpec()
        host_spec.operation = operation
        host_spec.host = host.content
        return host_spec

    @property
    def networkIO(self) -> bool:
        """Get Network I/O Control."""
        return self.content.config.networkResourceManagementEnabled

    @networkIO.setter
    def networkIO(self, value: bool) -> None:
        """Set Network I/O Control.

        :param value: enable/disable Network I/O Control.
        """
        self.content.EnableNetworkResourceManagement(value)

    def set_active_standby(self, active: List[str], standby: List[str]) -> None:
        """
        Set active and standby uplinks.

        :param active: Active nics.
        :param standby: Standby nics.
        """
        ds_spec = self.get_ds_config_spec()
        ds_spec.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
        ds_spec.defaultPortConfig.uplinkTeamingPolicy = (
            vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortTeamingPolicy()
        )
        ds_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder = (
            vim.dvs.VmwareDistributedVirtualSwitch.UplinkPortOrderPolicy()
        )

        active_uplinks = []
        for i in range(1, len(active) + 1, 1):
            active_uplinks.append(ESXI_UPLINK_FORMAT % i)
        standby_uplinks = []
        for i in range(len(active) + 1, len(active + standby) + 1, 1):
            standby_uplinks.append(ESXI_UPLINK_FORMAT % i)

        ds_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort = active_uplinks
        ds_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort = standby_uplinks
        self.vcenter.wait_for_tasks([self.content.ReconfigureDvs_Task(ds_spec)])

    def add_lag(
        self,
        name: str,
        uplinks_no: int,
        lacp_mode: str = "passive",
        lb_algorithm: str = "srcDestIpTcpUdpPortVlan",
    ) -> None:
        """
        Create link aggregation portgroup.

        :param name: Name of LAG.
        :param uplinks_no: Number of uplinks.
        :param lacp_mode: LACP protocol mode, "active" or "passive".
        :param lb_algorithm: Load balancing algorithm used on LAG.
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"[API] Adding LAG {name}")
        lacp_spec = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupSpec()
        lacp_spec.lacpGroupConfig = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupConfig()
        lacp_spec.lacpGroupConfig.ipfix = vim.dvs.VmwareDistributedVirtualSwitch.LagIpfixConfig()
        lacp_spec.lacpGroupConfig.vlan = vim.dvs.VmwareDistributedVirtualSwitch.LagVlanConfig()
        lacp_spec.lacpGroupConfig.name = name
        lacp_spec.lacpGroupConfig.uplinkNum = uplinks_no
        lacp_spec.lacpGroupConfig.mode = lacp_mode
        lacp_spec.lacpGroupConfig.loadbalanceAlgorithm = lb_algorithm
        lacp_spec.operation = "add"

        lacp_spec = [lacp_spec]
        self.content.UpdateDVSLacpGroupConfig_Task(lacp_spec)

    def remove_lag(self, name: str) -> None:
        """
        Remove link aggregation portgroup.

        :param name: Name of LAG.
        """
        lacp_spec = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupSpec()
        lacp_spec.lacpGroupConfig = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupConfig()
        lacp_object = get_obj_from_iter(self.content.config.lacpGroupConfig, name=name)
        lacp_spec.lacpGroupConfig.key = lacp_object.key
        lacp_spec.operation = "remove"
        lacp_spec = [lacp_spec]
        self.content.UpdateDVSLacpGroupConfig_Task(lacp_spec)

    def update_lag_uplinks(self, host: "Host", adapters_names: Iterator[str], lag_port_keys: Iterator[int]) -> None:
        """
        Update uplink in link aggregation portgroup.

        :param host: Name of LAG.
        :param adapters_names: Name of uplink NICs.
        :param lag_port_keys: LAG port keys.
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"[API] Adding {adapters_names} as uplinks to LAG",
        )

        uplink_pg_name = next((pg.key for pg in self.content.portgroup if "Uplinks" in pg.name), None)

        config = vim.host.NetworkConfig()
        proxy_switch_config = vim.host.HostProxySwitch.Config()
        proxy_switch_config.uuid = self.content.uuid  # ? self.uuid ?
        proxy_switch_config.changeOperation = "edit"
        proxy_switch_config.spec = vim.host.HostProxySwitch.Specification()
        proxy_switch_config.spec.backing = vim.dvs.HostMember.PnicBacking()
        proxy_switch_config.spec.backing.pnicSpec = []
        for name, lag_port in zip(adapters_names, lag_port_keys):
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"[API] Add {name} to LAG")
            host_pnic_spec = vim.dvs.HostMember.PnicSpec()
            host_pnic_spec.pnicDevice = name
            host_pnic_spec.uplinkPortKey = lag_port
            host_pnic_spec.uplinkPortgroupKey = uplink_pg_name
            proxy_switch_config.spec.backing.pnicSpec.append(host_pnic_spec)
        config.proxySwitch = [proxy_switch_config]
        host.update_network_backing(config)
