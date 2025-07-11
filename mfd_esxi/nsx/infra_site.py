# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX site."""
from com.vmware.nsx_policy.model_client import Site

from .base import NsxEntity
from .connection import NsxConnection
from .utils import api_call


class NsxInfraSite(NsxEntity):
    """NSX site."""

    DEFAULT_NAME = "default"

    def __init__(self, connection: NsxConnection):
        """Initialize instance."""
        super().__init__(self.DEFAULT_NAME, connection)

    @api_call
    def _get_content(self) -> Site:
        return self._connection.api.policy.infra.Sites.get(self.name)
