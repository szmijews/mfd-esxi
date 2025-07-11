# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from ipaddress import ip_address
from textwrap import dedent

import pytest
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess
from mfd_network_adapter.network_interface import NetworkInterface
from mfd_typing import OSName
from mfd_typing.network_interface import InterfaceInfo
from mfd_typing.pci_address import PCIAddress
from pyVmomi import vim

from mfd_esxi.host import ESXiHypervisor
from mfd_esxi.host_api import ESXiHostAPI
from mfd_esxi.vcenter.cluster import Cluster
from mfd_esxi.vcenter.datacenter import Datacenter
from mfd_esxi.vcenter.datastore import Datastore
from mfd_esxi.vcenter.distributed_switch.dswitch import DSwitch
from mfd_esxi.vcenter.distributed_switch.portgroup import DSPortgroup
from mfd_esxi.vcenter.distributed_switch.uplink import DSUplink
from mfd_esxi.vcenter.host import Host
from mfd_esxi.vcenter.vcenter import VCenter
from mfd_esxi.vcenter.virtual_adapter import VirtualAdapter
from mfd_esxi.vcenter.virtual_machine import VirtualMachine
from mfd_esxi.vcenter.virtual_switch.portgroup import VSPortgroup
from mfd_esxi.vcenter.virtual_switch.vswitch import VSwitch


@pytest.fixture()
def host(mocker):
    connection = mocker.create_autospec(RPyCConnection)
    connection.get_os_name.return_value = OSName.ESXI
    host = ESXiHypervisor(connection=connection)
    host._ip = ip_address("172.31.0.82")
    host.connection.execute_command.return_value = ConnectionCompletedProcess(return_code=0, args="command", stdout="")
    return host


@pytest.fixture()
def host_esxcfg_vswitch_1(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vswitch_1
    )
    return host


@pytest.fixture()
def host_esxcfg_vswitch_2(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vswitch_2
    )
    return host


@pytest.fixture()
def host_esxcfg_vswitch_3(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vswitch_3
    )
    return host


@pytest.fixture()
def host_esxcfg_vmknic_1(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vmknic_1
    )
    return host


@pytest.fixture()
def host_esxcfg_vmknic_2(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vmknic_2
    )
    return host


@pytest.fixture()
def host_esxcfg_vmknic_3(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_vmknic_3
    )
    return host


@pytest.fixture()
def host_esxcfg_nics_1(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_nics_1
    )
    return host


@pytest.fixture()
def host_esxcfg_nics_2(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=esxcfg_nics_2
    )
    return host


@pytest.fixture()
def host_gold_vmx(host):
    host.connection.execute_command.side_effect = [
        ConnectionCompletedProcess(return_code=0, args="command", stdout=base_vmx),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=primary_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=parent_vmdk),
    ]
    return host


@pytest.fixture()
def host_gold_vmx_ptp_old_esxi(host):
    host.connection.execute_command.side_effect = [
        ConnectionCompletedProcess(return_code=0, args="command", stdout=base_vmx),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=primary_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=parent_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout="    0   false  00000:050:01.0   -"),
        ConnectionCompletedProcess(
            return_code=0,
            args="command",
            stdout="0000:32:01.0               8086:1889 8086:0000 255/   /     @ P pciPassthru",
        ),
    ]
    return host


@pytest.fixture()
def host_gold_vmx_ptp_new_esxi(host):
    host.connection.execute_command.side_effect = [
        ConnectionCompletedProcess(return_code=0, args="command", stdout=base_vmx),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=primary_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=parent_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout="    6   false  0000:32:01.0      -"),
        ConnectionCompletedProcess(
            return_code=0,
            args="command",
            stdout="0000:32:01.0               8086:1889 8086:0000 255/   /     @ P pciPassthru",
        ),
    ]
    return host


