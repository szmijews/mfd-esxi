# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestHost:
    def test_repr(self, standalone_host, cluster_host):
        assert f"{standalone_host}" == "Host('PY-StandaloneHost')"
        assert f"{cluster_host}" == "Host('PY-ClusterHost')"
