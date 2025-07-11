# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX VNI Pool."""
import random
from com.vmware.nsx_policy.model_client import VniPoolConfig

from .base import NsxEntity
from .utils import api_call


class NsxVniPool(NsxEntity):
    """NSX Vni Pool."""

    @api_call
    def _get_content(self) -> VniPoolConfig:
        return self._connection.api.policy.infra.VniPools.get(self.name)

    @api_call
    def add(self) -> None:
        """Add VNI pool to NSX."""
        overlay_id = random.randint(75001, 16777215)

        if self.content is not None:
            return

        vni_poll_config = VniPoolConfig(start=overlay_id, end=overlay_id)

        self._connection.api.policy.infra.VniPools.patch(self.name, vni_poll_config)

    @api_call
    def overlay_id(self) -> int:
        """Return VNI overlay ID."""
        payload: VniPoolConfig = self.content
        return payload.start

    @api_call
    def delete(self) -> None:
        """Delete VNI pool."""
        if self.content is None:
            return
        self._connection.api.policy.infra.VniPools.delete(self.name)