@pytest.fixture()
def host_gold_vmx_ptp_new_esxi_hex(host):
    host.connection.execute_command.side_effect = [
        ConnectionCompletedProcess(return_code=0, args="command", stdout=base_vmx),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=primary_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout=parent_vmdk),
        ConnectionCompletedProcess(return_code=0, args="command", stdout="    6   false  0000:b1:01.0      -"),
        ConnectionCompletedProcess(
            return_code=0,
            args="command",
            stdout="0000:b1:01.0               8086:1889 8086:0000 255/   /     @ P pciPassthru",
        ),
    ]
    return host


@pytest.fixture()
def host_getallvms(host):
    host.connection.execute_command.return_value = ConnectionCompletedProcess(
        return_code=0, args="command", stdout=getallvms
    )
    return host


@pytest.fixture()
def host_api(mocker, monkeypatch):
    host_api = ESXiHostAPI("172.31.0.56", "root", "secret")
    host_api_content = mocker.create_autospec(vim.ServiceInstanceContent)
    host_api._ESXiHostAPI__content = host_api_content
    host_api._ESXiHostAPI__service = True
    return host_api


@pytest.fixture()
def host_api_with_cert(mocker, host_api):
    host_api._ESXiHostAPI__content.rootFolder = object()
    host_api._ESXiHostAPI__content.sessionManager = mocker.create_autospec(vim.SessionManager)
    host_api._ESXiHostAPI__content.sessionManager.currentSession = True
    host_api._service = True
    fake_host_config = mocker.create_autospec(vim.host.ConfigInfo)
    fake_host_config.certificate = hostapi_cert_bytes

    fake_host = mocker.create_autospec(vim.HostSystem)
    fake_host.config = fake_host_config

    fake_view = mocker.create_autospec(vim.view.ContainerView)
    fake_view.view = [fake_host]

    host_api._ESXiHostAPI__content.viewManager = mocker.create_autospec(vim.view.ViewManager)
    host_api._ESXiHostAPI__content.viewManager.CreateContainerView = lambda x, y, z: fake_view

    return host_api


@pytest.fixture()
def vcenter():
    vcenter = VCenter("172.31.12.144", "user", "secret")
    return vcenter


@pytest.fixture()
def datacenter(vcenter):
    datacenter = Datacenter("PY-Datacenter", vcenter)
    return datacenter


@pytest.fixture()
def cluster(datacenter):
    cluster = Cluster("PY-Cluster", datacenter)
    return cluster


@pytest.fixture()
def standalone_host(datacenter):
    host = Host("PY-StandaloneHost", datacenter)
    return host


@pytest.fixture()
def cluster_host(datacenter, cluster):
    host = Host("PY-ClusterHost", datacenter, cluster)
    return host


@pytest.fixture()
def datastore(standalone_host):
    datastore = Datastore("PY-Datastore", standalone_host)
    return datastore


@pytest.fixture()
def virtual_adapter(standalone_host):
    virtual_adapter = VirtualAdapter("PY-VirtualAdapter", standalone_host)
    return virtual_adapter


@pytest.fixture()
def virtual_machine(standalone_host):
    virtual_machine = VirtualMachine("PY-VirtualMachine", standalone_host)
    return virtual_machine


@pytest.fixture()
def dswitch(datacenter):
    dswitch = DSwitch("PY-DSwitch", datacenter)
    return dswitch


@pytest.fixture()
def dsportgroup(dswitch):
    dsportgroup = DSPortgroup("PY-DSPortgroup", dswitch)
    return dsportgroup


@pytest.fixture()
def dsuplink(dswitch):
    dsuplink = DSUplink("PY-DSUplink", 12, dswitch)
    return dsuplink


@pytest.fixture()
def vswitch(standalone_host):
    vswitch = VSwitch("PY-VSwitch", standalone_host)
    return vswitch


@pytest.fixture()
def vsportgroup(vswitch):
    vsportgroup = VSPortgroup("PY-VSPortgroup", vswitch)
    return vsportgroup


@pytest.fixture()
def vcenter_named_entities():
    class DummyNamedThing:
        def __init__(self, name):
            self._name = name

        def __repr__(self):
            return self._name

        @property
        def name(self):
            return self._name

    names = ("Named-1", "Named-2", "Named-3")
    return [DummyNamedThing(n) for n in names]


