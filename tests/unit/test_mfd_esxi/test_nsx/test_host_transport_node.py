# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest

from mfd_esxi.exceptions import MissingNsxEntity
from mfd_esxi.nsx.connection import NsxConnection
from mfd_esxi.nsx.host_transport_node import NsxHostTransportNode


class TestHostTransportNode:
    @pytest.fixture
    def connection(self, mocker):
        connection = mocker.create_autospec(NsxConnection)
        yield connection
        mocker.stopall()

    @pytest.fixture
    def host_transport_node(self, connection, mocker):
        host_tn = NsxHostTransportNode(name="test_transport_node", connection=connection)
        host_tn._patch = mocker.Mock()

        yield host_tn
        mocker.stopall()

    def test_add_switch_with_uplink_param(self, host_transport_node, mocker):

        vds_id = "test"
        mock_standard_host_switch = mocker.patch("mfd_esxi.nsx.host_transport_node.StandardHostSwitch", autospec=True)
        host_transport_node.add_switch(
            host_switch_name="test_sw",
            uplink_name="uplink",
            transport_zone_name="test_tz",
            vds_id=vds_id,
            uplinks=4,
            ip_pool_id="IPV6pool",
        )
        mock_standard_host_switch.assert_called_once()
        args, kwargs = mock_standard_host_switch.call_args
        assert kwargs["host_switch_name"] == "test_sw"
        assert len(kwargs["uplinks"]) == 4

    def test_add_switch_without_uplink_param(self, host_transport_node, mocker):
        # test whether Exception is not raised when uplink param is not provided
        mock_standard_host_switch = mocker.patch("mfd_esxi.nsx.host_transport_node.StandardHostSwitch", autospec=True)
        host_transport_node.add_switch(
            host_switch_name="test_sw",
            uplink_name="uplink",
            transport_zone_name="test_tz",
            vds_id="test",
            ip_pool_id="IPV4pool",
        )
        mock_standard_host_switch.assert_called_once()
        args, kwargs = mock_standard_host_switch.call_args
        from mfd_esxi.const import ESXI_UPLINK_NUMBER

        assert len(kwargs["uplinks"]) == ESXI_UPLINK_NUMBER

    def test_add_switch_no_payload(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)
        with pytest.raises(MissingNsxEntity):
            host_transport_node.add_switch(
                host_switch_name="test_sw",
                uplink_name="uplink",
                transport_zone_name="test_tz",
                vds_id="test",
                ip_pool_id=None,
            )
