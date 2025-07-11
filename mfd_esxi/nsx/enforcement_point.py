# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX NsxEnforcementPoint."""
from com.vmware.nsx_policy.model_client import EnforcementPoint

from .base import NsxEntity
from .connection import NsxConnection
from .infra_site import NsxInfraSite
from .utils import api_call


class NsxEnforcementPoint(NsxEntity):
    """NSX NsxEnforcementPoint."""

    DEFAULT_NAME = "default"

    def __init__(self, connection: NsxConnection):
        """Initialize instance."""
        super().__init__(self.DEFAULT_NAME, connection)

    @api_call
    def _get_content(self) -> EnforcementPoint:
        return self._connection.api.policy.infra.sites.EnforcementPoints.get(NsxInfraSite.DEFAULT_NAME, self.name)
