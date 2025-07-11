# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""VCenter specific exceptions."""
from typing import Any


class VCenterResourceInUse(Exception):
    """Resource is in use."""

    def __init__(self, resource: Any, message: str):
        """
        Initialize instance.

        :param resource: Resource.
        :param message: Exception message.
        """
        super().__init__(f"{resource}: {message}")


class VCenterResourceMissing(Exception):
    """Resource is missing."""

    def __init__(self, resource: Any):
        """
        Initialize instance.

        :param resource: Name of resource.
        """
        super().__init__(resource)


class VCenterDSPortgroupMissingHostMember(Exception):
    """VCenter Distributed Switch Portgroup is missing Host member."""


class VCenterDistributedSwitchUplinkRemovalFailed(Exception):
    """VCenter Distributed Switch Uplink removal has failed."""


class VCenterResourceSetupError(Exception):
    """Resource setup failed."""

    def __init__(self, resource: Any):
        """
        Initialize instance.

        :param resource: Name of resource.
        """
        super().__init__(resource)


class VCenterInvalidLogin(Exception):
    """Invalid VCenter login used."""


class VCenterSocketError(Exception):
    """VCenter socket error."""
