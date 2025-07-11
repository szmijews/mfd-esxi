# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestESXiHostApi:
    def test_fingerprint(self, host_api_with_cert):
        assert host_api_with_cert.fingerprint == "FE:32:B8:57:D5:6D:75:FC:1E:75:F6:97:2D:7F:27:A0:79:55:22:01"

    def test_get_adapters_sriov_info_all_ports(self, host_api_with_vf_info_and_interfaces):
        assert host_api_with_vf_info_and_interfaces[0].get_adapters_sriov_info(
            host_api_with_vf_info_and_interfaces[1], all_ports=True
        ) == {
            "0000:00:00.0": {
                "enabled": True,
                "max_vfs": 128,
                "num_vfs": 8,
                "req_vfs": 8,
            },
            "0000:00:00.1": {
                "enabled": False,
                "max_vfs": 128,
                "num_vfs": 0,
                "req_vfs": 0,
            },
        }

    def test_get_adapters_sriov_info_single_port(self, host_api_with_vf_info_and_interfaces):
        assert host_api_with_vf_info_and_interfaces[0].get_adapters_sriov_info(
            host_api_with_vf_info_and_interfaces[1], all_ports=False
        ) == {
            "0000:00:00.0": {
                "enabled": True,
                "max_vfs": 128,
                "num_vfs": 8,
                "req_vfs": 8,
            }
        }
