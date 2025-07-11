# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX Fabric Discovered Node."""
from com.vmware.nsx_policy.model_client import FabricHostNode

from .base import NsxEntity
from .utils import api_call


class NsxFabricDiscoveredNode(NsxEntity):
    """NSX Fabric Discovered Node."""

    @api_call
    def _get_content(self) -> FabricHostNode:
        # NSX API does not support get-by-name in this case. Manual search from all is required

        return next(
            filter(
                lambda fdn: self.name == fdn.display_name,
                self._connection.api.management.fabric.DiscoveredNodes.list().results,
            ),
            None,
        )
