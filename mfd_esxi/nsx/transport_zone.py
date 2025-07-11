# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX Transport Zone."""
from com.vmware.nsx_policy.model_client import PolicyTransportZone
from ..exceptions import UnsupportedNsxEntity

from .base import NsxEntity
from .enforcement_point import NsxEnforcementPoint
from .infra_site import NsxInfraSite
from .utils import api_call


class NsxTransportZone(NsxEntity):
    """NSX Transport Zone."""

    @api_call
    def _get_content(self) -> PolicyTransportZone:
        return self._connection.api.policy.infra.sites.enforcement_points.TransportZones.get(
            NsxInfraSite.DEFAULT_NAME, NsxEnforcementPoint.DEFAULT_NAME, self.name
        )

    @api_call
    def add(
        self,
        transport_type: str = PolicyTransportZone.TZ_TYPE_VLAN_BACKED,
    ) -> None:
        """
        Add Transport Zone to NSX.

        :param transport_type: Type of transport zone.
        :param forwarding_mode: Forwarding mode for the transport zone.
        """
        if self.content is not None:
            return

        policy_transport_zone = PolicyTransportZone(
            id=self.name,
            display_name=self.name,
            description=f"Policy Transport Zone {self.name}",
            resource_type=PolicyTransportZone.__name__,
            tz_type=transport_type,
        )

        self._connection.api.policy.infra.sites.enforcement_points.TransportZones.patch(
            NsxInfraSite.DEFAULT_NAME,
            NsxEnforcementPoint.DEFAULT_NAME,
            self.name,
            policy_transport_zone,
        )

    @api_call
    def delete(self) -> None:
        """Delete Transport Zone."""
        if self.content is None:
            return
        self._connection.api.policy.infra.sites.enforcement_points.TransportZones.delete(
            NsxInfraSite.DEFAULT_NAME, NsxEnforcementPoint.DEFAULT_NAME, self.name
        )

    @api_call
    def update_forwarding_mode(self, forwarding_mode: str = PolicyTransportZone.FORWARDING_MODE_IPV4_ONLY) -> None:
        """
        Update forwarding mode of the Transport Zone.

        :param forwarding_mode: New forwarding mode for the transport zone.
        """
        if self.content is None:
            raise ValueError("Transport Zone does not exist.")

        policy_transport_zone = self.content
        policy_transport_zone.forwarding_mode = forwarding_mode
        if policy_transport_zone.tz_type != PolicyTransportZone.TZ_TYPE_OVERLAY_BACKED:
            # VLAN_BACKED transport zones do not support forwarding mode changes
            raise UnsupportedNsxEntity("Cannot change forwarding mode for other than OVERLAY_BACKED transport zones.")

        self._connection.api.policy.infra.sites.enforcement_points.TransportZones.patch(
            NsxInfraSite.DEFAULT_NAME,
            NsxEnforcementPoint.DEFAULT_NAME,
            self.name,
            policy_transport_zone,
        )
