# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX Host Transport Node."""
from time import sleep, time
from typing import List

from mfd_esxi.exceptions import (
    NsxResourceSetupError,
    NsxResourcePartialSuccessSetupError,
    NsxResourceRemoveError,
    MissingNsxEntity,
)

from com.vmware.nsx_policy.model_client import (
    HostTransportNode,
    StandardHostSwitchSpec,
    VdsUplink,
    StandardHostSwitch,
    HostSwitchProfileTypeIdEntry,
    StaticIpPoolSpec,
    StaticIpv6PoolSpec,
    TransportZoneEndPoint,
    CpuCoreConfigForEnhancedNetworkingStackSwitch,
    AssignedByDhcp,
    TransportNodeState,
)
from com.vmware.vapi.std.errors_client import NotFound

from .base import NsxEntity
from .enforcement_point import NsxEnforcementPoint
from .fabric_discovered_node import NsxFabricDiscoveredNode
from .infra_site import NsxInfraSite
from .utils import api_call
from ..const import ESXI_UPLINK_FORMAT, ESXI_UPLINK_NUMBER


class NsxHostTransportNode(NsxEntity):
    """Host transport node."""

    @api_call
    def _get_content(self) -> HostTransportNode:
        return self._connection.api.policy.infra.sites.enforcement_points.HostTransportNodes.get(
            NsxInfraSite.DEFAULT_NAME, NsxEnforcementPoint.DEFAULT_NAME, self.name
        )

    def _patch(self, payload: HostTransportNode, timeout: int) -> str:
        self._connection.api.policy.infra.sites.enforcement_points.HostTransportNodes.patch(
            NsxInfraSite.DEFAULT_NAME,
            NsxEnforcementPoint.DEFAULT_NAME,
            self.name,
            payload,
        )

        t_end = timeout + time()

        while time() < t_end:
            r_state = self._connection.api.policy.infra.sites.enforcement_points.host_transport_nodes.State.get(
                NsxInfraSite.DEFAULT_NAME, NsxEnforcementPoint.DEFAULT_NAME, self.name
            )

            if r_state.node_deployment_state.state == TransportNodeState.STATE_SUCCESS:
                if r_state.state == TransportNodeState.STATE_SUCCESS:
                    return self.name
            elif r_state.node_deployment_state.state == TransportNodeState.STATE_FAILED:
                raise NsxResourceSetupError(r_state.to_json())
            elif r_state.node_deployment_state.state == TransportNodeState.STATE_PARTIAL_SUCCESS:
                raise NsxResourcePartialSuccessSetupError(r_state.to_json())
            sleep(10)

        raise NsxResourceSetupError(f"Timeout during operation on Host Transport Node {self.name}")

    @api_call
    def add(  # noqa: C901
        self,
        timeout: int = 600,
    ) -> None:
        """
        Add host transport node to NSX. Only hosts that are present in VCSA with VDS-es are supported.

        :param timeout: Maximum time add node can take to resolve.
        """
        if self.content is not None:
            return

        discovered_node = NsxFabricDiscoveredNode(self.name, self._connection).content
        if discovered_node is None:
            # Standalone ESXi hosts are not supported. They need to be present in discovery
            raise NsxResourceSetupError("Transport node missing in discovery")

        switch_specs = StandardHostSwitchSpec(host_switches=[])
        payload = HostTransportNode(
            discovered_node_id_for_create=discovered_node.external_id,
            display_name=self.name,
            host_switch_spec=switch_specs,
            description=f"Transport Node {self.name}",
        )

        self._patch(payload=payload, timeout=timeout)

    @api_call
    def add_switch(  # noqa: C901
        self,
        host_switch_name: str,
        uplink_name: str,
        transport_zone_name: str,
        vds_id: str,
        uplinks: int = ESXI_UPLINK_NUMBER,
        ip_pool_id: str | None = None,
        mode: str = StandardHostSwitch.HOST_SWITCH_MODE_STANDARD,
        lcore_mapping: List[CpuCoreConfigForEnhancedNetworkingStackSwitch] | None = None,
        lcores: int = 0,
        timeout: int = 600,
    ) -> None:
        """
        Add host transport node to NSX. Only hosts that are present in VCSA with VDS-es are supported.

        :param host_switch_name: Name of host switch to set
        :param uplink_name: Name of uplink profile
        :param transport_zone_name: Name of transport zone
        :param vds_id: ID of VDS (from VCSA). It looks like "50 03 bd df 08 0b cc d0-be 1a 5c 0e 16 87 7f a0"
        :param uplinks: number of uplinks
        :param ip_pool_id: ID of IP pool, for VLAN transport zone can be None
        :param mode: 'STANDARD', 'ENS' or 'ENS_INTERRUPT'
        :param lcore_mapping: CPU config. Will overwrite if provided alongside 'lcores'
        :param lcores: Logical cores count.
        :param timeout: Maximum time add node can take to resolve.
        """
        payload: HostTransportNode = self.content
        if payload is None:
            raise MissingNsxEntity(f"Host Transport Node {self.name} is missing")

        uplink_list = []
        for i in range(1, uplinks + 1):
            uplink_list.append(
                VdsUplink(
                    uplink_name=ESXI_UPLINK_FORMAT % i,
                    vds_uplink_name=ESXI_UPLINK_FORMAT % i,
                )
            )

        host_switch_profile_ids = [
            HostSwitchProfileTypeIdEntry(
                key=HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE,
                value=f"/infra/host-switch-profiles/{uplink_name}",
            )
        ]

        ip_assignment_spec = None
        ipv6_assignment_spec = None
        if ip_pool_id is None:
            ip_assignment_spec = AssignedByDhcp()
        else:
            if "IP4" in ip_pool_id:
                ip_assignment_spec = StaticIpPoolSpec(ip_pool_id=f"/infra/ip-pools/{ip_pool_id}")
            else:
                ipv6_assignment_spec = StaticIpv6PoolSpec(ipv6_pool_id=f"/infra/ip-pools/{ip_pool_id}")

        tz_path = f"/infra/sites/{NsxInfraSite.DEFAULT_NAME}/enforcement-points/{NsxEnforcementPoint.DEFAULT_NAME}/transport-zones/{transport_zone_name}"  # noqa: E501
        transport_zone_endpoints = [TransportZoneEndPoint(transport_zone_id=tz_path)]
        host_switch = StandardHostSwitch(
            host_switch_id=vds_id,
            host_switch_name=host_switch_name,
            host_switch_type=StandardHostSwitch.HOST_SWITCH_TYPE_VDS,
            uplinks=uplink_list,
            host_switch_mode=mode,
            host_switch_profile_ids=host_switch_profile_ids,
            ip_assignment_spec=ip_assignment_spec,
            ipv6_assignment_spec=ipv6_assignment_spec,
            transport_zone_endpoints=transport_zone_endpoints,
        )

        if mode == "ENS":
            if lcores > 0:
                lcore_mapping = [CpuCoreConfigForEnhancedNetworkingStackSwitch(num_lcores=lcores, numa_node_index=0)]

            if lcore_mapping is not None:
                host_switch.cpu_config = lcore_mapping

        switches = []
        if payload.host_switch_spec:
            for switch in payload.host_switch_spec.convert_to(StandardHostSwitchSpec).host_switches:
                if switch.host_switch_name != host_switch_name:
                    switches.append(switch)
        switches.append(host_switch)

        switch_specs = StandardHostSwitchSpec(host_switches=switches)
        payload.host_switch_spec = switch_specs

        self._patch(payload=payload, timeout=timeout)

    @api_call
    def delete_switches_return_uplink_profiles(self, timeout: int = 600) -> List[str]:
        """
        Delete all host switches.

        :param timeout: maximum time to resolve request
        :return: list of their uplink profiles
        """
        payload: HostTransportNode = self.content
        if payload is None or payload.host_switch_spec is None:
            return []

        names = []
        for switch in payload.host_switch_spec.convert_to(StandardHostSwitchSpec).host_switches:
            for up in switch.host_switch_profile_ids:
                if up.key == HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE:
                    names.append(up.value.split("/")[-1])

        payload.host_switch_spec = StandardHostSwitchSpec(host_switches=[])

        self._patch(payload=payload, timeout=timeout)

        return names

    @api_call
    def delete(self, unprepare_host: bool = True, force: bool = False, timeout: int = 600) -> None:
        """
        Remove host transport node from NSX.

        :param unprepare_host: True if NSX should be uninstalled from host.
        :param force: Force delete the resource even if it is being used somewhere.
        :param timeout: Maximum time add node can take to resolve.
        """
        if self.content is not None:  # If no content it was already removed, or never added. It is fine.
            self._connection.api.policy.infra.sites.enforcement_points.HostTransportNodes.delete(
                NsxInfraSite.DEFAULT_NAME,
                NsxEnforcementPoint.DEFAULT_NAME,
                self.name,
                unprepare_host=unprepare_host,
                force=force,
            )

        t_end = timeout + time()

        while t_end > time():
            try:
                rslv = self._connection.api.policy.infra.sites.enforcement_points.host_transport_nodes.State.get(
                    NsxInfraSite.DEFAULT_NAME,
                    NsxEnforcementPoint.DEFAULT_NAME,
                    self.name,
                ).node_deployment_state
            except NotFound:
                return
            if rslv.state == TransportNodeState.STATE_FAILED:
                raise NsxResourceRemoveError(rslv.to_json())

        raise NsxResourceRemoveError(f"Timeout on remove Host Transport Node {self.name}")

    @api_call
    def update_lcores(
        self,
        host_switch_name: str,
        lcore_mapping: List[CpuCoreConfigForEnhancedNetworkingStackSwitch] | None = None,
        lcores: int = 0,
        timeout: int = 600,
    ) -> None:
        """
        Update host transport node.

        :param host_switch_name: Name of host switch to set
        :param lcore_mapping: CPU config. Will overwrite if provided alongside 'lcores'
        :param lcores: Logical cores count.
        :param timeout: Maximum time add node can take to resolve.
        """
        payload: HostTransportNode = self.content
        if payload is None:
            raise MissingNsxEntity(f"Host Transport Node {self.name} is missing")

        switches = []
        if payload.host_switch_spec:
            for switch in payload.host_switch_spec.convert_to(StandardHostSwitchSpec).host_switches:
                if switch.host_switch_name == host_switch_name:
                    if switch.host_switch_mode == "ENS":
                        if lcores > 0:
                            lcore_mapping = [
                                CpuCoreConfigForEnhancedNetworkingStackSwitch(num_lcores=lcores, numa_node_index=0)
                            ]
                        if lcore_mapping is not None:
                            switch.cpu_config = lcore_mapping

                switches.append(switch)

        switch_specs = StandardHostSwitchSpec(host_switches=switches)
        payload.host_switch_spec = switch_specs

        self._patch(payload=payload, timeout=timeout)
