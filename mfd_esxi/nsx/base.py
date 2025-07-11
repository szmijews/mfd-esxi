# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Basic building blocks for more advanced classes."""
from abc import abstractmethod, ABC
from typing import Optional

from com.vmware.vapi.std.errors_client import NotFound
from vmware.vapi.bindings.struct import VapiStruct

from .connection import NsxConnection
from .utils import api_call


class NsxEntity(ABC):
    """Low level NSX entity."""

    def __init__(self, name: str, connection: NsxConnection):
        """
        Initialize entity instance.

        :param name: NSX entity name.
        :param connection: Connection to NSX.
        """
        self._connection = connection
        self._name = name

    @abstractmethod
    @api_call
    def _get_content(self) -> VapiStruct:
        """
        Get content from NSX.

        :return: Object content from NSX.
        """

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def content(self) -> Optional[VapiStruct]:
        """Get content."""
        try:
            return self._get_content()
        except NotFound:
            return None