@pytest.fixture()
def host_api(mocker, monkeypatch):
    host_api = ESXiHostAPI("172.31.0.56", "root", "secret")
    host_api_content = mocker.create_autospec(vim.ServiceInstanceContent)
    host_api._ESXiHostAPI__content = host_api_content
    host_api._ESXiHostAPI__service = True
    return host_api


@pytest.fixture()
def host_api_with_cert(mocker, host_api):
    host_api._ESXiHostAPI__content.rootFolder = object()
    host_api._ESXiHostAPI__content.sessionManager = mocker.create_autospec(vim.SessionManager)
    host_api._ESXiHostAPI__content.sessionManager.currentSession = True
    host_api._service = True
    fake_host_config = mocker.create_autospec(vim.host.ConfigInfo)
    fake_host_config.certificate = hostapi_cert_bytes

    fake_host = mocker.create_autospec(vim.HostSystem)
    fake_host.config = fake_host_config

    fake_view = mocker.create_autospec(vim.view.ContainerView)
    fake_view.view = [fake_host]

    host_api._ESXiHostAPI__content.viewManager = mocker.create_autospec(vim.view.ViewManager)
    host_api._ESXiHostAPI__content.viewManager.CreateContainerView = lambda x, y, z: fake_view

    return host_api


@pytest.fixture()
def host_api_with_vf_info_and_interfaces(mocker, host_api):
    pci_addresses = [PCIAddress(0, 0, 0, 0), PCIAddress(0, 0, 0, 1)]
    names = ["vmnic4", "vmnic5"]
    _connection = mocker.create_autospec(RPyCConnection)
    _connection.get_os_name.return_value = OSName.ESXI

    interfaces = []
    for pci_address, name in zip(pci_addresses, names):
        interfaces.append(
            NetworkInterface(
                connection=_connection,
                interface_info=InterfaceInfo(pci_address=pci_address, name=name),
            )
        )

    host_api._ESXiHostAPI__content.rootFolder = object()
    host_api._ESXiHostAPI__content.sessionManager = mocker.create_autospec(vim.SessionManager)
    host_api._ESXiHostAPI__content.sessionManager.currentSession = True
    host_api._service = True

    fake_pci_passthru_info_list = []
    vfs_info = [
        {
            "maxVirtualFunctionSupported": 128,
            "numVirtualFunction": 8,
            "numVirtualFunctionRequested": 8,
            "sriovEnabled": True,
        },
        {
            "maxVirtualFunctionSupported": 128,
            "numVirtualFunction": 0,
            "numVirtualFunctionRequested": 0,
            "sriovEnabled": False,
        },
    ]

    for pci_address, vf_info in zip(pci_addresses, vfs_info):
        pci_passthru_info = mocker.create_autospec(vim.host.SriovInfo)
        pci_passthru_info.id = pci_address.lspci
        pci_passthru_info.maxVirtualFunctionSupported = vf_info["maxVirtualFunctionSupported"]
        pci_passthru_info.numVirtualFunction = vf_info["numVirtualFunction"]
        pci_passthru_info.numVirtualFunctionRequested = vf_info["numVirtualFunctionRequested"]
        pci_passthru_info.sriovEnabled = vf_info["sriovEnabled"]

        fake_pci_passthru_info_list.append(pci_passthru_info)

    other_pci_passthru_info = mocker.create_autospec(vim.host.PciPassthruInfo)
    other_pci_address = PCIAddress(1, 1, 1, 2)
    other_pci_passthru_info.id = other_pci_address.lspci
    fake_pci_passthru_info_list.append(other_pci_passthru_info)

    fake_pci_passthru_system = mocker.create_autospec(vim.host.PciPassthruSystem)
    fake_pci_passthru_system.pciPassthruInfo = fake_pci_passthru_info_list

    fake_config_manager = mocker.create_autospec(vim.host.ConfigManager)
    fake_config_manager.pciPassthruSystem = fake_pci_passthru_system

    fake_host = mocker.create_autospec(vim.HostSystem)
    fake_host.configManager = fake_config_manager

    fake_view = mocker.create_autospec(vim.view.ContainerView)
    fake_view.view = [fake_host]

    host_api._ESXiHostAPI__content.viewManager = mocker.create_autospec(vim.view.ViewManager)
    host_api._ESXiHostAPI__content.viewManager.CreateContainerView = lambda x, y, z: fake_view

    return host_api, interfaces


