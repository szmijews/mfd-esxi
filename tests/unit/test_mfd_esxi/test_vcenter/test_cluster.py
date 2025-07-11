# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestCluster:
    def test_repr(self, cluster):
        assert f"{cluster}" == "Cluster('PY-Cluster')"
