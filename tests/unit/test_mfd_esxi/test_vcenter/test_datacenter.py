# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestDatacenter:
    def test_repr(self, datacenter):
        assert f"{datacenter}" == "Datacenter('PY-Datacenter')"
