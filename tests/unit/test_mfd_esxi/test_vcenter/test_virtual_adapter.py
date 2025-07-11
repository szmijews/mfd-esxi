# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestVirtualAdapter:
    def test_repr(self, virtual_adapter):
        assert f"{virtual_adapter}" == "VirtualAdapter('PY-VirtualAdapter') in Host('PY-StandaloneHost')"
