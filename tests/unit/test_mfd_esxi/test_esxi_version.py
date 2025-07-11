# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

import pytest
from packaging.version import Version

from mfd_esxi.esxi_version import ESXiVersion, ESXiVersionException
from mfd_connect.base import ConnectionCompletedProcess


class TestESXiVersion:
    output1 = "VMware ESXi 8.0.0 build-20513097"
    output2 = "VMware ESXi 7.0.3 build-19193900"
    output3 = "VMware ESXi 7.0.1 build-16850804"
    output4 = "VMware ESXi 7.0 GA"

    def test_version_1(self):
        version = ESXiVersion(self.output1)
        assert version.version == Version("8.0.0")
        assert version.build == 20513097

    def test_version_2(self):
        version = ESXiVersion(self.output2)
        assert version.version == Version("7.0.3")
        assert version.build == 19193900

    def test_discover(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=self.output3
        )
        version = ESXiVersion.discover(host)
        assert version.version == Version("7.0.1")
        assert version.build == 16850804

    def test_version_assert(self):
        with pytest.raises(ESXiVersionException):
            ESXiVersion(self.output4)