esxcfg_vswitch_1 = dedent(
    """\
    Switch Name      Num Ports   Used Ports  Configured Ports  MTU     Uplinks
    vSwitch0         6690        5           128               1500    vmnic0

      PortGroup Name                            VLAN ID  Used Ports  Uplinks
      ATmng                                   0        0           vmnic0
      VM Network                                0        1           vmnic0
      Management Network                        0        1           vmnic0

    DVS Name         Num Ports   Used Ports  Configured Ports  MTU     Uplinks
    DSwitch_063LongName 6690        4           512               9000    vmnic3

      DVPort ID                               In Use      Client
      0                                       1           vmnic3
      9                                       1           vmk1
"""
)

esxcfg_vswitch_2 = dedent(
    """\
    Switch Name      Num Ports   Used Ports  Configured Ports  MTU     Uplinks
    ATvSwitchLongName 8570        8           128               1500    vmnic10

      PortGroup Name                            VLAN ID  Used Ports  Uplinks
      ATNetwork                               0        4           vmnic10
      ATvmnic10                               0        1           vmnic10

    Switch Name      Num Ports   Used Ports  Configured Ports  MTU     Uplinks
    vSwitch0         8570        6           128               1500    vmnic4

      PortGroup Name                            VLAN ID  Used Ports  Uplinks
      ATmng                                   0        1           vmnic4
      VM Network                                0        1           vmnic4
      Management Network                        0        1           vmnic4
"""
)

esxcfg_vswitch_3 = dedent(
    """\
    DVS Name         Num Ports   Used Ports  Configured Ports  MTU     Uplinks
    dvSwitch         256         3           256               1500    vmnic9,vmnic8

      DVPort ID           In Use      Client
      0                   1           vmnic8
      1                   1           vmnic9
"""
)

esxcfg_vmknic_1 = dedent(
    """\
    Interface  Port Group/DVPort/Opaque Network        IP Family IP Address                              Netmask         Broadcast       MAC Address       MTU     TSO MSS   Enabled Type                NetStack
    vmk0       Management Network                      IPv4      172.31.0.82                             255.255.0.0     172.31.255.255  48:df:37:aa:bb:cc 1500    65535     true    DHCP                defaultTcpipStack
    vmk0       Management Network                      IPv6      fe80::4adf:37ff:fe07:1f14               64                              48:df:37:aa:bb:cc 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk1       ATvmnic10                             IPv4      1.1.1.1                                 255.0.0.0       1.255.255.255   00:50:56:aa:bb:cc 1500    65535     true    STATIC              defaultTcpipStack
    vmk1       ATvmnic10                             IPv6      fe80::250:56ff:fe66:5642                64                              00:50:56:aa:bb:cc 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
"""
)

esxcfg_vmknic_2 = dedent(
    """\
    Interface  Port Group/DVPort/Opaque Network        IP Family IP Address                              Netmask         Broadcast       MAC Address       MTU     TSO MSS   Enabled Type                NetStack
    vmk0       Management Network                      IPv4      172.31.0.82                             255.255.0.0     172.31.255.255  48:df:37:aa:bb:cc 1500    65535     true    DHCP                defaultTcpipStack
    vmk0       Management Network                      IPv6      fe80::4adf:37ff:fe07:1f14               64                              48:df:37:aa:bb:cc 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk1       ATvmnic10                             IPv4      1.1.1.1                                 255.0.0.0       1.255.255.255   00:50:56:aa:bb:cc 1500    65535     true    STATIC              defaultTcpipStack
    vmk1       ATvmnic10                             IPv6      fe80::250:56ff:fe66:5642                64                              00:50:56:aa:bb:cc 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk2       PGvmnic0                                IPv4      N/A                                     N/A             N/A             00:50:56:aa:bb:cc 9000    65535     true    NONE                defaultTcpipStack
    vmk2       PGvmnic0                                IPv6      fe80::250:56ff:fe63:a0ef                64                              00:50:56:aa:bb:cc 9000    65535     true    STATIC, PREFERRED   defaultTcpipStack
"""
)

