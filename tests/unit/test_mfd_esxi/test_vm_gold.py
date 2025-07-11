# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from unittest.mock import patch, Mock
from mfd_esxi.vm_gold import ESXiVMGold, ESXiVM
from packaging.version import Version


class TestESXiVMGold:
    def test_initialize(self, host_gold_vmx):
        gold = ESXiVMGold(host_gold_vmx, "datastore_050", "Base_R91")
        gold.initialize()
        assert gold.datastore == "datastore_050"
        assert gold.name == "Base_R91"
        assert gold.firmware == "efi"
        assert gold.guestOS == "other-64"
        assert gold.scsi_dev == "lsisas1068"
        assert gold.primary_vmdk == "Base_R91-000001.vmdk"
        assert gold.primary_flat == "Base_R91-000001-sesparse.vmdk"
        assert gold.parent_vmdk == "Base_R91.vmdk"
        assert gold.parent_flat == "Base_R91-flat.vmdk"


class TestESXiVM:
    @patch("mfd_esxi.vm_gold.copy", Mock())
    @patch("mfd_esxi.vm_gold.LocalConnection", Mock())
    def test_write_vmx(self, host_gold_vmx):
        gold = ESXiVMGold(host_gold_vmx, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        vm.write_vmx()

    def test_attach_network_vmxnet(self, host_gold_vmx):
        gold = ESXiVMGold(host_gold_vmx, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        vm.attach_network("test1")
        vm.attach_network("test2", rss=True)
        assert len(vm.ethernet) == 2

    def test_attach_network_sriov(self, host_gold_vmx, mocker):
        gold = ESXiVMGold(host_gold_vmx, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        adapter = mocker
        adapter.pci_address = mocker
        adapter.pci_address.lspci_short = "1:2.3"
        vm.attach_network("test1", model="sriov", pf=adapter)
        assert len(vm.ethernet) == 0
        assert len(vm.pciPassthru) == 1

    def test_attach_network_ptp_old_esxi(self, host_gold_vmx_ptp_old_esxi, mocker):
        gold = ESXiVMGold(host_gold_vmx_ptp_old_esxi, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        host_gold_vmx_ptp_old_esxi.esxi_version = mocker
        host_gold_vmx_ptp_old_esxi.esxi_version.version = Version("8.0.2")
        adapter = mocker
        adapter.name = "vmnic4"
        vm.attach_network("test1", model="ptp", pf=adapter)
        host_gold_vmx_ptp_old_esxi.connection.execute_command.assert_called_with(
            command="lspci -p | grep :32:01.0", shell=True
        )
        assert len(vm.ethernet) == 0
        assert len(vm.pciPassthru) == 1
        if len(vm.pciPassthru) == 1:
            assert vm.pciPassthru[0]["id"] == "00000:050:01.0"

    def test_attach_network_ptp_new_esxi(self, host_gold_vmx_ptp_new_esxi, mocker):
        gold = ESXiVMGold(host_gold_vmx_ptp_new_esxi, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        host_gold_vmx_ptp_new_esxi.esxi_version = mocker
        host_gold_vmx_ptp_new_esxi.esxi_version.version = Version("8.0.3")
        adapter = mocker
        adapter.name = "vmnic4"
        vm.attach_network("test1", model="ptp", pf=adapter)
        host_gold_vmx_ptp_new_esxi.connection.execute_command.assert_called_with(
            command="lspci -p | grep :32:01.0", shell=True
        )
        assert len(vm.ethernet) == 0
        assert len(vm.pciPassthru) == 1
        if len(vm.pciPassthru) == 1:
            assert vm.pciPassthru[0]["id"] == "00000:050:01.0"

    def test_attach_network_ptp_new_esxi_hex(self, host_gold_vmx_ptp_new_esxi_hex, mocker):
        gold = ESXiVMGold(host_gold_vmx_ptp_new_esxi_hex, "datastore_050", "Base_R91")
        gold.initialize()
        vm = ESXiVM(gold=gold, name="test", mng="test")
        host_gold_vmx_ptp_new_esxi_hex.esxi_version = mocker
        host_gold_vmx_ptp_new_esxi_hex.esxi_version.version = Version("8.0.3")
        adapter = mocker
        adapter.name = "vmnic4"
        vm.attach_network("test1", model="ptp", pf=adapter)
        host_gold_vmx_ptp_new_esxi_hex.connection.execute_command.assert_called_with(
            command="lspci -p | grep :b1:01.0", shell=True
        )
        assert len(vm.ethernet) == 0
        assert len(vm.pciPassthru) == 1
        if len(vm.pciPassthru) == 1:
            assert vm.pciPassthru[0]["id"] == "00000:177:01.0"
