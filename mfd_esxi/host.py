# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""ESXi host support."""

import logging
import re
from collections import namedtuple
from ipaddress import (
    IPv4Interface,
    IPv6Interface,
    IPv4Address,
    IPv6Address,
    IPv4Network,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import TYPE_CHECKING, List, Union, Optional

from mfd_common_libs import log_levels, add_logging_level
from mfd_typing.utils import strtobool
from mfd_typing import PCIAddress

from .esxi_version import ESXiVersion
from .exceptions import ESXiNotFound, ESXiRuntimeError
from .host_api import ESXiHostAPI
from .vm_mgr import ESXiVMMgr
from .vmknic import Vmknic
from .vswitch import ESXivSwitch

if TYPE_CHECKING:
    from mfd_connect import Connection
    from mfd_connect.base import ConnectionCompletedProcess
    from mfd_typing import MACAddress
    from mfd_network_adapter.network_interface.esxi import ESXiNetworkInterface

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)

IntnetCliVersion = namedtuple(typename="IntnetCliVersion", field_names=("intnet_ver", "ddk_ver"))


class ESXiHypervisor:
    """Class for most of ESXi functionality."""

    def __init__(self, connection: "Connection"):
        """
        Initialize host object.

        :param connection: Connection object
        """
        self.connection = connection
        self.hv: ESXiVMMgr = ESXiVMMgr(self)

        self.esxi_version = None
        self.vswitch: List[ESXivSwitch] = []
        self.vmknic: List[Vmknic] = []
        self.mng_vmknic: Union[Vmknic, None] = None
        self.mng_ip: Union[IPv4Interface, IPv6Interface, None] = None
        self._ip: Optional[Union[IPv4Address, IPv6Address]] = None
        self.api: Optional[ESXiHostAPI] = None

    def execute_command(self, command: str, **kwargs) -> "ConnectionCompletedProcess":
        """
        Shortcut for execute command.

        :param command: string with command
        :param kwargs: parameters
        :return: result of command
        """
        return self.connection.execute_command(command=command, **kwargs)

    def initialize(self, ip: str, login: str, password: str) -> None:
        """Read host configuration."""
        self._ip: Union[IPv4Address, IPv6Address] = ip_address(ip)
        self.api: ESXiHostAPI = ESXiHostAPI(ip=ip, login=login, password=password)

        self.initialize_version()
        self.initialize_vswitch()
        self.initialize_vmknic()
        self.initialize_mng()
        self.initialize_hv()

    def initialize_version(self) -> None:
        """Read version."""
        self.esxi_version = ESXiVersion.discover(self)

    def initialize_vswitch(self) -> None:
        """Read vSwitches."""
        self.vswitch = ESXivSwitch.discover(self)

    def initialize_vmknic(self) -> None:
        """Read vmknic adapters."""
        self.vmknic = Vmknic.discover(self)

    def initialize_mng(self) -> None:
        """Find management adapter and IP."""
        self.mng_vmknic = self.find_vmknic(ip=self._ip)
        for ip in self.mng_vmknic.ips:
            if self._ip in ip.network:
                self.mng_ip = ip
                return
        raise ESXiNotFound("Could not find management IP")

    def initialize_hv(self) -> None:
        """Read VMs on host."""
        self.hv.initialize()

    def add_vswitch(self, name: str) -> "ESXivSwitch":
        """
        Add vSwitch on host.

        :param name: name of vSwitch
        :return: vSwitch object
        """
        vswitch = ESXivSwitch.add_vswitch(self, name)
        self.vswitch.append(vswitch)
        return vswitch

    def del_vswitch(self, name: str) -> None:
        """
        Delete vSwitch on host.

        :param name: name of vSwitch
        """
        for i, vswitch in enumerate(self.vswitch):
            if vswitch.name == name:
                vswitch.del_vswitch()
                self.vswitch.pop(i)
                return
        raise ESXiNotFound(f"Could not find vSwitch {name}")

    def set_vswitch(
        self,
        name: str,
        uplinks: List[str],
        portgroups: List[str] = (),
        mtu: int = 1500,
        vmknic: bool = True,
    ) -> "ESXivSwitch":
        """
        Set existing or create new vSwitch.

        :param name: name of vSwitch
        :param uplinks: list of uplink names
        :param portgroups: list of portgroup names
        :param mtu: MTU value (default 1500)
        :param vmknic: create portgroups for vmknic adapters and add them
        :return:
        """
        for vswitch in self.vswitch:
            if vswitch.name == name:
                vswitch.reconfigure(uplinks=uplinks, portgroups=portgroups, mtu=mtu, vmknic=vmknic)
                return vswitch
        vswitch = self.add_vswitch(name)
        vswitch.configure(uplinks=uplinks, portgroups=portgroups, mtu=mtu, vmknic=vmknic)
        return vswitch

    def find_vswitch(self, name: str = None, uplink: str = None, portgroup: str = None) -> "ESXivSwitch":
        """
        Find vSwitch based on parameter.

        :param name: name of vSwitch
        :param uplink: uplink connected to vSwitch
        :param portgroup: portgroup connected to vSwitch
        :return: vSwitch object
        """
        for vswitch in self.vswitch:
            if name == vswitch.name or uplink in vswitch.uplinks or portgroup in vswitch.portgroups:
                return vswitch
        raise ESXiNotFound("Could not find vSwitch")

    def add_vmknic(self, portgroup: str, mtu: int = None, mac: "MACAddress" = None) -> "Vmknic":
        """
        Add vmknic adapter.

        :param portgroup: portgroup name
        :param mtu: MTU value
        :param mac: MAC value
        :return: Vmknic adapter
        """
        vmknic = Vmknic.add_vmknic(self, portgroup=portgroup, mtu=mtu, mac=mac)
        self.vmknic.append(vmknic)
        return vmknic

    def del_vmknic(self, name: str = None, portgroup: str = None) -> None:
        """
        Delete vmknic adapter.

        :param name: name of adapter
        :param portgroup: portgroup of adapter
        """
        for i, vmknic in enumerate(self.vmknic):
            if vmknic.name == name or vmknic.portgroup == portgroup:
                vmknic.del_vmknic()
                self.vmknic.pop(i)
                return
        raise ESXiNotFound("Could not find vmknic")

    def find_vmknic(
        self,
        name: str = None,
        portgroup: str = None,
        ip: Union[IPv4Address, IPv6Address, str] = None,
        net: Union[IPv4Network, IPv6Network, str] = None,
    ) -> "Vmknic":
        """
        Find vmknic adapter.

        :param name: name of adapter
        :param portgroup: portgroup of adapter
        :param ip: IP address of adapter
        :param net: IP from the same network as adapter
        :return: vmknic adapter
        """
        if isinstance(ip, str):
            ip = ip_address(ip)
        if isinstance(net, str):
            net = ip_network(net, strict=False)
        for vmknic in self.vmknic:
            if vmknic.name == name or vmknic.portgroup == portgroup:
                return vmknic
            for i in vmknic.ips:
                if ip == i.ip:
                    return vmknic
            if net is not None:
                for ip in vmknic.ips:
                    if ip in net:
                        return vmknic
        raise ESXiNotFound("Could not find vmknic")

    def get_meminfo(self) -> dict[str, int]:
        """
        Get information regarding the memory of the system.

        :return: dictionary represents /proc/meminfo data
        """
        output = self.execute_command("vsish -e get /memory/memInfo", expected_return_codes={0}).stdout

        regex = re.compile(
            r"(System heap free \(pages\):(?P<heap_free>\d+)\n\s*)?"
            r"System memory usage \(pages\):(?P<mem_usage>\d+)",
            re.MULTILINE,
        )
        match = regex.search(output)
        if not match:
            raise RuntimeError("Cannot get memory info for the host")

        if match.group("heap_free"):
            ret = {
                "heap_free": int(match.group("heap_free")),
                "mem_usage": int(match.group("mem_usage")),
            }
        else:
            ret = {"mem_usage": int(match.group("mem_usage"))}
        return ret

    def find_link_partner(self, vmnic: str) -> str:
        """Get link partner adapter (client) for given adapter on the same host.

        :param vmnic: vmnic name
        :return: client vmnic name
        :raises: ESXiRuntimeError
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Finding link partner for adapter {vmnic}",
        )
        output = self.execute_command("esxcfg-nics -l").stdout
        output = output.splitlines()
        output.pop(0)  # remove header

        for base in output:
            base = base.split()
            if base[0] == vmnic:
                break
        else:
            raise ESXiRuntimeError(f"Could not find adapter {vmnic}")

        # find adapter by closest PCI address
        func = int(base[1][-1])
        func = func ^ 1  # change last bit
        pci = f"{base[1][:-1]}{func}"

        for line in output:
            line = line.split()
            if line[1] == pci and line[3] == "Up":
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Link partner for adapter {vmnic} is {line[0]}",
                )
                return line[0]

        # find adapter from the same driver
        for line in output:
            line = line.split()
            if line[0] != base[0] and line[2] == base[2] and line[3] == "Up":
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Link partner for adapter {vmnic} is {line[0]}",
                )
                return line[0]

        raise ESXiRuntimeError(f"Could not find link partner to adapter {vmnic}")

    def find_pf0(self, nics: List[str]) -> List[str]:
        """Find base ports (PF0) of selected ports.

        :param nics: list of vmnic names
        :return: list of vmnic names
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Finding PF0 of adapters {nics}")
        output = self.execute_command("esxcfg-nics -l").stdout
        output = output.splitlines()
        output.pop(0)  # remove header

        # Create set of PCI addresses
        pci_set = set()
        for line in output:
            line = line.split()
            if line[0] in nics:
                pci_set.add(line[1].split(".")[0])

        pf0 = []
        for line in output:
            line = line.split()
            p = line[1].split(".")
            if p[1] == "0" and p[0] in pci_set:
                pf0.append(line[0])

        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Found PF0 ports {pf0}")
        return pf0

    def get_intnetcli_version(self) -> IntnetCliVersion:
        """Get version of intnetcli and associated DDK.

        :return: intnetcli version, DDK version
        :raises: RuntimeError
        """
        command = "esxcli software vib list | grep -i int-esx-intnetcli"
        res = self.connection.execute_command(command, shell=True, expected_return_codes=None)
        if res.return_code != 0:
            versions = IntnetCliVersion(intnet_ver=None, ddk_ver=None)
            return versions

        match = re.search(r"(?P<DDK>[0-9]+)\.(?P<intnet>[0-9\.]+)", res.stdout)
        if match:
            versions = IntnetCliVersion(intnet_ver=match.group("intnet"), ddk_ver=match.group("DDK"))
            return versions

        raise ESXiRuntimeError("Unknown version of intnetcli installed.")

    def get_pci_passthrough_capable_devices(self) -> dict[PCIAddress, bool]:
        """Get Dict with all devices that support PCI passthrough and current PCI passthrough status.

        return: correct passthrough status starting from ESXi 7.0
                as older versions do not present this information,
                status for such devices will be presented as false.
        """
        result = {}
        logger.log(level=log_levels.MODULE_DEBUG, msg="Get PCI passthrough capable devices")
        if self.connection.execute_command("uname -r").stdout.strip()[0] < "7":
            regex = r"address: (?P<pci>\d{4}:\w{2}:\w{2}\.\w+)(?:\s.*)*?\s{4}passthru capable: true"
            output = self.connection.execute_command(
                "esxcli hardware pci list | grep -i vmnic -B 6 -A 29", shell=True
            ).stdout.lower()
            match = re.findall(regex, output, re.MULTILINE)
            if match:
                result = {PCIAddress(data=pci): False for pci in match}
        else:
            regex = r"(?P<pci>\d{4}:\w{2}:\w{2}\.\w+).*(?P<status>false|true)"
            output = self.connection.execute_command("esxcli hardware pci pcipassthru list").stdout

            match = re.findall(regex, output)
            if match:
                result = {PCIAddress(data=pci): strtobool(status) for pci, status in match}

        return result

    def get_pci_passthrough_nics(self) -> list[PCIAddress]:
        """Get PCI addresses for PCI passthrough enabled NICs.

        Method does not return Virtual functions which are also PCI passthroughs.
        :return: list of PCI strings
        :raises ESXiRuntimeError when cannot get PCI addresses for PCI passthrough enabled NIC
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg="Get NICs with enabled PCI passthrough")
        output = self.connection.execute_command("lspci -p").stdout
        match = re.findall(r"(?P<pci>\d{4}:\w{2}:\w{2}\.\w+).*?A P .*", output)
        if not match:
            raise ESXiRuntimeError("Cannot get PCI addresses for PCI passthrough enabled NICs.")
        return [PCIAddress(data=pci) for pci in match]

    def get_vds_id(self) -> str:
        """Get Distributed vSwitch id. e.g. '64 76 73 5f 74 65 73 74-00 00 00 00 00 00 00 00'.

        :return: VDS id
        :raises ESXiRuntimeError: if it cannot get VDS ID
        """
        output = self.connection.execute_command("esxcli network vswitch dvs vmware list").stdout
        try:
            if output:
                dvs_id = output.splitlines()[2].lstrip("VDS ID: ")
                return dvs_id
        except IndexError:
            raise ESXiRuntimeError("Cannot get VDS ID.")

    def get_vm_name_for_vf_id(self, vf_id: int | str, interface: "ESXiNetworkInterface") -> str:
        """
        Find name of VM associated with a given VF.

        :param vf_id: VF ID
        :param interface: ESXi adapter
        :return: name of VM associated with VF
        """
        # get list of used vfs for adapter
        vfs = interface.virtualization.get_connected_vfs_info()

        # get list of used VMs
        cmd = "esxcli vm process list"
        output = self.connection.execute_command(cmd).stdout

        my_regex = re.compile(
            r".*World ID:\s(?P<world_id>\d+)\n"
            r".*Process ID:\s.*\n"
            r".*VMX Cartel ID:\s(?P<vmx_cartel_id>\d+)\n"
            r".*UUID:\s.*\n"
            r".*Display Name:\s(?P<name>.*)\n"
            r".*Config File:\s.*",
            re.MULTILINE,
        )

        vms = [
            {
                "world_id": match.group("world_id"),
                "name": match.group("name"),
                "vmx_cartel_id": match.group("vmx_cartel_id"),
            }
            for match in my_regex.finditer(output)
        ]

        # find VM name corresponding to given VF
        world_id = [vf.owner_world_id for vf in vfs if vf.vf_id == str(vf_id)]

        if not world_id:
            raise Exception(f"VF {vf_id} is not connected to any VM")

        os_version = float(self.connection.get_system_info().kernel_version[:3])

        return [
            vm["name"]
            for vm in vms
            if ((os_version < 7.0 or os_version >= 9.0) and vm["vmx_cartel_id"] == world_id[0])
            or ((7.0 <= os_version < 9.0) and vm["world_id"] == world_id[0])
        ][0]
