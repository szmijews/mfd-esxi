# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from unittest.mock import patch, Mock

from mfd_connect.base import ConnectionCompletedProcess
from mfd_esxi.vm_mgr import ESXiVMMgr


class TestESXiVMMgr:
    def test_initialize(self, host_getallvms):
        hv = ESXiVMMgr(host_getallvms)
        hv.initialize()
        assert len(hv.vm) == 2

    def test_clean_all(self, host_getallvms):
        hv = ESXiVMMgr(host_getallvms)
        hv.initialize()
        hv.clean()
        assert len(hv.vm) == 0

    def test_clean_keep(self, host_getallvms):
        hv = ESXiVMMgr(host_getallvms)
        hv.initialize()
        hv.clean(keep="AT_ESXI")
        assert len(hv.vm) == 1
        assert hv.vm[0].name == "AT_ESXI_050"

    def test_prepare_vms(self, host_gold_vmx):
        hv = ESXiVMMgr(host_gold_vmx)
        vms = hv.prepare_vms("datastore_050", "Base_R91", count=3, suffix="test")
        assert hv.gold[0].name == "Base_R91"
        assert len(vms) == 3

    def test_attach_network(self, host_gold_vmx):
        hv = ESXiVMMgr(host_gold_vmx)
        vms = hv.prepare_vms("datastore_050", "Base_R91", count=3, suffix="test")
        hv.attach_network(vms, "test")
        assert vms[0].ethernet[0]["networkName"] == "test"
        assert vms[1].ethernet[0]["networkName"] == "test"
        assert vms[2].ethernet[0]["networkName"] == "test"

    @patch("mfd_esxi.vm_gold.copy", Mock())
    @patch("mfd_esxi.vm_gold.LocalConnection", Mock())
    def test_create_vms(self, host_gold_vmx):
        hv = ESXiVMMgr(host_gold_vmx)
        vms = hv.prepare_vms("datastore_050", "Base_R91", count=3, suffix="test")
        host_gold_vmx.connection.execute_command.side_effect = None
        host_gold_vmx.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="5"
        )
        hv.create_vms(vms)
        assert len(hv.vm) == 3

    @patch("mfd_esxi.vm_gold.copy", Mock())
    @patch("mfd_esxi.vm_gold.LocalConnection", Mock())
    def test_find_vms(self, host_gold_vmx):
        hv = ESXiVMMgr(host_gold_vmx)
        vms = hv.prepare_vms("datastore_050", "Base_R91", count=3, suffix="test")
        host_gold_vmx.connection.execute_command.side_effect = None
        host_gold_vmx.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="5"
        )
        hv.create_vms(vms)
        found = hv.find_vms("Base_R91")
        assert len(found) == 3
        found = hv.find_vms("Base_R90")
        assert len(found) == 0
