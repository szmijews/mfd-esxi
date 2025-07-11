# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Virtual Machine."""

import logging
import re
from ipaddress import IPv4Address, IPv6Address, ip_address
from time import time, sleep
from typing import List, Union, TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level
from .exceptions import ESXiNotFound, ESXiWrongParameter, ESXiRuntimeError, ESXiVMNotRun

if TYPE_CHECKING:
    from mfd_esxi.host import ESXiHypervisor
    from mfd_connect import RPyCConnection
    from mfd_connect.base import ConnectionCompletedProcess

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class ESXiVMBase:
    """Class for VM handling."""

    def __init__(self, owner: "ESXiHypervisor"):
        """Init VM fields."""
        self.owner: "ESXiHypervisor" = owner
        self.id: Union[int, None] = None
        self.name: Union[str, None] = None
        self.datastore: Union[str, None] = None
        self.folder: Union[str, None] = None
        self.ip: Union[IPv4Address, IPv6Address, None] = None
        self.connection: Union["RPyCConnection", None] = None

    def initialize(self, output: str) -> None:
        """Initialize VM based on vim-cmd vmsvc/getallvms output.

        :param output: line of output
        """
        regex = re.search(
            r"(?P<id>\d+)\s*(?P<name>.+)\s+\[(?P<datastore>.+)]\s(?P<folder>.+)/.+.vmx\s+.+\s+vmx-\d+",
            output,
        )
        if not regex:
            raise ESXiNotFound("Could not find information about virtual machine")
        self.id = int(regex.group("id"))
        self.name = regex.group("name").strip()
        self.datastore = regex.group("datastore").strip()
        self.folder = regex.group("folder").strip()

    @staticmethod
    def discover(owner: "ESXiHypervisor") -> List["ESXiVMBase"]:
        """
        Discover all VMs on host.

        :param owner: ESXi host
        :return: list of DVS
        """
        output = owner.execute_command("vim-cmd vmsvc/getallvms", expected_return_codes={0}).stdout
        vms = []

        for line in output.splitlines():
            if line[0].isnumeric() and "vCLS" not in line:
                vm = ESXiVMBase(owner)
                vm.initialize(line)
                vms.append(vm)
        return vms

    def execute_command(self, command: str, **kwargs) -> "ConnectionCompletedProcess":
        """
        Shortcut for execute command.

        :param command: string with command
        :param kwargs: parameters
        :return: result of command
        """
        return self.connection.execute_command(command=command, **kwargs)

    def register(self, file: str) -> None:
        """Register VM.

        :param file: path to vmx file
        """
        if self.id is None:
            command = f"vim-cmd solo/registervm {file}"
            _id = self.owner.execute_command(command, expected_return_codes={0}).stdout
            self.id = int(_id)
        else:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"VM {self.name} already registered")

    def unregister(self) -> None:
        """Unregister VM."""
        if self.id is not None:
            command = f"vim-cmd vmsvc/unregister {self.id}"
            self.owner.execute_command(command, expected_return_codes={0})
            self.id = None
        else:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"VM {self.name} already unregistered",
            )

    def reload(self) -> None:
        """Reload vmx file with VM configuration."""
        if self.id is not None:
            command = f"vim-cmd vmsvc/reload {self.id}"
            self.owner.execute_command(command, expected_return_codes={0})
            return
        raise ESXiRuntimeError("Could not reload configuration of VM that has not been registered")

    def start(self) -> None:
        """Start VM."""
        command = f"vim-cmd vmsvc/power.on {self.id}"
        result = self.owner.execute_command(command, expected_return_codes={0, 1})
        if result.return_code == 0:
            return

        if "The attempted operation cannot be performed in the current state" in result.stderr:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"VM {self.name} already started")
            return
        elif "InsufficientMemoryResourcesFault" in result.stderr:
            raise ESXiVMNotRun("Host does not have sufficient memory pool to power on requested VM")

        raise ESXiRuntimeError(f"Command: {command} rc: {result.return_code} output: {result.stderr}")

    def stop(self) -> None:
        """Stop VM."""
        command = f"vim-cmd vmsvc/power.off {self.id}"
        result = self.owner.execute_command(command, expected_return_codes={0, 1})
        if result.return_code == 0:
            return

        if "The attempted operation cannot be performed in the current state" in result.stderr:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"VM {self.name} already stopped")
            return
        raise ESXiRuntimeError(f"Command: {command} rc: {result.return_code} output: {result.stderr}")

    def shutdown(self, wait: bool = True, timeout: int = 300) -> None:
        """Shutdown Guest OS.

        :param wait: wait for VM to stop
        :param timeout: time to wait
        """
        command = f"vim-cmd vmsvc/power.shutdown {self.id}"
        result = self.owner.execute_command(command, expected_return_codes={0, 1})
        if result.return_code == 0:
            if wait:
                self.wait_for_state("off", timeout=timeout)
            return

        if "The attempted operation cannot be performed in the current state" in result.stderr:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"VM {self.name} already stopped")
            return
        raise ESXiRuntimeError(f"Command: {command} rc: {result.return_code} output: {result.stderr}")

    def reboot(self) -> None:
        """Reboot VM."""
        command = f"vim-cmd vmsvc/power.reboot {self.id}"
        result = self.owner.execute_command(command, expected_return_codes={0, 1})
        if result.return_code == 0:
            return

        if "The attempted operation cannot be performed in the current state" in result.stderr:
            return self.start()
        raise ESXiRuntimeError(f"Command: {command} rc: {result.return_code} output: {result.stderr}")

    def get_state(self) -> str:
        """Get power state of VM."""
        command = f"vim-cmd vmsvc/power.getstate {self.id}"
        output = self.owner.execute_command(command, expected_return_codes={0}).stdout
        if "Powered on" in output:
            return "on"
        if "Powered off" in output:
            return "off"
        raise ESXiRuntimeError(f"Unexpected VM state: {output}")

    def wait_for_state(self, state: str, timeout: int = 60) -> None:
        """Wait for desired state.

        :param state: state on or off
        :param timeout: time to wait
        """
        state = state.lower()
        if state not in ["on", "off"]:
            raise ESXiWrongParameter(f"Wrong parameter provided: state = {state}")

        start = time()
        while time() < start + timeout:
            if state == self.get_state():
                return
            sleep(5)
        raise ESXiRuntimeError(f"Timeout waiting for VM state: {state}")

    def get_guest_mng_ip(self, timeout: int = 300) -> Union[IPv4Address, IPv6Address]:
        """Get management ip address for vm.

        :param timeout: time to get ip address from vm
        :return: mng IP for virtual machine
        """
        ip = self.wait_for_mng_ip(timeout)

        if ip is True:
            # VM is running but is unable to provide the mng ip probably because hang
            raise ESXiVMNotRun("Unable to get mng ip for vm.")
        if ip is False:
            # VM crashed during power on, try one reboot
            self.stop()
            self.start()
            ip = self.wait_for_mng_ip(timeout)
            if isinstance(ip, bool):
                raise ESXiVMNotRun("Unable to get mng ip for vm.")

        self.ip = ip
        return ip

    def wait_for_mng_ip(self, timeout: int = 300) -> Union[IPv4Address, IPv6Address, bool]:
        """Wait timeout seconds for mng ip.

        :param timeout: seconds to wait
        :return: IP of VM or running state if not found
        """
        state = False
        start = time()
        while time() - start < timeout:
            command = f"vim-cmd vmsvc/get.guest {self.id}"
            result = self.owner.execute_command(command, expected_return_codes=None)
            state = 'guestState = "running"' in result.stdout
            if result.return_code != 0:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Command {command} ended with code error: {result.return_code}",
                )
            else:
                pattern = re.compile("ipAddress =.{2}([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+)")
                ips = [ip for ip in re.findall(pattern, result.stdout) if ip_address(ip) in self.owner.mng_ip.network]
                if ips:
                    # We assume that vm have only one mng ip
                    return ip_address(ips[0])
            sleep(5)
        return state
