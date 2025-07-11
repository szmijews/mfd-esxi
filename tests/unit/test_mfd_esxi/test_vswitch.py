# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from mfd_connect.base import ConnectionCompletedProcess

from mfd_esxi.exceptions import VswitchError
from mfd_esxi.vswitch import ESXivSwitch
from .fixtures import esxcfg_vswitch_1, esxcfg_vswitch_2, esxcfg_vmknic_1


class TestESXivSwitch:
    def test_initialize(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.initialize(esxcfg_vswitch_1)
        assert vswitch.mtu == 1500
        assert vswitch.uplinks == ["vmnic0"]
        assert "ATmng" in vswitch.portgroups
        assert "VM Network" in vswitch.portgroups
        assert "Management Network" in vswitch.portgroups

    def test_refresh(self, host_esxcfg_vswitch_2):
        vswitch = ESXivSwitch(host_esxcfg_vswitch_2, "ATvSwitchLongName")
        vswitch.refresh()
        assert vswitch.mtu == 1500
        assert vswitch.uplinks == ["vmnic10"]
        assert "ATNetwork" in vswitch.portgroups
        assert "ATvmnic10" in vswitch.portgroups

    def test_discover(self, host_esxcfg_vswitch_1):
        vswitches = ESXivSwitch.discover(host_esxcfg_vswitch_1)
        assert len(vswitches) == 1

    def test_add_vswitch(self, host):
        vswitch = ESXivSwitch.add_vswitch(host, "test")
        assert isinstance(vswitch, ESXivSwitch)
        assert vswitch.name == "test"

    def test_del_vswitch(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vswitch_2
        )
        host.initialize_vswitch()
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vmknic_1
        )
        host.initialize_vmknic()

        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        assert len(host.vswitch) == 2
        assert len(host.vmknic) == 2
        for vswitch in host.vswitch:
            if vswitch.name == "ATvSwitchLongName":
                vswitch.del_vswitch()
                assert len(host.vmknic) == 1
                break
        else:
            assert False

    def test_set_mtu(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.set_mtu(5000)
        assert vswitch.mtu == 5000

    def test_add_uplink(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.add_uplink("vmnic99")
        assert "vmnic99" in vswitch.uplinks

    def test_del_uplink(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.add_uplink("vmnic99")
        vswitch.del_uplink("vmnic99")
        assert len(vswitch.uplinks) == 0

    def test_add_portgroup(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.add_portgroup("PGtest")
        assert "PGtest" in vswitch.portgroups

    def test_del_portgroup(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.add_portgroup("PGtest")
        vswitch.del_portgroup("PGtest")
        assert len(vswitch.portgroups) == 0

    def test_del_portgroup_vmknic(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vswitch_2
        )
        host.initialize_vswitch()
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=esxcfg_vmknic_1
        )
        host.initialize_vmknic()

        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        assert len(host.vswitch) == 2
        assert len(host.vmknic) == 2

        for vswitch in host.vswitch:
            if vswitch.name == "ATvSwitchLongName":
                vswitch.del_portgroup("ATvmnic10")
                assert len(host.vmknic) == 1
                break
        else:
            assert False

    def test_set_vlan(self, host):
        vswitch = ESXivSwitch(host, "ATvSwitchLongName")
        vswitch.initialize(esxcfg_vswitch_2)
        vswitch.set_portgroup_vlan("ATNetwork", 10)

    def test_set_portgroup_uplinks(self, host):
        vswitch = ESXivSwitch(host, "ATvSwitchLongName")
        vswitch.initialize(esxcfg_vswitch_2)
        vswitch.set_portgroup_uplinks("ATNetwork", ["vmnic10"])

    def test_configure(self, host):
        vswitch = ESXivSwitch(host, "ATvSwitch")
        vswitch.configure(uplinks=["vmnic4", "vmnic5"], portgroups=["t1", "t2"], vmknic=False)
        assert "vmnic4" in vswitch.uplinks
        assert "vmnic5" in vswitch.uplinks
        assert "t1" in vswitch.portgroups
        assert "t2" in vswitch.portgroups

    def test_reconfigure(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        vswitch.initialize(esxcfg_vswitch_1)
        vswitch.reconfigure(
            uplinks=["vmnic4", "vmnic5"],
            portgroups=["t1", "t2"],
            mtu=9000,
            vmknic=False,
        )
        assert "vmnic4" in vswitch.uplinks
        assert "vmnic5" in vswitch.uplinks
        assert "t1" in vswitch.portgroups
        assert "t2" in vswitch.portgroups
        assert 9000 == vswitch.mtu

    def test_set_forged_transmit(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vswitch.set_forged_transmit("protgroup-name", True)
        host.connection.execute_command.assert_called_once_with(
            "esxcli network vswitch standard portgroup policy security set -p protgroup-name -f True"
        )

    def test_change_ens_fpo_support(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        host.connection.execute_command.return_value = ConnectionCompletedProcess(return_code=0, args="", stdout="")
        vswitch.change_ens_fpo_support(True)
        host.connection.execute_command.assert_called_once_with("nsxdp-cli ens fpo set --enable")

    def test_change_ens_fpo_support_provided_vds(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        host.connection.execute_command.return_value = ConnectionCompletedProcess(return_code=0, args="", stdout="")
        vswitch.change_ens_fpo_support(True, "vSphereDistributedSwitch")
        host.connection.execute_command.assert_called_once_with(
            "nsxdp-cli ens fpo set --enable -dvs vSphereDistributedSwitch"
        )

    def test_set_mac_change_policy_enabled(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        portgroup = "test1"
        host.connection.execute_command.return_value = ConnectionCompletedProcess(return_code=0, args="", stdout="..")

        vswitch.set_mac_change_policy(portgroup_name=portgroup, enabled=True)

        assert host.connection.execute_command.call_count == 1
        host.connection.execute_command.assert_called_with(
            command=f"esxcli network vswitch standard portgroup policy security set -p {portgroup} -m True",
            custom_exception=VswitchError,
        )

    def test_set_mac_change_policy_disabled(self, host):
        vswitch = ESXivSwitch(host, "vSwitch0")
        portgroup = "test1"
        host.connection.execute_command.return_value = ConnectionCompletedProcess(return_code=0, args="", stdout="..")
        vswitch.set_mac_change_policy(portgroup_name=portgroup, enabled=False)

        assert host.connection.execute_command.call_count == 1
        host.connection.execute_command.assert_called_with(
            command=f"esxcli network vswitch standard portgroup policy security set -p {portgroup} -m False",
            custom_exception=VswitchError,
        )
