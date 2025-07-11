# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

import pytest
from ipaddress import ip_interface, ip_address

from mfd_connect.base import ConnectionCompletedProcess
from .fixtures import getallvms
from mfd_esxi.vm_base import ESXiVMBase
from mfd_esxi.exceptions import ESXiRuntimeError, ESXiVMNotRun, ESXiWrongParameter


class TestESXiVMBase:
    def test_initialize1(self):
        vm = ESXiVMBase(None)
        lines = getallvms.splitlines()
        vm.initialize(lines[1])
        assert vm.id == 1
        assert vm.name == "AT_ESXI_050"
        assert vm.datastore == "datastore_050"
        assert vm.folder == "AT_ESXI"

    def test_initialize2(self):
        vm = ESXiVMBase(None)
        lines = getallvms.splitlines()
        vm.initialize(lines[2])
        assert vm.id == 24
        assert vm.name == "Test Test [Test] [Test]"
        assert vm.datastore == "datastore_050_vmfs6"
        assert vm.folder == "Test"

    def test_discover(self, host_getallvms):
        vms = ESXiVMBase.discover(host_getallvms)
        assert len(vms) == 2

    def test_register(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="5"
        )
        vm = ESXiVMBase(host)
        vm.register("path")
        assert vm.id == 5
        vm.register("path")
        assert vm.id == 5

    def test_unregister(self, host):
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.unregister()
        assert vm.id is None
        vm.unregister()
        assert vm.id is None

    def test_reload(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.reload()
        vm.id = None
        with pytest.raises(ESXiRuntimeError):
            vm.reload()

    def test_start(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.start()

    def test_start_already_started(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1,
            args="command",
            stdout="",
            stderr="The attempted operation cannot be performed in the current state",
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.start()

    def test_start_insufficient_memory(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1,
            args="command",
            stdout="",
            stderr="InsufficientMemoryResourcesFault",
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiVMNotRun):
            vm.start()

    def test_start_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1, args="command", stdout="", stderr=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiRuntimeError):
            vm.start()

    def test_stop(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.stop()

    def test_stop_already_stopped(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1,
            args="command",
            stdout="",
            stderr="The attempted operation cannot be performed in the current state",
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.stop()

    def test_stop_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1, args="command", stdout="", stderr=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiRuntimeError):
            vm.stop()

    def test_shutdown(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Powered off"
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.shutdown(wait=True, timeout=10)

    def test_shutdown_already_stopped(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1,
            args="command",
            stdout="",
            stderr="The attempted operation cannot be performed in the current state",
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.shutdown()

    def test_shutdown_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1, args="command", stdout="", stderr=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiRuntimeError):
            vm.shutdown()

    def test_reboot(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.reboot()

    def test_reboot_already_stopped(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1,
            args="command",
            stdout="",
            stderr="The attempted operation cannot be performed in the current state",
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.reboot()

    def test_reboot_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=1, args="command", stdout="", stderr=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiRuntimeError):
            vm.reboot()

    def test_getstate_off(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Powered off"
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        assert vm.get_state() == "off"

    def test_getstate_on(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Powered on"
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        assert vm.get_state() == "on"

    def test_getstate_error(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout=""
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        with pytest.raises(ESXiRuntimeError):
            vm.get_state()

    def test_wait_for_state_off(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Powered off"
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.wait_for_state("off")

    def test_wait_for_state_on(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="command", stdout="Powered on"
        )
        vm = ESXiVMBase(host)
        vm.id = 5
        vm.wait_for_state("on")

    def test_wait_for_state_wrong_parameter(self, host):
        vm = ESXiVMBase(host)
        with pytest.raises(ESXiWrongParameter):
            vm.wait_for_state(state="")

    def test_get_guest_mng_ip(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0,
            args="command",
            stdout='guestState = "running"\nipAddress = "1.1.10.1"',
        )
        host.mng_ip = ip_interface("1.1.1.1/8")
        vm = ESXiVMBase(host)
        vm.id = 5
        assert vm.get_guest_mng_ip() == ip_address("1.1.10.1")

    def test_wait_for_mng_ip(self, host):
        host.connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0,
            args="command",
            stdout='guestState = "running"\nipAddress = "1.1.10.1"',
        )
        host.mng_ip = ip_interface("1.1.1.1/8")
        vm = ESXiVMBase(host)
        vm.id = 5
        assert vm.wait_for_mng_ip() == ip_address("1.1.10.1")