esxcfg_vmknic_3 = dedent(
    """\
    Interface  Port Group/DVPort/Opaque Network        IP Family IP Address                              Netmask         Broadcast       MAC Address       MTU     TSO MSS   Enabled Type                NetStack     
    vmk0       Management Network                      IPv4      172.31.0.103                            255.255.0.0     172.31.255.255  b0:7b:25:aa:bb:cc 1500    65535     true    DHCP                defaultTcpipStack
    vmk0       Management Network                      IPv6      fe80::b27b:25ff:fede:7484               64                              b0:7b:25:aa:bb:cc 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk1       16                                      IPv4      15.1.1.1                                255.0.0.0       15.255.255.255  00:50:aa:bb:cc:5e 1500    65535     true    STATIC              defaultTcpipStack
    vmk1       16                                      IPv6      fe80::250:56ff:fe6f:1b5e                64                              00:50:aa:bb:cc:5e 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk1       16                                      IPv6      3001:15::1:1:1                          64                              00:50:aa:bb:cc:5e 1500    65535     true    STATIC, PREFERRED   defaultTcpipStack
    vmk10      2764417a-a5e8-4ae5-b5f8-b5c163648066    IPv4      14.1.1.1                                255.0.0.0       14.255.255.255  00:50:aa:bb:cc:4c 1700    65535     true    STATIC              vxlan        
    vmk10      2764417a-a5e8-4ae5-b5f8-b5c163648066    IPv6      fe80::250:56ff:fe6b:7a4c                64                              00:50:aa:bb:cc:4c 1700    65535     true    STATIC, PREFERRED   vxlan        
    vmk10      2764417a-a5e8-4ae5-b5f8-b5c163648066    IPv6      3001:14::1:1:1                          64                              00:50:aa:bb:cc:4c 1700    65535     true    STATIC, PREFERRED   vxlan        
    vmk11      c1e2b8b8-8fed-4e7e-a87f-3d438d99ee0c    IPv4      11.1.1.1                                255.0.0.0       11.255.255.255  00:50:aa:bb:cc:a8 1700    65535     true    STATIC              vxlan        
    vmk11      c1e2b8b8-8fed-4e7e-a87f-3d438d99ee0c    IPv6      fe80::250:56ff:fe62:fda8                64                              00:50:aa:bb:cc:a8 1700    65535     true    STATIC, PREFERRED   vxlan        
    vmk11      c1e2b8b8-8fed-4e7e-a87f-3d438d99ee0c    IPv6      3001:11::1:1:1                          64                              00:50:aa:bb:cc:a8 1700    65535     true    STATIC, PREFERRED   vxlan        
    vmk12      90e27848-f8d1-4df0-ace1-23d78ce5d85d    IPv4      1.1.1.1                                 255.0.0.0       1.255.255.255   00:50:aa:bb:cc:bd 1700    65535     true    STATIC              vxlan        
    vmk12      90e27848-f8d1-4df0-ace1-23d78ce5d85d    IPv6      fe80::250:56ff:fe64:28bd                64                              00:50:aa:bb:cc:bd 1700    65535     true    STATIC, PREFERRED   vxlan        
    vmk12      90e27848-f8d1-4df0-ace1-23d78ce5d85d    IPv6      3001:1::1:1:1                           64                              00:50:aa:bb:cc:bd 1700    65535     true    STATIC, PREFERRED   vxlan             
    vmk50      b8200bd5-c046-40f8-8caa-86647c65dda6    IPv4      8.1.1.1                                 255.0.0.0       8.255.255.255   00:50:aa:bb:cc:30 1700    65535     true    STATIC              hyperbus     
"""
)

