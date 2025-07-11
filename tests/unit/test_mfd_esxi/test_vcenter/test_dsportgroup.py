# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestDSPortgroup:
    def test_repr(self, dsportgroup):
        assert f"{dsportgroup}" == "DSPortgroup('PY-DSPortgroup')"
