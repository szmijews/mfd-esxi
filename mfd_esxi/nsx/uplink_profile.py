# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX Uplink Profile."""
from com.vmware.nsx_policy.model_client import (
    PolicyUplinkHostSwitchProfile,
    TeamingPolicy,
    Uplink,
)

from .base import NsxEntity
from .utils import api_call
from ..const import ESXI_UPLINK_FORMAT, ESXI_UPLINK_NUMBER


class NsxUplinkProfile(NsxEntity):
    """NSX Uplink profile."""

    @api_call
    def _get_content(self) -> PolicyUplinkHostSwitchProfile:
        return self._connection.api.policy.infra.HostSwitchProfiles.get(self.name)

    @api_call
    def add(
        self,
        uplinks: int = ESXI_UPLINK_NUMBER,
        policy: str = TeamingPolicy.POLICY_LOADBALANCE_SRCID,
        transport_vlan: int | None = None,
        overlay_encap: str | None = None,
    ) -> None:
        """
        Add or replace Uplink Profile to NSX.

        :param uplinks: number of uplinks
        :param policy: teaming policy
        :param transport_vlan: VLAN tag or None
        :param overlay_encap: when using overlay option of GENEVE or VXLAN
        """
        active_list = []
        for i in range(1, uplinks + 1):
            uplink = Uplink(uplink_name=ESXI_UPLINK_FORMAT % i, uplink_type=Uplink.UPLINK_TYPE_PNIC)
            active_list.append(uplink)

        teaming = TeamingPolicy(active_list=active_list, standby_list=[], policy=policy)

        payload: PolicyUplinkHostSwitchProfile = self.content
        if payload is not None:
            payload = payload.convert_to(PolicyUplinkHostSwitchProfile)
            payload.teaming = teaming
            payload.transport_vlan = transport_vlan
            payload.overlay_encap = overlay_encap
        else:
            payload = PolicyUplinkHostSwitchProfile(
                id=self.name,
                resource_type=PolicyUplinkHostSwitchProfile.__name__,
                teaming=teaming,
                transport_vlan=transport_vlan,
                overlay_encap=overlay_encap,
            )

        self._connection.api.policy.infra.HostSwitchProfiles.patch(self.name, payload)

    @api_call
    def delete(self) -> None:
        """Delete Uplink Profile."""
        if self.content is None:
            return
        self._connection.api.policy.infra.HostSwitchProfiles.delete(self.name)

    @api_call
    def update_transport_vlan(self, transport_vlan: int) -> None:
        """
        Update Uplink Profile with transport VLAN.

        :param transport_vlan: VLAN tag
        """
        if self.content is None:
            raise ValueError("Uplink profile does not exist.")

        payload = self.content
        payload.transport_vlan = transport_vlan
        self._connection.api.policy.infra.HostSwitchProfiles.patch(self.name, payload)