esxcfg_nics_1 = dedent(
    """\
    Name    PCI          Driver      Link Speed      Duplex MAC Address       MTU    Description
    vmnic0  0000:4b:00.0 icen        Up   25000Mbps  Full   68:05:ca:aa:bb:cc 1500   Intel(R) Ethernet Controller E810-C for SFP
    vmnic1  0000:4b:00.1 icen        Up   25000Mbps  Full   68:05:ca:aa:bb:cd 1500   Intel(R) Ethernet Controller E810-C for SFP
    vmnic10 0000:ca:00.0 i40en       Up   10000Mbps  Full   3c:fd:aa:bb:cc:e0 1500   Intel(R) Ethernet Controller X710 for 10GbE SFP+
    vmnic11 0000:ca:00.1 i40en       Up   10000Mbps  Full   3c:fd:aa:bb:cc:e1 1500   Intel(R) Ethernet Controller X710 for 10GbE SFP+
    vmnic12 0000:ca:00.2 i40en       Up   10000Mbps  Full   3c:fd:aa:bb:cc:e2 1500   Intel(R) Ethernet Controller X710 for 10GbE SFP+
    vmnic13 0000:ca:00.3 i40en       Up   10000Mbps  Full   3c:fd:aa:bb:cc:e3 1500   Intel(R) Ethernet Controller X710 for 10GbE SFP+
    vmnic14 0000:98:00.0 bnxtnet     Down 0Mbps      Half   84:16:aa:bb:cc:f0 1500   Broadcom BCM57416 NetXtreme-E 10GBASE-T RDMA Ethernet Controller
    vmnic15 0000:98:00.1 bnxtnet     Down 0Mbps      Half   84:16:aa:bb:cc:f1 1500   Broadcom BCM57416 NetXtreme-E 10GBASE-T RDMA Ethernet Controller
    vmnic2  0000:4b:00.2 icen        Up   25000Mbps  Full   68:05:aa:bb:cc:c2 1500   Intel(R) Ethernet Controller E810-C for SFP
    vmnic3  0000:4b:00.3 icen        Up   25000Mbps  Full   68:05:aa:bb:cc:c3 1500   Intel(R) Ethernet Controller E810-C for SFP
    vmnic4  0000:31:00.0 igbn        Up   1000Mbps   Full   48:df:37:aa:bb:cc 1500   Intel(R) I350 Gigabit Network Connection
    vmnic5  0000:31:00.1 igbn        Down 0Mbps      Half   48:df:37:aa:bb:cd 1500   Intel(R) I350 Gigabit Network Connection
    vmnic6  0000:31:00.2 igbn        Down 0Mbps      Half   48:df:37:aa:bb:ce 1500   Intel(R) I350 Gigabit Network Connection
    vmnic7  0000:31:00.3 igbn        Down 0Mbps      Half   48:df:37:aa:bb:cf 1500   Intel(R) I350 Gigabit Network Connection
    vmnic8  0000:b1:00.0 ixgben      Up   10000Mbps  Full   90:e2:aa:bb:cc:34 1500   Intel(R) 82599 10 Gigabit Dual Port Network Connection
    vmnic9  0000:b1:00.1 ixgben      Up   10000Mbps  Full   90:e2:aa:bb:cc:35 1500   Intel(R) 82599 10 Gigabit Dual Port Network Connection
"""
)

esxcfg_nics_2 = dedent(
    """\
    Name    PCI          Driver      Link Speed      Duplex MAC Address       MTU    Description
    vmnic0  0000:e1:00.0 ntg3        Up   1000Mbps   Full   70:b5:aa:bb:cc:ce 1500   Broadcom Corporation NetXtreme BCM5720 Gigabit Ethernet
    vmnic1  0000:e1:00.1 ntg3        Down 0Mbps      Half   70:b5:aa:bb:cc:cf 1500   Broadcom Corporation NetXtreme BCM5720 Gigabit Ethernet
    vmnic2  0000:24:00.0 icen        Down 100000Mbps Full   b4:96:aa:bb:cc:f8 1500   Intel(R) Ethernet Controller E810-C for QSFP
    vmnic3  0000:21:00.0 icen        Up   100000Mbps Full   b4:96:aa:bb:cc:fc 1500   Intel(R) Ethernet Controller E810-C for QSFP
"""
)

