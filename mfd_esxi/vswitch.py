# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Support for standard vSwitch."""

import re
from typing import List, TYPE_CHECKING
from .exceptions import ESXiNotFound, ESXiNameException, VswitchError

if TYPE_CHECKING:
    from .host import ESXiHypervisor

ESXI_VSWITCH_NAME_MAX_LEN = 16
ESXI_PORTGROUP_NAME_MAX_LEN = 39
ESXI_PORTGROUP_VMKNIC = "PG"


class ESXivSwitch:
    """Class for standard vSwitch."""

    def __init__(self, owner: "ESXiHypervisor", name: str):
        """
        Initialize vSwitch.

        :param owner: ESXi host
        :param name: name of vSwitch
        """
        self.owner = owner
        self.name = name
        self.mtu = 1500
        self.uplinks = []
        self.portgroups = []

    @staticmethod
    def _find_name(line: str) -> str:
        """Find name of vSwitch in output.

        :param line: line of text from esxcfg-vswitch-l
        """
        m1 = line[0:ESXI_VSWITCH_NAME_MAX_LEN].strip()
        m2 = line.split()[0]
        return m1 if len(m1) > len(m2) else m2

    def initialize(self, output: str) -> None:
        """
        Initialize vSwitch based on esxcfg-vswitch -l output.

        :param output: output of esxcfg-vswitch -l
        """
        self.portgroups = []

        lines = output.splitlines()
        for line in range(len(lines)):
            if lines[line].startswith("Switch Name"):
                nr = line + 1
                if self.name == ESXivSwitch._find_name(lines[nr]):
                    fields = lines[nr].split()
                    if "vmnic" in fields[-1]:
                        self.mtu = int(fields[-2])
                        self.uplinks = fields[-1].split(",")
                    else:
                        self.mtu = int(fields[-1])
                    break
                continue
        else:
            raise ESXiNotFound(f"Could not find vSwitch {self.name}")

        capture = False
        for line in range(nr, len(lines)):
            if lines[line].startswith("Switch Name"):
                break
            if lines[line].startswith("  PortGroup Name"):
                capture = True
                continue
            if capture:
                name = lines[line][2 : 2 + ESXI_PORTGROUP_NAME_MAX_LEN].strip()
                if len(name) > 0:
                    self.portgroups.append(name)
                else:
                    capture = False

    def refresh(self) -> None:
        """Refresh setting of vSwitch."""
        output = self.owner.execute_command("esxcfg-vswitch -l").stdout
        self.initialize(output)

    @staticmethod
    def discover(owner: "ESXiHypervisor") -> List["ESXivSwitch"]:
        """
        Discover all vSwitches on host.

        :param owner: ESXi host
        :return: list of vSwitches
        """
        output = owner.execute_command("esxcfg-vswitch -l").stdout
        vswitches = []

        capture_vswitch = False
        for line in output.splitlines():
            if capture_vswitch:
                name = ESXivSwitch._find_name(line)
                vswitch = ESXivSwitch(owner, name)
                vswitch.initialize(output)
                vswitches.append(vswitch)
                capture_vswitch = False
                continue
            if line.startswith("Switch Name"):
                capture_vswitch = True
                continue

        return vswitches

    @staticmethod
    def add_vswitch(owner: "ESXiHypervisor", name: str) -> "ESXivSwitch":
        """
        Create vSwitch.

        :param owner: ESXi host
        :param name: name of vSwitch
        :return: vSwitch object
        """
        if re.match(r"^[A-Za-z0-9_]+$", name):
            owner.execute_command(f"esxcli network vswitch standard add -v {name}")
            return ESXivSwitch(owner, name)
        raise ESXiNameException("Switch name should contain only letters, digits and underscore")

    def del_vswitch(self) -> None:
        """Delete vSwitch."""
        for portgroup in self.portgroups:
            for vmknic in self.owner.vmknic:
                if vmknic.portgroup == portgroup:
                    self.owner.del_vmknic(portgroup=portgroup)
                    break
        self.owner.execute_command(f"esxcli network vswitch standard remove -v {self.name}")

    def set_mtu(self, mtu: int = 1500) -> None:
        """
        Change MTU.

        :param mtu: MTU value
        """
        command = f"esxcli network vswitch standard set -m {mtu} -v {self.name}"
        self.owner.execute_command(command)
        self.mtu = mtu

    def add_uplink(self, name: str) -> None:
        """
        Add uplink.

        :param name: vmnic name
        """
        if name not in self.uplinks:
            command = f"esxcli network vswitch standard uplink add -u {name} -v {self.name}"
            self.owner.execute_command(command)
            self.uplinks.append(name)

    def del_uplink(self, name: str) -> None:
        """
        Remove uplink.

        :param name: name of uplink
        """
        command = f"esxcli network vswitch standard uplink remove -u {name} -v {self.name}"
        self.owner.execute_command(command)
        self.uplinks.remove(name)

    def add_portgroup(self, name: str) -> None:
        """
        Create portgroup.

        :param name: name of portgroup
        """
        if name not in self.portgroups:
            if re.match(r"^[A-Za-z0-9_]+$", name):
                command = f"esxcli network vswitch standard portgroup add -p {name} -v {self.name}"
                self.owner.execute_command(command)
                self.portgroups.append(name)
                return
            raise ESXiNameException("Portgroup name should contain only letters, digits and underscore")

    def del_portgroup(self, name: str) -> None:
        """
        Remove portgroup.

        :param name: name of portgroup
        """
        for vmknic in self.owner.vmknic:
            if vmknic.portgroup == name:
                self.owner.del_vmknic(portgroup=name)
                break
        command = f"esxcli network vswitch standard portgroup remove -p {name} -v {self.name}"
        self.owner.execute_command(command)
        self.portgroups.remove(name)

    def set_portgroup_vlan(self, name: str, vlan: int = 0) -> None:
        """
        Set VLAN of portgroup.

        :param name: name of portgroup
        :param vlan: VLAN number (0 - no vlan, 4095 - all vlans)
        """
        command = f"esxcli network vswitch standard portgroup set -v {vlan} -p {name}"
        self.owner.execute_command(command)

    def set_portgroup_uplinks(self, name: str, uplinks: List[str]) -> None:
        """
        Set uplinks of portgroup.

        :param name: name of porgroup
        :param uplinks: list of uplink names
        """
        links = ",".join(uplinks)
        command = f"esxcli network vswitch standard portgroup policy failover set -a {links} -s '' -p {name}"
        self.owner.execute_command(command)

    def reconfigure(
        self,
        uplinks: List[str],
        portgroups: List[str] = (),
        mtu: int = 1500,
        vmknic: bool = True,
    ) -> None:
        """
        Reconfigure vSwitch, create/remove uplinks and portgroups.

        Create vmknic adapters, set MTU.
        Recover policy of vSwitch and all portgroups.

        :param uplinks: list of uplink names
        :param portgroups: list of portgroup names
        :param mtu: MTU value (default 1500)
        :param vmknic: create portgroups for vmknic adapters and add them
        """
        for uplink in self.uplinks.copy():
            if uplink not in uplinks:
                self.del_uplink(uplink)

        for uplink in uplinks:
            if uplink not in self.uplinks:
                self.add_uplink(uplink)

        self.restore_vswitch_default()

        for portgroup in self.portgroups.copy():
            if vmknic and portgroup.startswith(f"{ESXI_PORTGROUP_VMKNIC}vmnic"):
                vmnic = portgroup[len(ESXI_PORTGROUP_VMKNIC) :]
                if vmnic not in uplinks:
                    self.del_portgroup(portgroup)
            elif portgroup not in portgroups:
                self.del_portgroup(portgroup)

        self.restore_portgroups_default()

        self.configure(uplinks=uplinks, portgroups=portgroups, mtu=mtu, vmknic=vmknic)

    def configure(  # noqa: C901
        self,
        uplinks: List[str],
        portgroups: List[str] = (),
        mtu: int = 1500,
        vmknic: bool = True,
    ) -> None:
        """
        Configure freshly created vSwitch, create uplinks and portgroups, set MTU.

        :param uplinks: list of uplink names
        :param portgroups: list of portgroup names
        :param mtu: MTU value (default 1500)
        :param vmknic: create portgroups for vmknic adapters and add them
        """
        for uplink in uplinks:
            if uplink not in self.uplinks:
                self.add_uplink(uplink)

        for portgroup in portgroups:
            if portgroup not in self.portgroups:
                self.add_portgroup(portgroup)

        for uplink in uplinks:
            portgroup = f"{ESXI_PORTGROUP_VMKNIC}{uplink}"
            if vmknic and portgroup not in self.portgroups:
                self.add_portgroup(portgroup)
                self.set_portgroup_uplinks(portgroup, [uplink])
                self.owner.add_vmknic(portgroup=portgroup, mtu=mtu)

        if self.mtu != mtu:
            self.set_mtu(mtu)

        for vmknic in self.owner.vmknic:
            if vmknic.portgroup in self.portgroups:
                if vmknic.mtu != mtu:
                    vmknic.set_mtu(mtu)

    def restore_vswitch_default(self) -> None:
        """Restore default vSwitch policy."""
        uplinks = ",".join(self.uplinks)
        command = (
            f"esxcli network vswitch standard policy failover set "
            f"-v {self.name} -a {uplinks} "
            f"-b true -f link -l portid -n true -s ''"
        )
        self.owner.execute_command(command)
        command = f"esxcli network vswitch standard policy security set " f"-f false -m false -p false -v {self.name}"
        self.owner.execute_command(command)
        command = f"esxcli network vswitch standard policy shaping set -e false -v {self.name}"
        self.owner.execute_command(command)

    def restore_portgroups_default(self) -> None:
        """Restore default policy of portgroups."""
        for portgroup in self.portgroups:
            self.set_portgroup_vlan(portgroup, 0)
            command = f"esxcli network vswitch standard portgroup policy failover set -u -p {portgroup}"
            self.owner.execute_command(command)
            if portgroup.startswith(f"{ESXI_PORTGROUP_VMKNIC}vmnic"):
                vmnic = portgroup[len(ESXI_PORTGROUP_VMKNIC) :]
                self.set_portgroup_uplinks(portgroup, [vmnic])
            command = f"esxcli network vswitch standard portgroup policy security set -u -p {portgroup}"
            self.owner.execute_command(command)
            command = f"esxcli network vswitch standard portgroup policy shaping set -u -p {portgroup}"
            self.owner.execute_command(command)

    def set_forged_transmit(self, name: str, enable: bool = True) -> None:
        """
        Set forged transmit policy on portgroup.

        :param name: Name of portgroup
        :param enable: Status of forged transmit parameter, Allow = True / Disallow = False
        """
        command = f"esxcli network vswitch standard portgroup policy security set -p {name} -f {str(enable)}"
        self.owner.execute_command(command)

    def change_ens_fpo_support(self, enable: bool, vds: str | None = None) -> None:
        """
        Enable or disable FPO support.

        When vds is provided change support on given vds, otherwise change settings globally.

        :param enable: True - enable FPO support, False - disable FPO support
        :param vds: portset name, retrieved with discover method
        """
        states = {True: "enable", False: "disable"}
        cmd = f"nsxdp-cli ens fpo set --{states[enable]}"
        if vds:
            cmd += f" -dvs {vds}"

        self.owner.execute_command(cmd)

    def set_mac_change_policy(self, portgroup_name: str, enabled: bool = False) -> None:
        """
        Set MAC change policy on portgroup.

        :param portgroup_name: Name of portgroup
        :param enabled: Status of mac change, Allow= True / Disallow = False
        """
        command = f"esxcli network vswitch standard portgroup policy security set -p {portgroup_name} -m {enabled}"
        self.owner.execute_command(command, custom_exception=VswitchError)
