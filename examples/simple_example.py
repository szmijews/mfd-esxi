# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Simple example."""

import logging
from ipaddress import ip_interface

from mfd_connect import RPyCConnection
from mfd_host import Host

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


if __name__ == "__main__":
    connection = RPyCConnection("172.31.0.50")
    host = Host(connection=connection)
    adapter = host.network.get_interface(interface_name="vmnic2")
    host.virtualization.initialize(ip="172.31.0.50", login="root", password="***")
    host.virtualization.hv.clean(keep="AT_ESXI")

    print(host.virtualization.api.version)
    print(host.virtualization.api.get_performance_metrics([adapter]))
    print(host.virtualization.api.get_lldp_status(adapter))
    print(host.virtualization.api.get_adapters_sriov_info([adapter]))
    host.virtualization.api.set_adapters_sriov([adapter], 10, False)
    print(host.virtualization.api.get_adapters_sriov_info([adapter]))
    host.virtualization.api.set_adapters_sriov([adapter], 0, False)
    print(host.virtualization.api.get_adapters_sriov_info([adapter]))
    host.virtualization.api.set_adapters_sriov([adapter], 8, False)
    print(host.virtualization.api.get_adapters_sriov_info([adapter]))

    for vswitch in host.virtualization.vswitch:
        if vswitch.name in ["test1", "ATvSwitch", "TESTvSwitch"]:
            host.virtualization.del_vswitch(vswitch.name)

    vswitch1 = host.virtualization.set_vswitch(
        "test1", uplinks=["vmnic2", "vmnic3"], portgroups=["t1a", "t1b"], mtu=9000
    )
    vswitch1.set_portgroup_vlan("t1a", 82)
    vswitch1.change_ens_fpo_support(True, "vSphereDistributedSwitch")
    vmknic1 = host.virtualization.find_vmknic(portgroup="PGvmnic2")
    vmknic1.add_ip(ip_interface("1.1.1.1/8"))
    vmknic1.add_ip("2.1.1.1/8")
    vmknic1.add_ip(ip_interface("2001:1::2/64"))
    vmknic1.add_ip("2001:1::3/64")
    vswitch1.reconfigure(uplinks=["vmnic2"], portgroups=["t1a"])
    vswitch1.reconfigure(uplinks=["vmnic2", "vmnic3"], portgroups=["t1a", "t1b"], mtu=9000)
    vmknic1.del_ip("2001:1::2/64")

    vswitch = host.virtualization.set_vswitch("test1", uplinks=["vmnic2"], portgroups=["test1"])

    vswitch.set_mac_change_policy(portgroup_name="test1", enabled=True)

    vms91 = host.virtualization.hv.prepare_vms("datastore_050_vmfs6", "Base_R91", count=1, suffix="050")
    host.virtualization.hv.attach_network(vms91, portgroup="test1", model="sriov", adapter=adapter)
    host.virtualization.hv.create_vms(vms91)

    vms90 = host.virtualization.hv.prepare_vms("datastore_050", "Base_R90", count=4, suffix="050")
    host.virtualization.hv.attach_network(vms90, portgroup="test1")
    host.virtualization.hv.create_vms(vms90)

    host.virtualization.hv.clean(keep="AT_ESXI")