base_vmx = dedent(
    """\
    .encoding = "UTF-8"
    config.version = "8"
    cpuid.coresPerSocket = "4"
    displayName = "Base_R91"
    ethernet0.networkName = "ATmng"
    ethernet0.pciSlotNumber = "160"
    ethernet0.present = "TRUE"
    ethernet0.virtualDev = "vmxnet3"
    firmware = "efi"
    floppy0.present = "FALSE"
    guestOS = "other-64"
    hpet0.present = "TRUE"
    memSize = "2048"
    messageBus.tunnelEnabled = "FALSE"
    mks.enable3d = "TRUE"
    numvcpus = "4"
    pciBridge0.pciSlotNumber = "17"
    pciBridge0.present = "TRUE"
    pciBridge4.functions = "8"
    pciBridge4.pciSlotNumber = "21"
    pciBridge4.present = "TRUE"
    pciBridge4.virtualDev = "pcieRootPort"
    pciBridge5.functions = "8"
    pciBridge5.pciSlotNumber = "22"
    pciBridge5.present = "TRUE"
    pciBridge5.virtualDev = "pcieRootPort"
    pciBridge6.functions = "8"
    pciBridge6.pciSlotNumber = "23"
    pciBridge6.present = "TRUE"
    pciBridge6.virtualDev = "pcieRootPort"
    pciBridge7.functions = "8"
    pciBridge7.pciSlotNumber = "24"
    pciBridge7.present = "TRUE"
    pciBridge7.virtualDev = "pcieRootPort"
    replay.supported = "false"
    sata0.pciSlotNumber = "33"
    sata0.present = "TRUE"
    sched.cpu.affinity = "all"
    sched.cpu.latencySensitivity = "normal"
    sched.cpu.min = "0"
    sched.cpu.shares = "normal"
    sched.cpu.units = "mhz"
    sched.mem.min = "2048"
    sched.mem.minSize = "2048"
    sched.mem.pin = "TRUE"
    sched.mem.shares = "normal"
    sched.scsi0:0.shares = "normal"
    sched.scsi0:0.throughputCap = "off"
    scsi0.pciSlotNumber = "160"
    scsi0.present = "TRUE"
    scsi0.virtualDev = "lsisas1068"
    scsi0:0.deviceType = "scsi-hardDisk"
    scsi0:0.fileName = "Base_R91-000001.vmdk"
    scsi0:0.present = "TRUE"
    softPowerOff = "TRUE"
    svga.present = "TRUE"
    svga.vramSize = "8388608"
    toolScripts.afterPowerOn = "TRUE"
    toolScripts.afterResume = "TRUE"
    toolScripts.beforePowerOff = "TRUE"
    toolScripts.beforeSuspend = "TRUE"
    tools.guest.desktop.autolock = "FALSE"
    tools.syncTime = "FALSE"
    tools.upgrade.policy = "manual"
    virtualHW.productCompatibility = "hosted"
    virtualHW.version = "13"
    vmci.filter.enable = "true"
    vmci0.pciSlotNumber = "32"
    vmci0.present = "TRUE"
    vmotion.checkpointFBSize = "8388608"
"""
)

primary_vmdk = dedent(
    """\
    # Disk DescriptorFile
    version=1
    CID=3729b687
    parentCID=3729b687
    createType="seSparse"
    parentFileNameHint="Base_R91.vmdk"
    # Extent description
    RW 41943040 SESPARSE "Base_R91-000001-sesparse.vmdk"
    
    # The Disk Data Base
    #DDB
    
    ddb.encoding = "UTF-8"
    ddb.grain = "8"
    ddb.longContentID = "f6371048ed90dd02a7e9ded6fffffffe"
"""
)

