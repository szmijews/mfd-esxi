# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
from textwrap import dedent

import pytest
from packaging.version import Version
from ipaddress import ip_interface
from unittest.mock import MagicMock

from mfd_connect.base import ConnectionCompletedProcess
from mfd_network_adapter.network_interface.feature.virtualization.data_structures import (
    VFInfo,
)
from mfd_esxi.exceptions import ESXiRuntimeError
from mfd_esxi.host import IntnetCliVersion
from mfd_connect import RPyCConnection
from mfd_typing import OSName, PCIAddress
from mfd_network_adapter.network_interface.esxi import ESXiNetworkInterface
from mfd_typing.network_interface import InterfaceInfo


class TestESXiHypervisor:
    @pytest.fixture()
    def interface(self, mocker):
        pci_address = PCIAddress(0, 1, 0, 1)
        name = "vmnic1"
        _connection = mocker.create_autospec(RPyCConnection)
        _connection.get_os_name.return_value = OSName.ESXI

        interface = ESXiNetworkInterface(
            connection=_connection,
            interface_info=InterfaceInfo(pci_address=pci_address, name=name),
        )
        mocker.stopall()
        return interface

    def test_initialize_version(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="VMware ESXi 8.0.0 build-20513097"
        )
        host.initialize_version()
        assert host.esxi_version.version == Version("8.0.0")
        assert host.esxi_version.build == 20513097

    def test_initialize_vswitch(self, host_esxcfg_vswitch_2):
        host_esxcfg_vswitch_2.initialize_vswitch()
        assert len(host_esxcfg_vswitch_2.vswitch) == 2

    def test_initialize_vmknic(self, host_esxcfg_vmknic_1):
        host_esxcfg_vmknic_1.initialize_vmknic()
        assert len(host_esxcfg_vmknic_1.vmknic) == 2

    def test_initialize_mng(self, host_esxcfg_vmknic_1):
        host_esxcfg_vmknic_1.initialize_vmknic()
        host_esxcfg_vmknic_1.initialize_mng()
        assert host_esxcfg_vmknic_1.mng_vmknic.name == "vmk0"
        assert host_esxcfg_vmknic_1.mng_ip == ip_interface("172.31.0.82/16")

    def test_add_vswitch(self, host):
        host.add_vswitch("test")
        assert len(host.vswitch) == 1
        assert host.vswitch[0].name == "test"

    def test_del_vswitch(self, host_esxcfg_vswitch_2):
        host_esxcfg_vswitch_2.initialize_vswitch()
        host_esxcfg_vswitch_2.del_vswitch("ATvSwitchLongName")
        assert len(host_esxcfg_vswitch_2.vswitch) == 1
        assert host_esxcfg_vswitch_2.vswitch[0].name == "vSwitch0"

    def test_set_vswitch(self, host):
        vswitch = host.add_vswitch("test")
        host.set_vswitch(
            name=vswitch.name,
            uplinks=["vmnic4", "vmnic5"],
            portgroups=["t1", "t2"],
            vmknic=False,
        )
        assert "vmnic4" in vswitch.uplinks
        assert "vmnic5" in vswitch.uplinks
        assert "t1" in vswitch.portgroups
        assert "t2" in vswitch.portgroups

    def test_set_vswitch_create(self, host):
        host.set_vswitch(
            name="test",
            uplinks=["vmnic4", "vmnic5"],
            portgroups=["t1", "t2"],
            vmknic=False,
        )
        vswitch = host.vswitch[0]
        assert "vmnic4" in vswitch.uplinks
        assert "vmnic5" in vswitch.uplinks
        assert "t1" in vswitch.portgroups
        assert "t2" in vswitch.portgroups

    def test_find_vswitch(self, host_esxcfg_vswitch_2):
        host_esxcfg_vswitch_2.initialize_vswitch()
        vswitch = host_esxcfg_vswitch_2.find_vswitch(name="vSwitch0")
        assert vswitch.name == "vSwitch0"
        vswitch = host_esxcfg_vswitch_2.find_vswitch(uplink="vmnic10")
        assert vswitch.name == "ATvSwitchLongName"
        vswitch = host_esxcfg_vswitch_2.find_vswitch(portgroup="ATmng")
        assert vswitch.name == "vSwitch0"

    def test_add_vmknic(self, host_esxcfg_vmknic_2):
        vmknic = host_esxcfg_vmknic_2.add_vmknic("PGvmnic0")
        assert len(host_esxcfg_vmknic_2.vmknic) == 1
        vmknic.name = "vmknic2"
        vmknic.portgroup = "PGvmnic0"

    def test_del_vmknic(self, host_esxcfg_vmknic_1):
        host_esxcfg_vmknic_1.initialize_vmknic()
        assert len(host_esxcfg_vmknic_1.vmknic) == 2
        host_esxcfg_vmknic_1.del_vmknic(portgroup="ATvmnic10")
        assert len(host_esxcfg_vmknic_1.vmknic) == 1
        host_esxcfg_vmknic_1.del_vmknic(name="vmk0")
        assert len(host_esxcfg_vmknic_1.vmknic) == 0

    def test_find_vmknic(self, host_esxcfg_vmknic_2):
        host_esxcfg_vmknic_2.add_vmknic("PGvmnic0")
        host_esxcfg_vmknic_2.add_vmknic("ATvmnic10")
        vmknic = host_esxcfg_vmknic_2.find_vmknic(name="vmk2")
        assert vmknic.name == "vmk2"
        vmknic = host_esxcfg_vmknic_2.find_vmknic(portgroup="ATvmnic10")
        assert vmknic.name == "vmk1"
        vmknic = host_esxcfg_vmknic_2.find_vmknic(ip="1.1.1.1")
        assert vmknic.name == "vmk1"
        vmknic = host_esxcfg_vmknic_2.find_vmknic(net="1.0.0.0/8")
        assert vmknic.name == "vmk1"
        vmknic = host_esxcfg_vmknic_2.find_vmknic(net="fe80::0/64")
        assert vmknic.name == "vmk2"

    def test_find_link_partner1(self, host_esxcfg_nics_1):
        lp = host_esxcfg_nics_1.find_link_partner("vmnic2")
        assert lp == "vmnic3"

    def test_find_link_partner2(self, host_esxcfg_nics_2):
        lp = host_esxcfg_nics_2.find_link_partner("vmnic2")
        assert lp == "vmnic3"

    def test_find_link_partner3(self, host_esxcfg_nics_2):
        with pytest.raises(ESXiRuntimeError):
            host_esxcfg_nics_2.find_link_partner("vmnic3")

    def test_find_pf0(self, host_esxcfg_nics_1):
        pf0 = host_esxcfg_nics_1.find_pf0(["vmnic3", "vmnic13", "vmnic8"])
        assert len(pf0) == 3
        assert "vmnic0" in pf0
        assert "vmnic10" in pf0
        assert "vmnic8" in pf0

    def test_get_meminfo(self, host):
        output = """Memory information {
           System memory usage (pages):191681
           Number of NUMA nodes:2
           Number of memory nodes:3
           Number of memory tiers:1
           First valid MPN:1
           Last valid MPN:17301503
           Max valid MPN:274877906944
           Max support RAM (in MB):33585088
        }
        """
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        pattern_dict = {"mem_usage": 191681}
        dict_out = host.get_meminfo()
        assert pattern_dict == dict_out

    def test_get_intnetcli_version_success(self, host):
        output = """int-esx-intnetcli              700.1.8.1.0-15843807                   INT     PartnerSupported  2021-11-24"""  # noqa
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        expected_res = IntnetCliVersion(intnet_ver="1.8.1.0", ddk_ver="700")
        assert expected_res == host.get_intnetcli_version()

    def test_get_intnetcli_version_bad_output(self, host):
        output = """int-esx-intnetcli              bad_version-15843807                   INT     PartnerSupported  2021-11-24"""  # noqa
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        with pytest.raises(ESXiRuntimeError, match="Unknown version of intnetcli installed."):
            host.get_intnetcli_version()

    def test_get_intnetcli_version_missing_out(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1, args="command", stdout=""
        )
        expected_res = IntnetCliVersion(intnet_ver=None, ddk_ver=None)
        assert expected_res == host.get_intnetcli_version()

    def test_get_pci_passthrough_capable_devices_success(self, host):
        # < 7.0 case
        output = dedent(
            """\
        0000:af:00.0
           address: 0000:af:00.0
           segment: 0x0000
           bus: 0xaf
           slot: 0x00
           function: 0x0
           vmkernel name: vmnic4
           passthru capable: true
           parent device: pci 0:174:0:0
           dependent device: pci 0:175:0:2
           reset method: function reset
           fpt sharable: true

        0000:af:00.3
           address: 0000:af:00.3
           segment: 0x0000
           passthru capable: true"""
        )
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        expected_res = {
            PCIAddress(data="0000:af:00.0"): False,
            PCIAddress(data="0000:af:00.3"): False,
        }
        assert expected_res == host.get_pci_passthrough_capable_devices()

    def test_get_pci_passthrough_capable_devices_success_higher_7_0(self, host):
        # >= 7.0 case
        output = dedent(
            """\
        Device ID     Enabled
        ------------  -------
        0000:02:00.0    true
        0000:18:00.0    false
        """
        )
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        expected_res = {
            PCIAddress(data="0000:02:00.0"): True,
            PCIAddress(data="0000:18:00.0"): False,
        }
        assert expected_res == host.get_pci_passthrough_capable_devices()

    def test_get_pci_passthrough_nics_success(self, host):
        output = dedent(
            """\
        0000:af:00.0 8086:1572 8086:0004 255/   /     A P pciPassthru        vmnic8
        0000:af:00.1 8086:1572 8086:0000 255/   /     A P pciPassthru        vmnic9
        0000:af:00.2 8086:1572 8086:0000 255/   /     A V i40en        vmnic10
        0000:5e:09.0 8086:1889 8086:0000 255/   /     @ P pciPassthru  PF_0.94.1_VF_0
        """
        )
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        assert [
            PCIAddress(data="0000:af:00.0"),
            PCIAddress(data="0000:af:00.1"),
        ] == host.get_pci_passthrough_nics()

    def test_get_pci_passthrough_nics_success_esxi_8(self, host):
        # case >= 8.0
        output = dedent(
            """\
        0000:af:00.0               8086:1572 8086:0008  11/   /     A V i40en
        0000:af:00.1               8086:1572 8086:0000  11/   /     A P pciPassthru
        0000:af:02.0               8086:154c 8086:0000 255/   /     @ P pciPassthru
        """
        )
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        assert [PCIAddress(data="0000:af:00.1")] == host.get_pci_passthrough_nics()

    def test_get_pci_passthrough_nics_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Invalid output"
        )
        with pytest.raises(
            ESXiRuntimeError,
            match="Cannot get PCI addresses for PCI passthrough enabled NICs.",
        ):
            host.get_pci_passthrough_nics()

    def test_get_vds_id_success(self, host):
        output = dedent(
            """\
        DSwitch_078
        Name: DSwitch_078
        VDS ID: 50 1e 81 57 81 ea ba d3-94 e9 0f 7b c9 1b da 81
        Class: cswitch
        Num Ports: 3456
        Used Ports: 4
        Configured Ports: 512
        MTU: 1500
        CDP Status: listen
        Beacon Timeout: -1
        Uplinks: vmnic4
        VMware Branded: true
        DVPort:
              Client: vmnic4
              DVPortgroup ID: dvportgroup-117200
              In Use: true
              Port ID: 0

              Client: Base_R83_VM001_078.eth1
              DVPortgroup ID: dvportgroup-117201
              In Use: true
              Port ID: 2"""
        )
        expected_output = "50 1e 81 57 81 ea ba d3-94 e9 0f 7b c9 1b da 81"
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output
        )
        assert expected_output == host.get_vds_id()

    def test_get_vds_id_wrong(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Invalid_output"
        )
        with pytest.raises(ESXiRuntimeError, match="Cannot get VDS ID."):
            host.get_vds_id()

    def test_get_vm_name_by_vf(self, host, interface, mocker):
        vfs = [
            VFInfo(
                vf_id="0",
                pci_address=PCIAddress(domain=0, bus=75, slot=17, func=0),
                owner_world_id="2169609",
            ),
            VFInfo(
                vf_id="1",
                pci_address=PCIAddress(domain=0, bus=75, slot=17, func=1),
                owner_world_id="2169642",
            ),
            VFInfo(
                vf_id="2",
                pci_address=PCIAddress(domain=0, bus=75, slot=17, func=2),
                owner_world_id="2169798",
            ),
            VFInfo(
                vf_id="3",
                pci_address=PCIAddress(domain=0, bus=75, slot=17, func=3),
                owner_world_id="2169831",
            ),
        ]
        output = dedent(
            """AT_ESXI_145
               World ID: 2101442
               Process ID: 0
               VMX Cartel ID: 2101441
               UUID: 56 4d a9 ac 1c ee 5d d7-f1 ae a5 95 f8 3d 2a 2d
               Display Name: AT_ESXI_145
               Config File: /vmfs/volumes/5b645dbf-d27a664c-e76a-1402ec67d6e6/AT_ESXI/AT_ESXI.vmx
            VM2_145
               World ID: 2169831
               Process ID: 0
               VMX Cartel ID: 2169642
               UUID: 56 4d 76 ff f9 9b 86 df-e9 9a e3 10 ac e1 69 80
               Display Name: VM2_145
               Config File: /vmfs/volumes/5b645dbf-d27a664c-e76a-1402ec67d6e6/VM2_145/Base_S12SP3.vmx
            VM1_145
               World ID: 2169832
               Process ID: 0
               VMX Cartel ID: 2169831
               UUID: 56 4d 07 6d 65 0a 82 54-7c d5 90 c5 f7 89 6a a2
               Display Name: VM1_145
               Config File: /vmfs/volumes/5b645dbf-d27a664c-e76a-1402ec67d6e6/VM1_145/Base_S12SP3.vmx
               """
        )

        vf_id = 3  # 'Owner World ID': '2169831'
        results = {
            "6.5.0": "VM1_145",  # 'VMX Cartel ID': '2169831'
            "6.7.0": "VM1_145",  # 'VMX Cartel ID': '2169831'
            "7.0.0": "VM2_145",  # 'World ID': '2169831'
            "7.0.2": "VM2_145",  # 'World ID': '2169831'
            "9.0.0": "VM1_145",  # 'VMX Cartel ID': '2169831'
        }

        mocker.patch.object(interface.virtualization, "get_connected_vfs_info", return_value=vfs)
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=output, stderr="stderr"
        )
        host.connection.get_system_info.side_effect = [
            MagicMock(kernel_version="6.5.0"),
            MagicMock(kernel_version="6.7.0"),
            MagicMock(kernel_version="7.0.0"),
            MagicMock(kernel_version="7.0.2"),
            MagicMock(kernel_version="9.0.0"),
        ]
        assert host.get_vm_name_for_vf_id(vf_id=vf_id, interface=interface) == results["6.5.0"]
        assert host.get_vm_name_for_vf_id(vf_id=vf_id, interface=interface) == results["6.7.0"]
        assert host.get_vm_name_for_vf_id(vf_id=vf_id, interface=interface) == results["7.0.0"]
        assert host.get_vm_name_for_vf_id(vf_id=vf_id, interface=interface) == results["7.0.2"]
        assert host.get_vm_name_for_vf_id(vf_id=vf_id, interface=interface) == results["9.0.0"]
