# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest

from mfd_esxi.nsx.connection import NsxConnection
from mfd_esxi.nsx.uplink_profile import NsxUplinkProfile


class TestHostTransportNode:
    @pytest.fixture
    def connection(self, mocker):
        connection = mocker.create_autospec(NsxConnection)
        yield connection
        mocker.stopall()

    @pytest.fixture
    def uplink_profile(self, connection, mocker):
        host_up = NsxUplinkProfile(name="test_uplink_profile", connection=connection)
        host_up._patch = mocker.Mock()

        yield host_up
        mocker.stopall()

    def test_updates_vlan_when_uplink_profile_exists(self, mocker, uplink_profile):
        uplink_profile._get_content = mocker.Mock()

        uplink_profile.update_transport_vlan(transport_vlan=101)

        uplink_profile._connection.api.policy.infra.HostSwitchProfiles.patch.assert_called_once()  # noqa: E501

    def test_raises_value_error_when_uplink_profile_does_not_exist(self, mocker, uplink_profile):
        uplink_profile._get_content = mocker.Mock()
        uplink_profile._get_content.return_value = None

        with pytest.raises(ValueError, match="Uplink profile does not exist."):
            uplink_profile.update_transport_vlan(transport_vlan=101)
