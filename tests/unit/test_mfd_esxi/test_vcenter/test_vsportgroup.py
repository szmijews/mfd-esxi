# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestVSPortgroup:
    def test_repr(self, vsportgroup):
        assert f"{vsportgroup}" == "VSPortgroup('PY-VSPortgroup')"
