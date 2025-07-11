# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Version of ESXi."""

import re
from packaging.version import Version
from typing import TYPE_CHECKING
from .exceptions import ESXiVersionException

if TYPE_CHECKING:
    from mfd_esxi.host import ESXiHypervisor


class ESXiVersion:
    """Class for ESXi version."""

    def __init__(self, full_string: str):
        """
        Initialize version object.

        :param full_string: output of vmware -v
        """
        match = re.search(r"\s+(?P<version>\d+\.\d+\.\d+)\s+build-(?P<build>\d+)", full_string)
        if match:
            self.version = Version(match.group("version"))
            self.build = int(match.group("build"))
            self.full_string = full_string
        else:
            raise ESXiVersionException(f"Unable to parse version: {full_string}")

    @staticmethod
    def discover(owner: "ESXiHypervisor") -> "ESXiVersion":
        """
        Discover the ESXi version.

        :param owner: ESXi host
        :return: version object
        """
        output = owner.execute_command("vmware -v").stdout
        version = ESXiVersion(output)
        return version
