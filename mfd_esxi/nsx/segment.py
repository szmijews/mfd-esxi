# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX Segment."""
from typing import List
from com.vmware.nsx_policy.model_client import Segment

from .base import NsxEntity
from .connection import NsxConnection
from .enforcement_point import NsxEnforcementPoint
from .infra_site import NsxInfraSite
from .utils import api_call
from ..exceptions import MissingNsxEntity


class NsxSegment(NsxEntity):
    """NSX Uplink profile."""

    @api_call
    def _get_content(self) -> Segment:
        return self._connection.api.policy.infra.Segments.get(self.name)

    @api_call
    def add(
        self,
        transport_zone_name: str,
        vlan_ids: List[str] | None = None,
        vlan: int | None = None,
        overlay_id: int | None = None,
    ) -> None:
        """
        Add Segment to NSX.

        :param transport_zone_name: name of transport zone
        :param vlan_ids: list of vlan numbers or ranges
        :param vlan: vlan number
        :param overlay_id: create custom VNI ID for overlay traffic
        """
        transport_zone_path = (
            f"/infra/sites/{NsxInfraSite.DEFAULT_NAME}/enforcement-points/"
            f"{NsxEnforcementPoint.DEFAULT_NAME}/transport-zones/{transport_zone_name}"
        )

        segment: Segment = self.content
        if segment is None:
            segment = Segment(
                id=self.name,
                display_name=self.name,
                description=f"Segment {self.name}",
                resource_type=Segment.__name__,
                transport_zone_path=transport_zone_path,
            )
        if vlan_ids is not None:
            segment.vlan_ids = vlan_ids
        elif vlan is not None:
            segment.vlan_ids = [str(vlan)]
        else:
            segment.vlan_ids = []
        if overlay_id is not None:
            segment.overlay_id = overlay_id

        self._connection.api.policy.infra.Segments.patch(self.name, segment)

    @api_call
    def set_vlan(self, vlan_ids: List[str] | None = None, vlan: int | None = None) -> None:
        """
        Set VLAN for segment.

        :param vlan_ids: list of vlan numbers or range
        :param vlan: vlan number
        """
        segment: Segment = self.content
        if segment is None:
            raise MissingNsxEntity(f"Could not find segment {self.name}")

        if vlan_ids is not None:
            segment.vlan_ids = vlan_ids
        elif vlan is not None:
            segment.vlan_ids = [str(vlan)]
        else:
            segment.vlan_ids = []

        self._connection.api.policy.infra.Segments.patch(self.name, segment)

    @api_call
    def delete(self) -> None:
        """Delete Segment."""
        if self.content is None:
            return
        self._connection.api.policy.infra.Segments.delete(self.name)

    @staticmethod
    @api_call
    def list_zones(zones: List[str], connection: NsxConnection) -> List[str]:
        """
        Get list of all segments using selected transport zones.

        :param zones: list of transport zone names
        :param connection: NSX object
        :return: list of all segment names used by transport zones
        """
        results = connection.api.policy.infra.Segments.list().results
        segments = []
        for result in results:
            if result.transport_zone_path is not None:
                tzone_name = result.transport_zone_path.split("/")[-1]
                if tzone_name in zones:
                    segments.append(result.id)
        return segments
