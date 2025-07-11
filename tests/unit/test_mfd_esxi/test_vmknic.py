# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from ipaddress import ip_interface

from .fixtures import esxcfg_vmknic_1
from mfd_typing import MACAddress
from mfd_esxi.vmknic import Vmknic


class TestVmknic:
    def test_initialize(self, host):
        vmknic = Vmknic(host, "vmk1")
        vmknic.initialize(esxcfg_vmknic_1)
        assert vmknic.mtu == 1500
        assert vmknic.name == "vmk1"
        assert vmknic.portgroup == "ATvmnic10"
        assert vmknic.mac == MACAddress("00:50:56:aa:bb:cc")

    def test_refresh(self, host_esxcfg_vmknic_2):
        vmknic = Vmknic(host_esxcfg_vmknic_2, "vmk2")
        vmknic.refresh()
        assert str(vmknic.mac) == "00:50:56:aa:bb:cc"
        assert vmknic.ips[0] == ip_interface("fe80::250:56ff:fe63:a0ef/64")

    def test_discover(self, host_esxcfg_vmknic_1):
        vmknics = Vmknic.discover(host_esxcfg_vmknic_1)
        assert len(vmknics) == 2

    def test_add_vmknic(self, host_esxcfg_vmknic_2):
        vmknic = Vmknic.add_vmknic(host_esxcfg_vmknic_2, "PGvmnic0")
        assert vmknic.name == "vmk2"
        assert vmknic.portgroup == "PGvmnic0"
        assert vmknic.mtu == 9000
        assert len(vmknic.ips) == 1
        assert ip_interface("fe80::250:56ff:fe63:a0ef/64") in vmknic.ips

    def test_del_vmknic(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.del_vmknic()

    def test_set_mtu(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.set_mtu(5000)
        assert vmknic.mtu == 5000

    def test_set_vlan(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.set_vlan(500)

    def test_add_ipv4(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.add_ip("1.1.1.1/8")
        assert len(vmknic.ips) == 1
        assert vmknic.ips[0] == ip_interface("1.1.1.1/8")

    def test_add_ipv4_multiple(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.add_ip("1.1.1.1/8")
        vmknic.add_ip("2.1.1.1/8")
        assert len(vmknic.ips) == 1
        assert vmknic.ips[0] == ip_interface("2.1.1.1/8")

    def test_add_ipv6(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.add_ip("2001:1::1/64")
        assert len(vmknic.ips) == 1
        assert vmknic.ips[0] == ip_interface("2001:1::1/64")

    def test_add_ipv6_multiple(self, host):
        vmknic = Vmknic(host, "vmk2")
        vmknic.add_ip("2001:1::1/64")
        vmknic.add_ip("2001:1::2/64")
        assert len(vmknic.ips) == 2

    def test_discover_vxlan_vmk(self, host_esxcfg_vmknic_3):
        vmknics = Vmknic.discover(host_esxcfg_vmknic_3)
        assert len(vmknics) == 2
