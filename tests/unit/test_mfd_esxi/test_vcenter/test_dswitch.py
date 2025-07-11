# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestDSwitch:
    def test_repr(self, dswitch):
        assert f"{dswitch}" == "DSwitch('PY-DSwitch')"
