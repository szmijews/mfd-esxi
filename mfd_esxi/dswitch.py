# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Support for local Distributed Switch."""

import re

from .exceptions import ESXiNotFound, ESXiNameException
from ipaddress import IPv4Interface, IPv6Interface
from .vmknic import Vmknic
from time import sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .host import ESXiHypervisor

ESXI_PORTGROUP_VMKNIC = "PG"
UPLINK_NAME = "uplink{}"
ESXI_DSWITCH_NAME_MAX_LEN = 16
ESXI_DPORTGROUP_NAME_MAX_LEN = 37
ENS_SWITCH_SLEEP_SECONDS = 5
ESXI_MAX_LCORES = 8


class ESXiDVSwitch:
    """Class for Distributed DSwitch."""

    def __init__(self, owner: "ESXiHypervisor", name: str):
        """Initialize Distributed Switch object."""
        self.portgroups = []
        self.uplinks = {}
        self.owner = owner
        self.mtu = 1500
        self.name = name
        self.ens_sw_id: int | None = None

    @staticmethod
    def _find_name(line: str) -> str:
        """
        Find name of Distributed Switch in output.

        :param line: line of text from esxcfg-vswitch-l
        :return: Name of the Distributed Switch,
        returning longer name since ESXI limits it to 16 characters but it is possible to create longer name.
        """
        m1 = line[0:ESXI_DSWITCH_NAME_MAX_LEN].strip()
        m2 = line.split()[0]
        return m1 if len(m1) > len(m2) else m2

    def initialize(self, output: str) -> None:
        """
        Initialize Distributed Switch object.

        :param output: Output from esxcfg-vswitch command.
        """
        self.portgroups = []

        lines = output.splitlines()
        nr = self._parse_switch_details(lines)
        self._parse_portgroups(lines, nr)

    def _parse_switch_details(self, lines: list[str]) -> int:
        """
        Parse switch details such as MTU and uplinks.

        :param lines: List of lines from the command output.
        :return: Line number where the switch details end.
        """
        for line in range(len(lines)):
            if lines[line].startswith("DVS Name"):
                nr = line + 1
                if self.name == ESXiDVSwitch._find_name(lines[nr]):
                    fields = lines[nr].split()
                    if "vmnic" in fields[-1]:
                        self.mtu = int(fields[-2])
                        for index, uplink in enumerate(fields[-1].split(",")):
                            self.uplinks[UPLINK_NAME.format(index)] = uplink
                    else:
                        self.mtu = int(fields[-1])
                    return nr
        raise ESXiNotFound(f"Could not find vSwitch {self.name}")

    def _parse_portgroups(self, lines: list[str], start_line: int) -> None:
        """
        Parse portgroups from the command output.

        :param lines: List of lines from the command output.
        :param start_line: Line number to start parsing portgroups.
        """
        capture = False
        for line in range(start_line, len(lines)):
            if lines[line].startswith("DVS Name"):
                break
            if lines[line].lstrip().startswith("DVPort ID"):
                capture = True
                continue

            if capture:
                name = lines[line][2 : 2 + ESXI_DPORTGROUP_NAME_MAX_LEN].strip()
                if len(name) > 0:
                    self.portgroups.append(name)
                else:
                    capture = False

    def refresh(self) -> None:
        """Refresh Distributed Switch object."""
        output = self.owner.execute_command("esxcfg-vswitch -l").stdout
        self.initialize(output)

    @staticmethod
    def discover(owner: "ESXiHypervisor") -> list["ESXiDVSwitch"]:
        """
        Discover Distributed Switches on the ESXi host.

        :param owner: The ESXiHypervisor instance to discover switches on.
        :return: A list of ESXiDVSwitch objects representing the discovered switches.
        """
        output = owner.execute_command("esxcfg-vswitch -l").stdout
        dswitches = []
        lines = iter(output.splitlines())  # Create an iterator from the lines

        for line in lines:
            if line.startswith("DVS Name"):
                name = ESXiDVSwitch._find_name(next(lines, ""))  # Use the iterator to fetch the next line
                dswitch = ESXiDVSwitch(owner, name)
                dswitch.initialize(output)
                dswitches.append(dswitch)

        return dswitches

    def reconfigure(
        self,
        uplinks: list[str],
        portgroups: list[str] | None = None,
        mtu: int = 1500,
        vmknic: bool = True,
    ) -> None:
        """
        Reconfigure Distributed Switch, create/remove uplinks and portgroups.

        :param uplinks: List of uplink (vmnic) names.
        :param portgroups: List of portgroup names (default is None).
        :param mtu: MTU value (default is 1500).
        :param vmknic: Whether to create portgroups for vmknic adapters (default is True).
        """
        portgroups = portgroups or []
        self.del_all_vmknics()
        self.unlink_all_adapters()

        for portgroup in self.portgroups.copy():
            if vmknic and portgroup.startswith(f"{ESXI_PORTGROUP_VMKNIC}vmnic"):
                vmnic = portgroup[len(ESXI_PORTGROUP_VMKNIC) :]
                if vmnic not in self.uplinks.values():
                    self.del_portgroup(portgroup)
            elif portgroup not in portgroups:
                self.del_portgroup(portgroup)

        self.configure(uplinks=uplinks, portgroups=portgroups, mtu=mtu, vmknic=vmknic)

    def configure(
        self,
        uplinks: list[str],
        portgroups: list[str] | None = None,
        mtu: int = 1500,
        vmknic: bool = True,
    ) -> None:
        """
        Configure the vSwitch by creating uplinks, portgroups, and setting MTU.

        :param uplinks: List of uplink (vmnic) names.
        :param portgroups: List of portgroup names (default is None).
        :param mtu: MTU value (default is 1500).
        :param vmknic: Whether to create portgroups for vmknic adapters (default is True).
        """
        portgroups = portgroups or []

        self.set_uplink_number(len(uplinks))
        for uplink in uplinks:
            self.link_adapter(uplink)

        for portgroup in portgroups:
            if portgroup not in self.portgroups:
                self.add_portgroup(portgroup)

        if vmknic:
            ip_num = 1
            for uplink in self.uplinks:
                portgroup = f"{ESXI_PORTGROUP_VMKNIC}{uplink}"
                if portgroup not in self.portgroups:
                    self.add_portgroup(portgroup)
                    # Add vmknic with temporary IP address that will be changed in the later configuration
                    self.add_vmknic(
                        port_name=portgroup,
                        mtu=mtu,
                        ip=IPv4Interface(f"20.20.20.{ip_num}/8"),
                    )
                    ip_num += 1

        if self.mtu != mtu:
            self.set_mtu(mtu)

        for vmknic in self.owner.vmknic:
            if vmknic.portgroup in self.portgroups and vmknic.mtu != mtu:
                vmknic.set_mtu(mtu)

    # Commands
    @staticmethod
    def add_dswitch_esxcfg(owner: "ESXiHypervisor", name: str) -> "ESXiDVSwitch":
        """
        Add local Distributed Switch for ENS.

        :param owner: ESXi host.
        :param name: Name of the switch.
        """
        if not re.match(r"^[A-Za-z0-9_]+$", name):
            raise ESXiNameException("Switch name should contain only letters, digits and underscore")
        owner.connection.execute_command(f"esxcfg-vswitch -a {name} --dvswitch --impl-class=vswitch")
        return ESXiDVSwitch(owner, name)

    def del_dswitch_esxcfg(self) -> None:
        """Delete local Distributed VSwitch from ESXi system using esxcfg command."""
        command = f"esxcfg-vswitch -d --dvswitch {self.name}"
        self.owner.execute_command(command, expected_return_codes={0})

    def set_uplink_number(self, uplink_number: int) -> None:
        """
        Set number of uplinks.

        :param uplink_number: How many ports should have Distributed Switch.
        """
        command = f"net-dvs -U {str(uplink_number)} {self.name}"
        self.owner.execute_command(command)
        self.uplinks = dict((UPLINK_NAME.format(str(idx)), None) for idx in range(uplink_number))

    def add_vmk_esxcfg(self, port_name: str, ip: IPv4Interface | IPv6Interface, mtu: int) -> None:
        """
        Add VMKernel NIC to port with specified ip and net mask using esxcfg command.

        :param port_name: Name of the port.
        :param ip: IP address to be assigned.
        :param mtu: MTU size.
        """
        command = f"esxcfg-vmknic -a -i {ip.ip} -n {ip.netmask} -m {mtu} -s {self.name} -v {port_name}"
        self.owner.execute_command(command)

    def del_vmk_esxcfg(self, vmk: Vmknic) -> None:
        """
        Delete VMKernel NIC from port using esxcfg command.

        :param vmk: VMKernel NIC to be deleted.
        """
        command = f"esxcfg-vmknic -d {vmk.name} -s {self.name} -v {vmk.portgroup}"
        self.owner.execute_command(command)

    def link_adapter_esxcfg(self, name: str, uplink: str) -> None:
        """
        Link adapter to Distributed Switch using esxcfg command.

        :param name: Name of the vmnic.
        :param uplink: Name of the uplink.
        """
        command = f"esxcfg-vswitch -P {name} -V {uplink} {self.name}"
        self.owner.execute_command(command)

    def unlink_adapter_esxcfg(self, name: str, uplink: str) -> None:
        """
        Unlink adapter from Distributed Switch using esxcfg command.

        :param name: Name of the vmnic.
        :param uplink: Name of the uplink.
        """
        command = f"esxcfg-vswitch -Q {name} -V {uplink} {self.name}"
        self.owner.execute_command(command)

    def enable_thread_load_balancer(self) -> None:
        """Enable thread load balancer for Distributed Switch."""
        command = f"LC_ALL=en_US.UTF-8  nsxdp-cli ens tlb status -dvs {self.name} --enable"
        self.owner.execute_command(command, expected_return_codes={0}, shell=True)

    def disable_thread_load_balancer(self) -> None:
        """Disable thread load balancer for Distributed Switch."""
        command = f"LC_ALL=en_US.UTF-8  nsxdp-cli ens tlb status -dvs {self.name} --disable"
        self.owner.execute_command(command, expected_return_codes={0}, shell=True)

    # Logic for Distributed Switch
    def link_adapter(self, name: str) -> None:
        """
        Link adapter to Distributed Switch.

        :param name: Name of the vmnic.
        """
        # Find free uplink to use
        for uplink_name, uplink in self.uplinks.items():
            if uplink is None:
                self.link_adapter_esxcfg(name, uplink_name)
                self.uplinks[uplink_name] = name
                return
        raise RuntimeError("No free uplinks to use")

    def unlink_adapter(self, name: str) -> None:
        """
        Unlink adapter from Distributed Switch.

        :param name: Name of the vmnic.
        """
        uplink_name = None
        for uplink in self.uplinks:
            if self.uplinks[uplink] == name:
                uplink_name = uplink
                break
        self.unlink_adapter_esxcfg(name, uplink_name)

        # Release uplink reserved by adapter
        self.uplinks[uplink_name] = None

    def unlink_all_adapters(self) -> None:
        """Unlink all adapters from Distributed Switch."""
        for adapter in self.uplinks.values():
            if adapter:
                self.unlink_adapter(adapter)

    def add_portgroup(self, name: str) -> None:
        """
        Add portgroup to Distributed Switch.

        :param name: Name of the portgroup.
        """
        if not name:
            raise ESXiNameException("Portgroup name cannot be empty")
        command = f"net-dvs -A -p {name} {self.name}"
        self.owner.execute_command(command)
        self.portgroups.append(name)

    def del_portgroup(self, name: str) -> None:
        """
        Delete portgroup from Distributed Switch.

        :param name: Name of the portgroup.
        """
        if name not in self.portgroups:
            raise ESXiNotFound(f"Portgroup {name} not found in {self.name}")
        command = f"net-dvs -D -p {name} {self.name}"
        self.owner.execute_command(command)
        self.portgroups.remove(name)

    def set_portgroup_vlan(self, name: str, vlan: int) -> None:
        """
        Set VLAN for portgroup.

        :param name: Name of the portgroup.
        :param vlan: VLAN ID.
        """
        if vlan < 0 or vlan > 4095:
            raise ValueError("VLAN ID should be in range 0-4095")

        if vlan != 4095:
            command = (
                f"LC_ALL=en_US.UTF-8 nsxdp-cli vswitch vlan policy set --no-guest-tagging --vlan {vlan} "
                f"-p {name} -dvs {self.name}"
            )
        else:
            command = (
                f"LC_ALL=en_US.UTF-8 nsxdp-cli vswitch vlan policy set --guest-tagging -p {name} -dvs {self.name}"
            )
        self.owner.execute_command(command, shell=True)

    def add_vmknic(self, port_name: str, ip: IPv4Interface | IPv6Interface, mtu: int = 1500) -> Vmknic:
        """
        Add VMKernel NIC to port with specified ip and net mask.

        :param port_name: Name of the port.
        :param ip: IP address to be assigned.
        :param mtu: MTU size.
        """
        # Add new vmk adapter
        self.add_vmk_esxcfg(port_name, ip, mtu)

        # Create new Vmknic object and add it to host vmknic list
        output = self.owner.execute_command("esxcfg-vmknic -l").stdout
        for line in output.splitlines():
            if f" {port_name} " in line:
                name = line.split()[0]
                vmknic = Vmknic(self.owner, name)
                vmknic.initialize(output)
                self.owner.vmknic.append(vmknic)
                return vmknic
        raise ESXiNotFound(f"VMKernel NIC in port {port_name} not found")

    def del_vmknic(self, vmknic: Vmknic) -> None:
        """
        Delete VMKernel NIC from port.

        :param vmknic: VMKernel NIC to be deleted.
        """
        if vmknic not in self.owner.vmknic:
            raise ESXiNotFound(f"VMKernel NIC {vmknic.name} not found in {self.name}")
        self.del_vmk_esxcfg(vmknic)
        self.owner.vmknic.remove(vmknic)

    def del_all_vmknics(self) -> None:
        """Delete all VMKernel NICs."""
        for vmknic in self.owner.vmknic:
            if vmknic.portgroup in self.portgroups:
                self.del_vmknic(vmknic)

    def get_dswitch_id(self) -> str:
        """Get Distributed Switch ID."""
        command = f"net-dvs -l {self.name}"
        output = self.owner.execute_command(command, expected_return_codes={0}).stdout
        dvs_id = output.split("\n")[0][7:54]
        return dvs_id

    def set_mtu(self, mtu: int) -> None:
        """
        Set MTU for Distributed Switch.

        :param mtu: MTU size.
        """
        if mtu < 1500 or mtu > 9000:
            raise ValueError("MTU should be in range 1500-9000")
        command = f"esxcfg-vswitch --mtu {mtu} {self.name}"
        self.owner.execute_command(command)
        self.mtu = mtu

    def get_ens_switch_id(self) -> int:
        """Get ENS switch ID."""
        command = "LC_ALL=en_US.UTF-8 nsxdp-cli ens switch list"
        output = self.owner.execute_command(command, expected_return_codes={0}, shell=True).stdout
        for line in output.splitlines():
            if line.startswith(f"{self.name} "):
                return int(line.split()[1])
        raise RuntimeError(f"Could not find ENS DVS {self.name}")

    def enable_ens(self) -> None:
        """Enable ENS on Distributed Switch."""
        command = f"esxcfg-vswitch -y {self.name}"
        self.owner.execute_command(command)
        self.ens_sw_id = self.get_ens_switch_id()
        sleep(ENS_SWITCH_SLEEP_SECONDS)

    def disable_ens(self) -> None:
        """Disable ENS on Distributed Switch."""
        command = f"esxcfg-vswitch -Y {self.name}"
        self.owner.execute_command(command)
        sleep(ENS_SWITCH_SLEEP_SECONDS)
        self.del_ens_lcores()

    def add_ens_lcores(self, lcores: int) -> None:
        """
        Add ENS lcores to Distributed Switch.

        :param lcores: Number of lcores to be added.
        """
        lcores = min(lcores, ESXI_MAX_LCORES)

        command = "esxcli network ens lcore list"
        output = self.owner.execute_command(command, expected_return_codes={0}).stdout
        lines = output.splitlines()
        del lines[:2]

        numbers = []
        for line in lines:
            number = int(line.split()[0])
            numbers.append(number)

            if f" {self.name} " in line:
                lcores -= 1
            if "Not set" in line:
                command = f"esxcli network ens lcore switch add --switch {self.name} --lcore-id {number}"
                self.owner.execute_command(command, expected_return_codes={0})
                lcores -= 1
            if lcores == 0:
                break

        number = 0
        while lcores > 0:
            if number not in numbers:
                command = f"esxcli network ens lcore add --lcore-id {number}"
                self.owner.execute_command(command, expected_return_codes={0})
                command = f"esxcli network ens lcore switch add --switch {self.name} --lcore-id {number}"
                self.owner.execute_command(command, expected_return_codes={0})
                lcores -= 1
            number += 1

    def del_ens_lcores(self) -> None:
        """Delete ENS lcores from Distributed Switch."""
        command = "esxcli network ens lcore list"
        output = self.owner.execute_command(command, expected_return_codes={0}).stdout
        lines = output.splitlines()
        del lines[:2]

        for line in lines:
            if "Not set" in line:
                command = f"esxcli network ens lcore remove -l {line.split()[0]}"
                self.owner.execute_command(command, expected_return_codes={0})

    def migrate_ens_lcores(self) -> None:
        """Migrate ports on ENS switch to different lcores."""
        self.disable_thread_load_balancer()

        command = f"LC_ALL=en_US.UTF-8 nsxdp-cli ens port list --sw-id {self.ens_sw_id} | grep VNIC"
        output = self.owner.execute_command(command, expected_return_codes={0}, shell=True).stdout

        core = 0
        for line in output.splitlines():
            pid = int(line.split()[1])

            command = (
                f"LC_ALL=en_US.UTF-8 nsxdp-cli ens port migrate --sw-id {self.ens_sw_id} "
                f"--port-id {pid} --lcore-id {core} --dir 0"
            )
            self.owner.execute_command(command, expected_return_codes={0}, shell=True)
            command = (
                f"LC_ALL=en_US.UTF-8 nsxdp-cli ens port migrate --sw-id {self.ens_sw_id} "
                f"--port-id {pid} --lcore-id {core} --dir 1"
            )
            self.owner.execute_command(command, expected_return_codes={0}, shell=True)

            core = (core + 1) % ESXI_MAX_LCORES

    def del_dswitch(self) -> None:
        """Delete local Distributed VSwitch."""
        self.del_all_vmknics()
        self.del_dswitch_esxcfg()