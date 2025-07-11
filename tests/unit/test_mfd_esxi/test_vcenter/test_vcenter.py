# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestVCenter:
    def test_repr(self, vcenter):
        assert f"{vcenter}" == "VCenter('172.31.12.144')"

    def test_initialization(self, vcenter):
        assert vcenter._ip == "172.31.12.144"
        assert vcenter._login == "user"
        assert vcenter._password == "secret"
        assert vcenter._port == 443
