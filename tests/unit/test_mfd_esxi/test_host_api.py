# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import time
from mfd_esxi.exceptions import ESXiAPISocketError


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

    def test_returns_performance_metrics_table_for_multiple_adapters(self, mocker, host_api_with_cert):
        mock_adapter1 = mocker.Mock()
        mock_adapter1.name = "eth0"
        mock_adapter2 = mocker.Mock()
        mock_adapter2.name = "eth1"
        mock_host = mocker.Mock()
        mock_perf_manager = mocker.Mock()
        mock_counter_info = {
            "cpu.usage.average": 1,
            "net.received.average": 2,
            "net.transmitted.average": 3,
        }
        mock_stats = [
            (["stat0"], "CPU"),
            (["stat1"], "eth0-Rx"),
            (["stat2"], "eth0-Tx"),
            (["stat3"], "eth1-Rx"),
            (["stat4"], "eth1-Tx"),
        ]
        mocker.patch.object(host_api_with_cert, "get_host", return_value=mock_host)
        host_api_with_cert._ESXiHostAPI__content.perfManager = mock_perf_manager
        mocker.patch.object(host_api_with_cert, "get_performance_metrics_keys", return_value=mock_counter_info)
        mocker.patch.object(host_api_with_cert, "get_performance_metrics_stats", return_value=mock_stats)
        mocker.patch.object(host_api_with_cert, "create_performance_metrics_table", return_value="table")
        result = host_api_with_cert.get_performance_metrics([mock_adapter1, mock_adapter2])
        assert result == "table"

    def test_raises_error_after_five_failed_connection_attempts(self, host_api_with_cert, mocker):
        mocker.patch.object(host_api_with_cert, "get_host", side_effect=Exception("fail"))
        mocker.patch("mfd_esxi.host_api.sleep", mocker.create_autospec(time.sleep))
        try:
            host_api_with_cert.get_performance_metrics([])
            assert False, "Should have raised ESXiAPISocketError"
        except ESXiAPISocketError as e:
            assert "Unable to connect to host" in str(e)

    def test_returns_metrics_table_when_create_chart_false(self, host_api_with_cert, mocker):
        mock_adapter = mocker.Mock()
        mock_adapter.name = "eth0"
        mock_host = mocker.Mock()
        mock_perf_manager = mocker.Mock()
        mock_counter_info = {
            "cpu.usage.average": 1,
            "net.received.average": 2,
            "net.transmitted.average": 3,
        }
        mock_stats = [(["stat0"], "CPU"), (["stat1"], "eth0-Rx"), (["stat2"], "eth0-Tx")]
        mocker.patch.object(host_api_with_cert, "get_host", return_value=mock_host)
        host_api_with_cert._ESXiHostAPI__content.perfManager = mock_perf_manager
        mocker.patch.object(host_api_with_cert, "get_performance_metrics_keys", return_value=mock_counter_info)
        mocker.patch.object(host_api_with_cert, "get_performance_metrics_stats", return_value=mock_stats)
        mocker.patch.object(host_api_with_cert, "create_performance_metrics_table", return_value={"some": "dict"})
        result = host_api_with_cert.get_performance_metrics([mock_adapter], create_chart=False)
        assert result == {"some": "dict"}