parent_vmdk = dedent(
    """\
    # Disk DescriptorFile
    version=1
    CID=3729b687
    parentCID=ffffffff
    createType="vmfs"
    
    # Extent description
    RW 41943040 VMFS "Base_R91-flat.vmdk"
    
    # The Disk Data Base
    #DDB
    
    ddb.adapterType = "ide"
    ddb.deletable = "true"
    ddb.encoding = "UTF-8"
    ddb.geometry.cylinders = "41610"
    ddb.geometry.heads = "16"
    ddb.geometry.sectors = "63"
    ddb.longContentID = "f6371048ed90dd02a7e9ded6fffffffe"
    ddb.thinProvisioned = "1"
    ddb.uuid = "60 00 C2 9f 9a b0 9b 9c-13 55 b8 11 fd 2c 92 9b"
    ddb.virtualHWVersion = "6"
"""
)

getallvms = dedent(
    """\
Vmid            Name                              File                       Guest OS      Version   Annotation
1      AT_ESXI_050             [datastore_050] AT_ESXI/AT_ESXI.vmx   ubuntu64Guest   vmx-11
24     Test Test [Test] [Test]   [datastore_050_vmfs6] Test/Test.vmx       otherGuest64    vmx-17
"""
)

hostapi_cert_bytes = list(
    dedent(
        """\
-----BEGIN CERTIFICATE-----
MIIDeDCCAmCgAwIBAgIULSI68CT+a61Fzi5UifInXs8SwgcwDQYJKoZIhvcNAQEL
BQAwZzELMAkGA1UEBhMCVVMxEzARBgNVBAgMCkNhbGlmb3JuaWExFjAUBgNVBAcM
DVNhbiBGcmFuY2lzY28xEzARBgNVBAoMCk15IENvbXBhbnkxFjAUBgNVBAMMDW15
Y29tcGFueS5jb20wHhcNMjUwNzA5MjEzMTA0WhcNMjYwNzA5MjEzMTA0WjBnMQsw
CQYDVQQGEwJVUzETMBEGA1UECAwKQ2FsaWZvcm5pYTEWMBQGA1UEBwwNU2FuIEZy
YW5jaXNjbzETMBEGA1UECgwKTXkgQ29tcGFueTEWMBQGA1UEAwwNbXljb21wYW55
LmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMZyFhfQZxmJgHnB
5IgQQNHFRIRG0fcIIOscmQdsPAsFEoABAVWZMDBllVbyrzRm5yH08edL7d/bR2LV
OjsKTO6dD77hAEcXLU6D0byF4GLunky0XYfA+8kdF9RUUZLJY/Q4aNe2rswdB7eB
zSO0I4bOBIeOb5DfOK/rMYUHJzWHNOYUUf2w4H9p06wKAnX22gnUKIuDMOZ9D56Y
E62W1LMkVOgD5mqDN+oOxSR40M03gHSEk01H3biJJjgbvKD0VLEcJTyO7cD1TLPe
AlhyNGIW885IKzIBXi0zSwRD+qK6sJAHock2WkEh1fGzJW4K1hMsy0NuzzWzNWsj
OvXCfm8CAwEAAaMcMBowGAYDVR0RBBEwD4INbXljb21wYW55LmNvbTANBgkqhkiG
9w0BAQsFAAOCAQEAuqOaW3JONXZaN7DRrj7mzJON1Mviqi+sBag3yYs1YYL4/qxd
sukwbnSvLD6rGW8w9Ez/6K16dkLo4lMy3IsOMoecMrohDnDvtYxmcPmDknUjvPON
Bk5DAaaC7paIT0zcZ/UzZbd5MbJWPhggmcFGUVTl2ftsVb1jVm5O/sMaV785Y9Cd
+tEjfxfFmJ3WnInjElHTa16ZJreRPxGnUfBLonr7GUflMe+15C3CVJXgBxUUCvR1
ygm1smzjqu67KzXYAEibj4HBvlEtpOequkcAp6oD1L22OLXq4LH9DRkr2V2WKi3y
zwtSfd09AbWPe53xxdYlvsniRi1vaB3El+Zn7Q==
-----END CERTIFICATE-----
    """
    ).encode("UTF-8")
)
