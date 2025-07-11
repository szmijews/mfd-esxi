# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Support for vmkernel adapters."""

import re
from typing import List, Union, TYPE_CHECKING
from ipaddress import IPv4Interface, IPv6Interface, ip_interface

from mfd_typing import MACAddress
from .exceptions import ESXiNotFound, ESXiNotSupported

if TYPE_CHECKING:
    from mfd_esxi.host import ESXiHypervisor


class Vmknic:
    """Class for vmkernel adapters."""

    def __init__(self, owner: "ESXiHypervisor", name: str):
        """
        Initialize vmknic adapter.

        :param owner: ESXi host
        :param name: name of vmknic adapter
        """
        self.owner = owner
        self.name = name
        self.portgroup: Union[str, None] = None
        self.ips: List[Union[IPv4Interface, IPv6Interface]] = []
        self.mac: Union[MACAddress, None] = None
        self.mtu: int = 1500

    def initialize(self, output: str) -> None:
        """
        Initialize vmknic adapter base on esxcfg-vmknic -l output.

        :param output: output of esxcfg-vmknic -l
        """
        found = False
        self.ips = []
        for line in output.splitlines():
            if line.startswith(f"{self.name} "):
                pattern = (
                    rf"^{self.name}\s+(?P<portgroup>.+)\s+IPv(?P<ip_ver>\d)\s+(?P<ip>\S+)\s+(?P<netmask>\S+)\s+"
                    r"(?P<gateway>\S+)?\s+(?P<mac>\S{2}:\S{2}:\S{2}:\S{2}:\S{2}:\S{2})\s+(?P<mtu>\d+)"
                )
                match = re.search(pattern, line)
                if match:
                    self.portgroup = match.group("portgroup").strip()
                    if match.group("ip") != "N/A" and match.group("netmask") != "N/A":
                        self.ips.append(ip_interface(f"{match.group('ip')}/{match.group('netmask')}"))
                    self.mac = MACAddress(match.group("mac"))
                    self.mtu = int(match.group("mtu"))
                    found = True
        if not found:
            raise ESXiNotFound(f"Unable to find vmknic with name {self.name}")

    def refresh(self) -> None:
        """Refresh setting of vmknic adapter."""
        output = self.owner.execute_command("esxcfg-vmknic -l").stdout
        self.initialize(output)

    @staticmethod
    def discover(owner: "ESXiHypervisor") -> List["Vmknic"]:
        """
        Discover all vmknic adapters on host.

        :param owner: ESXi host
        :return:  list of vmknic adapters
        """
        output = owner.execute_command("esxcfg-vmknic -l").stdout
        vmknic = []
        for line in output.splitlines():
            if line.startswith("Interface") or any(vmk_type in line for vmk_type in ["vxlan", "hyperbus"]):
                continue
            fields = line.split()
            if fields:
                vmknic.append(fields[0])

        vmknic = list(set(vmknic))  # remove duplicates
        objects = []
        for vmk in vmknic:
            adapter = Vmknic(owner, vmk)
            adapter.initialize(output)
            objects.append(adapter)

        return objects

    @staticmethod
    def add_vmknic(
        owner: "ESXiHypervisor",
        portgroup: str,
        mtu: int = None,
        mac: "MACAddress" = None,
    ) -> "Vmknic":
        """
        Create vmknic adapter.

        :param owner: ESXi host
        :param portgroup: portgroup
        :param mtu: MTU value
        :param mac: MAC address of adapter (optional)
        :return:
        """
        command = f"esxcli network ip interface add -p {portgroup}"
        if mtu is not None:
            command += f" -m {mtu}"
        if mac is not None:
            command += f" -M {mac}"
        owner.execute_command(command)
        output = owner.execute_command("esxcfg-vmknic -l").stdout
        for line in output.splitlines():
            if f" {portgroup} " in line:
                name = line.split()[0]
                vmknic = Vmknic(owner, name)
                vmknic.initialize(output)
                return vmknic
        raise ESXiNotFound("Could not find created vmknic")

    def del_vmknic(self) -> None:
        """Delete vmknic adapter."""
        command = f"esxcli network ip interface remove -p {self.portgroup}"
        self.owner.execute_command(command)

    def set_mtu(self, mtu: int) -> None:
        """
        Set MTU for vmknic adapter.

        :param mtu: MTU value
        """
        command = f"esxcli network ip interface set -i {self.name} -m {mtu}"
        self.owner.execute_command(command)
        self.mtu = mtu

    def set_vlan(self, vlan: int) -> None:
        """
        Set VLAN of vmknic adapter.

        :param vlan: VLAN number (0 - no vlan, 4095 - all vlans)
        """
        command = f"esxcli network vswitch standard portgroup set -p {self.portgroup} -v {vlan}"
        self.owner.execute_command(command)

    def add_ip(self, ip: Union["IPv4Interface", "IPv6Interface", str]) -> None:
        """
        Set IPv4 or add IPv6.

        :param ip: IPv4 or IPv6
        """
        if isinstance(ip, str):
            ip = ip_interface(ip)
        if ip.version == 4:
            command = f"esxcli network ip interface ipv4 set -i {self.name} -I {ip.ip} -N {ip.netmask} -t static"
        elif ip.version == 6:
            command = f"esxcli network ip interface ipv6 address add -i {self.name} -I {ip}"
        else:
            raise ESXiNotSupported(f"Unknown ip version {ip.version}")
        self.owner.execute_command(command)
        if ip.version == 4:
            for i in self.ips:
                if i.version == 4:
                    self.ips.remove(i)
                    break
        self.ips.append(ip)

    def del_ip(self, ip: Union["IPv4Interface", "IPv6Interface", str]) -> None:
        """
        Delete IPv6.

        :param ip: IPv6
        """
        if isinstance(ip, str):
            ip = ip_interface(ip)
        if ip.version == 4:
            raise ESXiNotSupported("Unable to remove IPv4 address")
        elif ip.version == 6:
            command = f"esxcli network ip interface ipv6 address remove -i {self.name} -I {ip}"
        else:
            raise ESXiNotSupported(f"Unknown ip version {ip.version}")
        self.owner.execute_command(command)
        self.ips.remove(ip)
