# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest

from com.vmware.nsx_policy.model_client import PolicyTransportZone
from mfd_esxi.exceptions import UnsupportedNsxEntity
from mfd_esxi.nsx.connection import NsxConnection
from mfd_esxi.nsx.transport_zone import NsxTransportZone


class TestTransportZone:
    @pytest.fixture
    def connection(self, mocker):
        connection = mocker.create_autospec(NsxConnection)
        yield connection
        mocker.stopall()

    @pytest.fixture
    def host_transport_node(self, connection, mocker):
        host_tn = NsxTransportZone(name="test_transport_zone", connection=connection)
        host_tn._patch = mocker.Mock()

        yield host_tn
        mocker.stopall()

    def test_updates_forwarding_mode_when_transport_zone_exists(self, mocker, host_transport_node):
        host_transport_node._get_content = mocker.Mock()
        host_transport_node._get_content.return_value.tz_type = PolicyTransportZone.TZ_TYPE_OVERLAY_BACKED

        host_transport_node.update_forwarding_mode("NEW_MODE")

        host_transport_node._connection.api.policy.infra.sites.enforcement_points.TransportZones.patch.assert_called_once()  # noqa: E501

    def test_raises_value_error_when_transport_zone_does_not_exist(self, mocker, host_transport_node):
        host_transport_node._get_content = mocker.Mock()
        host_transport_node._get_content.return_value = None

        with pytest.raises(ValueError, match="Transport Zone does not exist."):
            host_transport_node.update_forwarding_mode("ANY_MODE")

    def test_raises_exception_when_transport_zone_is_vlan_backed(self, mocker, host_transport_node):
        host_transport_node._get_content = mocker.Mock()
        host_transport_node._get_content.return_value.tz_type = PolicyTransportZone.TZ_TYPE_VLAN_BACKED

        with pytest.raises(UnsupportedNsxEntity):
            host_transport_node.update_forwarding_mode("ANY_MODE")
