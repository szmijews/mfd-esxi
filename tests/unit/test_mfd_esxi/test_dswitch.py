# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest
from unittest.mock import MagicMock, call
from ipaddress import IPv4Interface
from mfd_esxi.dswitch import ESXiDVSwitch
from mfd_esxi.exceptions import ESXiNameException, ESXiNotFound
from .fixtures import (
    esxcfg_vswitch_4,
    esxcfg_vswitch_5,
    esxcfg_vswitch_6,
    esxcfg_vmknic_4,
    esxcfg_vmknic_3,
    net_dvs_lcores_1,
    net_dvs_lcores_2,
    net_dvs_lcores_3,
    net_dvs_lcores_4,
)
from mfd_connect.base import ConnectionCompletedProcess
import time


def assert_not_called_with(mock, *args, **kwargs):
    if call(*args, **kwargs) in mock.mock_calls:
        raise AssertionError(f"Expected not to be called with {args} and {kwargs}, but it was.")


class TestESXiDVSwitch:
    def test_initialize_correctly_parses_output(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.initialize(esxcfg_vswitch_4)
        assert switch.mtu == 1500
        assert switch.uplinks == {"uplink0": "vmnic0", "uplink1": "vmnic1"}
        assert switch.portgroups == ["PG1", "PG2"]

    def test_initialize_raises_error_if_switch_not_found(self, host):
        switch = ESXiDVSwitch(host, "NonExistentSwitch1")
        with pytest.raises(ESXiNotFound, match="Could not find vSwitch NonExistentSwitch"):
            switch.initialize(esxcfg_vswitch_4)

    def test_initialize_handles_no_portgroups(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.initialize(esxcfg_vswitch_5)
        assert switch.portgroups == []

    def test_initialize_handles_empty_output(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        output = ""
        with pytest.raises(ESXiNotFound, match="Could not find vSwitch TestSwitch"):
            switch.initialize(output)

    def test_initialize_parses_mtu_without_uplinks(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.initialize(esxcfg_vswitch_6)
        assert switch.mtu == 1500
        assert switch.uplinks == {}

    def test_refresh_updates_portgroups_and_uplinks(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vswitch_4
        )
        switch = ESXiDVSwitch(owner=host, name="TestSwitch")
        switch.refresh()
        assert switch.portgroups == ["PG1", "PG2"]
        assert switch.uplinks == {"uplink0": "vmnic0", "uplink1": "vmnic1"}

    def test_refresh_raises_exception_if_switch_not_found(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vswitch_4
        )
        switch = ESXiDVSwitch(owner=host, name="TestSwitch1")
        with pytest.raises(ESXiNotFound):
            switch.refresh()

    def test_discover(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vswitch_4
        )
        switches = ESXiDVSwitch.discover(host)
        assert len(switches) == 1

    def test_reconfigure(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.initialize(esxcfg_vswitch_4)
        switch.reconfigure(
            uplinks=["vmnic4", "vmnic5"],
            portgroups=["t1", "t2"],
            mtu=9000,
            vmknic=False,
        )
        assert switch.uplinks == {"uplink0": "vmnic4", "uplink1": "vmnic5"}
        assert "t1" in switch.portgroups
        assert "t2" in switch.portgroups
        assert 9000 == switch.mtu

    def test_configures_uplinks_correctly(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.set_uplink_number = MagicMock()
        switch.link_adapter = MagicMock()

        switch.configure(uplinks=["vmnic0", "vmnic1"])

        switch.set_uplink_number.assert_called_once_with(2)
        switch.link_adapter.assert_any_call("vmnic0")
        switch.link_adapter.assert_any_call("vmnic1")

    def test_configures_portgroups_correctly(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_portgroup = MagicMock()
        switch.portgroups = ["PG1"]

        switch.configure(uplinks=[], portgroups=["PG1", "PG2"])

        switch.add_portgroup.assert_called_once_with("PG2")

    def test_configures_vmknic_portgroups(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_vmknic = MagicMock()
        switch.add_portgroup = MagicMock()
        switch.uplinks = {"uplink0": None, "uplink1": None}

        switch.configure(uplinks=["vmnic1", "vmnic2"], vmknic=True)
        switch.add_portgroup.assert_any_call("PGuplink0")
        switch.add_portgroup.assert_any_call("PGuplink1")
        switch.add_vmknic.assert_any_call(port_name="PGuplink0", mtu=1500, ip=IPv4Interface("20.20.20.1/8"))
        switch.add_vmknic.assert_any_call(port_name="PGuplink1", mtu=1500, ip=IPv4Interface("20.20.20.2/8"))

    def test_updates_mtu_correctly(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.set_mtu = MagicMock()
        switch.mtu = 1400

        switch.configure(uplinks=[], mtu=1600)

        switch.set_mtu.assert_called_once_with(1600)

    def test_updates_vmknic_mtu(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        mock_vmknic = MagicMock()
        mock_vmknic.portgroup = "PG1"
        mock_vmknic.mtu = 1400
        host.vmknic = [mock_vmknic]
        switch.portgroups = ["PG1"]

        switch.configure(uplinks=[], mtu=1600)

        mock_vmknic.set_mtu.assert_called_once_with(1600)

    def test_link_adapter_uses_free_uplink(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.link_adapter_esxcfg = MagicMock()
        switch.uplinks = {"uplink0": None, "uplink1": "vmnic1"}

        switch.link_adapter("vmnic2")

        assert switch.uplinks["uplink0"] == "vmnic2"
        switch.link_adapter_esxcfg.assert_called_once_with("vmnic2", "uplink0")

    def test_link_adapter_raises_error_when_no_free_uplinks(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.uplinks = {"uplink0": "vmnic0", "uplink1": "vmnic1"}

        with pytest.raises(RuntimeError, match="No free uplinks to use"):
            switch.link_adapter("vmnic2")

    def test_unlink_adapter_releases_uplink(self, host):
        switch = ESXiDVSwitch(owner=host, name="TestSwitch")
        switch.uplinks = {"uplink0": "vmnic0", "uplink1": None}
        switch.unlink_adapter_esxcfg = MagicMock()

        switch.unlink_adapter("vmnic0")

        switch.unlink_adapter_esxcfg.assert_called_once_with("vmnic0", "uplink0")
        assert switch.uplinks["uplink0"] is None

    def test_unlink_all_adapters_unlinks_all_when_uplinks_are_assigned(self, host):
        dswitch = ESXiDVSwitch(owner=host, name="TestSwitch")
        dswitch.uplinks = {"uplink0": "vmnic0", "uplink1": "vmnic1"}
        dswitch.unlink_adapter = MagicMock()

        dswitch.unlink_all_adapters()

        dswitch.unlink_adapter.assert_any_call("vmnic0")
        dswitch.unlink_adapter.assert_any_call("vmnic1")
        assert dswitch.unlink_adapter.call_count == 2

    def test_unlink_all_adapters_does_nothing_when_no_uplinks_are_assigned(self, host):
        dswitch = ESXiDVSwitch(owner=host, name="TestSwitch")
        dswitch.uplinks = {"uplink0": None, "uplink1": None}
        dswitch.unlink_adapter = MagicMock()

        dswitch.unlink_all_adapters()

        dswitch.unlink_adapter.assert_not_called()

    def test_add_portgroup_executes_correct_command(self, host):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "test_switch")
        switch.add_portgroup("test_portgroup")
        host.execute_command.assert_called_once_with("net-dvs -A -p test_portgroup test_switch")
        assert "test_portgroup" in switch.portgroups

    def test_add_portgroup_appends_to_portgroups_list(self, host):
        switch = ESXiDVSwitch(host, "test_switch")
        switch.add_portgroup("new_portgroup")
        assert "new_portgroup" in switch.portgroups

    def test_add_portgroup_handles_empty_name_gracefully(self, host):
        switch = ESXiDVSwitch(host, "test_switch")
        with pytest.raises(ESXiNameException, match="Portgroup name cannot be empty"):
            switch.add_portgroup("")

    def test_deletes_existing_portgroup(self, host):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.portgroups = ["PG1", "PG2", "PG3"]

        switch.del_portgroup("PG2")

        host.execute_command.assert_called_once_with("net-dvs -D -p PG2 TestSwitch")
        assert switch.portgroups == ["PG1", "PG3"]

    def test_raises_error_when_deleting_nonexistent_portgroup(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.portgroups = ["PG1", "PG2", "PG3"]

        with pytest.raises(ESXiNotFound, match="Portgroup PG4 not found in TestSwitch"):
            switch.del_portgroup("PG4")

    def test_set_portgroup_vlan_sets_correct_vlan_policy(self, host):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.set_portgroup_vlan("TestPortgroup", 100)
        host.execute_command.assert_called_once_with(
            "LC_ALL=en_US.UTF-8 nsxdp-cli vswitch vlan policy set --no-guest-tagging "
            "--vlan 100 -p TestPortgroup -dvs TestSwitch",
            shell=True,
        )

    def test_set_portgroup_vlan_sets_guest_tagging_for_vlan_4095(self, host):
        host.execute_command = MagicMock()
        dvs = ESXiDVSwitch(host, "TestSwitch")
        dvs.set_portgroup_vlan("TestPortgroup", 4095)
        host.execute_command.assert_called_once_with(
            "LC_ALL=en_US.UTF-8 nsxdp-cli vswitch vlan policy set --guest-tagging -p TestPortgroup -dvs TestSwitch",
            shell=True,
        )

    def test_set_portgroup_vlan_raises_error_for_invalid_vlan(self, host):
        host.execute_command = MagicMock()
        dvs = ESXiDVSwitch(host, "TestSwitch")
        with pytest.raises(ValueError):
            dvs.set_portgroup_vlan("TestPortgroup", -1)

    def test_adds_vmknic_to_portgroup(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = esxcfg_vmknic_4
        port_name = "PGvmnic0"
        ip = IPv4Interface("20.20.20.1/8")
        mtu = 1500

        switch = ESXiDVSwitch(host, "TestSwitch")
        vmknic = switch.add_vmknic(port_name, ip, mtu)

        assert vmknic.name == "vmk0"
        assert vmknic.portgroup == port_name
        assert vmknic.mtu == mtu
        host.execute_command.assert_called_with("esxcfg-vmknic -l")

    def test_raises_error_when_vmknic_not_found(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = esxcfg_vmknic_3
        port_name = "PGvmnic0"
        ip = IPv4Interface("20.20.20.1/8")
        mtu = 1500

        switch = ESXiDVSwitch(host, "TestSwitch")

        with pytest.raises(ESXiNotFound, match=f"VMKernel NIC in port {port_name} not found"):
            switch.add_vmknic(port_name, ip, mtu)

    def test_del_vmknic_removes_vmknic_from_owner_list(self, host):
        vmknic = MagicMock()
        host.execute_command = MagicMock()
        vmknic.portgroup = "test_portgroup"
        host.vmknic = [vmknic]
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_vmknic(vmknic)
        assert vmknic not in host.vmknic
        host.execute_command.assert_called_once_with(f"esxcfg-vmknic -d {vmknic.name} -s TestSwitch -v test_portgroup")

    def test_del_vmknic_raises_exception_if_vmknic_not_found(self, host):
        vmknic = MagicMock()
        host.vmknic = []
        switch = ESXiDVSwitch(host, "TestSwitch")
        with pytest.raises(ESXiNotFound):
            switch.del_vmknic(vmknic)

    def test_deletes_all_vmknics_associated_with_portgroups(self, host):
        vmknic1 = MagicMock()
        vmknic1.portgroup = "PG1"
        vmknic2 = MagicMock()
        vmknic2.portgroup = "PG2"
        vmknic3 = MagicMock()
        vmknic3.portgroup = "Other"
        host.vmknic = [vmknic1, vmknic2, vmknic3]

        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.portgroups = ["PG1", "PG2"]
        switch.del_vmknic = MagicMock()

        switch.del_all_vmknics()

        switch.del_vmknic.assert_any_call(vmknic1)
        switch.del_vmknic.assert_any_call(vmknic2)
        assert_not_called_with(switch.del_vmknic, vmknic3)

    def test_does_nothing_when_no_vmknics_match_portgroups(self, host):
        vmknic1 = MagicMock()
        vmknic1.portgroup = "Other1"
        vmknic2 = MagicMock()
        vmknic2.portgroup = "Other2"
        host.vmknic = [vmknic1, vmknic2]

        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.portgroups = ["PG1", "PG2"]
        switch.del_vmknic = MagicMock()

        switch.del_all_vmknics()

        switch.del_vmknic.assert_not_called()

    def test_get_dswitch_id_returns_correct_id(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = "switch 74 65 73 74 2d 64 76 73-00 00 00 00 00 00 00 00\n"
        switch = ESXiDVSwitch(host, "TestSwitch")
        result = switch.get_dswitch_id()
        assert result == "74 65 73 74 2d 64 76 73-00 00 00 00 00 00 00 00"

    def test_sets_mtu_correctly(self, host):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(owner=host, name="TestSwitch")
        switch.set_mtu(9000)
        host.execute_command.assert_called_once_with("esxcfg-vswitch --mtu 9000 TestSwitch")
        assert switch.mtu == 9000

    def test_raises_error_for_invalid_mtu(self, host):
        switch = ESXiDVSwitch(owner=host, name="TestSwitch")
        with pytest.raises(ValueError):
            switch.set_mtu(1499)

    def test_get_ens_switch_id_returns_correct_id(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = "switch1 123\nswitch2 456\n"
        switch = ESXiDVSwitch(host, "switch1")
        assert switch.get_ens_switch_id() == 123

    def test_get_ens_switch_id_raises_error_when_switch_not_found(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = "switch2 456\nswitch3 789\n"
        dvs = ESXiDVSwitch(host, "switch1")
        with pytest.raises(RuntimeError, match="Could not find ENS DVS switch1"):
            dvs.get_ens_switch_id()

    def test_enables_ens_successfully(self, host, mocker):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.get_ens_switch_id = MagicMock(return_value=123)

        mocker.patch("mfd_esxi.dswitch.sleep", mocker.create_autospec(time.sleep))
        switch.enable_ens()

        host.execute_command.assert_any_call("esxcfg-vswitch -y TestSwitch")
        switch.get_ens_switch_id.assert_called_once()
        assert switch.ens_sw_id == 123

    def test_raises_error_when_get_ens_switch_id_fails(self, host, mocker):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.get_ens_switch_id = MagicMock(side_effect=RuntimeError("Failed to get ENS switch ID"))

        mocker.patch("mfd_esxi.dswitch.sleep", mocker.create_autospec(time.sleep))
        with pytest.raises(RuntimeError):
            switch.enable_ens()

        host.execute_command.assert_any_call("esxcfg-vswitch -y TestSwitch")
        switch.get_ens_switch_id.assert_called_once()

    def test_disables_ens_successfully(self, host, mocker):
        host.execute_command = MagicMock()
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_ens_lcores = MagicMock()

        mocker.patch("mfd_esxi.dswitch.sleep", mocker.create_autospec(time.sleep))
        switch.disable_ens()

        host.execute_command.assert_called_once_with("esxcfg-vswitch -Y TestSwitch")
        switch.del_ens_lcores.assert_called_once()

    def test_disable_ens_raises_exception_when_command_fails(self, host):
        host.execute_command = MagicMock()
        host.execute_command.side_effect = RuntimeError("Command failed")
        switch = ESXiDVSwitch(host, "TestSwitch")

        with pytest.raises(RuntimeError):
            switch.disable_ens()

    def test_add_ens_lcores_adds_correct_number_of_lcores(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_2
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_ens_lcores(3)
        # 1 list lcores, 2 add to existing lcores, 1 add new lcore, 1 add to newly created one
        assert host.execute_command.call_count == 5

    def test_add_ens_lcores_handles_existing_lcores(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_1
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_ens_lcores(4)
        # 1 lcore already assigned to the TestSwitch
        # 1 list lcores, 2 add to existing lcores, 1 add new lcore, 1 add to newly created one
        assert host.execute_command.call_count == 5

    def test_add_ens_lcores_limits_to_maximum_of_8(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_2
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_ens_lcores(10)
        # 1 list lcores, 2 add to existing lcores, 6 add new lcore, 6 add to newly created one
        assert host.execute_command.call_count == 15

    def test_add_ens_lcores_skips_already_assigned_lcores(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_3

        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.add_ens_lcores(2)
        assert host.execute_command.call_count == 1  # Command to view lcores only
        host.execute_command.assert_called_once_with("esxcli network ens lcore list", expected_return_codes={0})

    def test_deletes_all_lcores_when_not_set(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_2
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_ens_lcores()
        host.execute_command.assert_any_call("esxcli network ens lcore remove -l 0", expected_return_codes={0})
        host.execute_command.assert_any_call("esxcli network ens lcore remove -l 1", expected_return_codes={0})

    def test_does_nothing_when_no_lcores_are_not_set(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_3
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_ens_lcores()
        assert_not_called_with(
            host.execute_command,
            "esxcli network ens lcore remove -l 0",
            expected_return_codes={0},
        )
        assert_not_called_with(
            host.execute_command,
            "esxcli network ens lcore remove -l 1",
            expected_return_codes={0},
        )

    def test_handles_empty_lcore_list(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = net_dvs_lcores_4
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_ens_lcores()
        host.execute_command.assert_called_once()

    def test_migrate_ports_to_different_lcores(self, host):
        host.execute_command = MagicMock()
        host.execute_command.return_value.stdout = "VNIC 1\n" "VNIC 2\n" "VNIC 3\n"
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.ens_sw_id = 123

        switch.migrate_ens_lcores()

        host.execute_command.assert_any_call(
            "LC_ALL=en_US.UTF-8 nsxdp-cli ens port migrate --sw-id 123 --port-id 1 --lcore-id 0 --dir 0",
            expected_return_codes={0},
            shell=True,
        )
        host.execute_command.assert_any_call(
            "LC_ALL=en_US.UTF-8 nsxdp-cli ens port migrate --sw-id 123 --port-id 1 --lcore-id 0 --dir 1",
            expected_return_codes={0},
            shell=True,
        )

    def test_deletes_all_vmknics_before_deleting_dswitch(self, host):
        switch = ESXiDVSwitch(host, "TestSwitch")
        switch.del_all_vmknics = MagicMock()
        switch.del_dswitch_esxcfg = MagicMock()

        switch.del_dswitch()

        switch.del_all_vmknics.assert_called_once()
        switch.del_dswitch_esxcfg.assert_called_once()

    def test_addswitch_creates_switch_with_valid_name(self, host):
        switch = ESXiDVSwitch.add_dswitch_esxcfg(host, "valid_name")
        host.connection.execute_command.assert_called_once_with(
            "esxcfg-vswitch -a valid_name --dvswitch --impl-class=vswitch"
        )
        assert isinstance(switch, ESXiDVSwitch)
        assert switch.name == "valid_name"

    def test_addswitch_does_not_execute_command_for_invalid_name(self, host):
        with pytest.raises(
            ESXiNameException,
            match="Switch name should contain only letters, digits and underscore",
        ):
            ESXiDVSwitch.add_dswitch_esxcfg(host, "invalid-name!")
        host.connection.execute_command.assert_not_called()

    def test_add_portgroup(self, host):
        dswitch = ESXiDVSwitch(host, "DVSwitch0")
        dswitch.add_portgroup("PGtest")
        assert "PGtest" in dswitch.portgroups

    def test_del_portgroup(self, host):
        dswitch = ESXiDVSwitch(host, "DVSwitch0")
        dswitch.add_portgroup("PGtest")
        dswitch.del_portgroup("PGtest")
        assert len(dswitch.portgroups) == 0