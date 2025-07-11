# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestVirtualMachine:
    def test_repr(self, virtual_machine):
        assert f"{virtual_machine}" == "VirtualMachine('PY-VirtualMachine')"
