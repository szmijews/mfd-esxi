# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestVSwitch:
    def test_repr(self, vswitch):
        assert f"{vswitch}" == "VSwitch('PY-VSwitch')"
