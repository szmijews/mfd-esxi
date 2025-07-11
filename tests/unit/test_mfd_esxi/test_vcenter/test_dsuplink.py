# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestDSUplink:
    def test_repr(self, dsuplink):
        assert f"{dsuplink}" == "DSUplink('PY-DSUplink')"
