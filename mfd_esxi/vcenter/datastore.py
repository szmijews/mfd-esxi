# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Datastore wrapper."""
import logging
from typing import Any, Generator, TYPE_CHECKING
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from .virtual_machine import VirtualMachine
from .utils import get_obj_from_iter, MiB
from .exceptions import VCenterResourceMissing

if TYPE_CHECKING:
    from .host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class Datastore(object):
    """Datastore wrapper."""

    def __init__(self, name: str, host: "Host"):
        """
        Initialize instance.

        :param name: Name of datastore.
        :param host: Host parent of datastore.
        """
        self._name = name
        self._host = host

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> "vim.Datastore":
        """Get content of datastore in API."""
        # pylint: disable=protected-access
        for datastore in self._host.content.datastore:
            if datastore.name == self.name:
                return datastore
        raise VCenterResourceMissing(self)

    @property
    def name(self) -> str:
        """Get name of datastore."""
        return self._name

    @property
    def host(self) -> "Host":
        """Get host parent of datastore."""
        return self._host

    @property
    def capacity(self) -> int:
        """Get capacity of datastore in MB."""
        return self.content.info.vmfs.capacity / MiB

    @property
    def free_space(self) -> int:
        """Get free space in datastore in MB."""
        return self.content.info.freeSpace / MiB

    @property
    def vms(self) -> Generator["VirtualMachine", Any, None]:
        """Get all VMs for datastore."""
        return (VirtualMachine(vm.name, self._host) for vm in self.content.vm)

    def get_vm_by_name(self, name: str) -> "VirtualMachine":
        """Get specific VM from datastore.

        :param name: Name of VM.

        :return: Virtual machine.
        """
        return get_obj_from_iter(self.vms, name)
