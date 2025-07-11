# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
# pylint: disable=protected-access
"""Datacenter wrapper."""
import logging
from typing import Any, Generator, Iterable, TYPE_CHECKING

from pyVmomi import vim
from itertools import chain
from packaging.version import parse as version_parse

from .host import Host
from .cluster import Cluster
from .distributed_switch.dswitch import DSwitch
from ..const import ESXI_UPLINK_FORMAT, ESXI_UPLINK_NUMBER

from .exceptions import (
    VCenterResourceInUse,
    VCenterResourceMissing,
    VCenterResourceSetupError,
)
from .utils import get_obj_from_iter, get_first_match_from_iter

from mfd_common_libs import log_levels, add_logging_level

if TYPE_CHECKING:
    from .datastore import Datastore
    from .vcenter import VCenter


logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class Datacenter(object):
    """Datacenter wrapper."""

    def __init__(self, name: str, vcenter: "VCenter"):
        """
        Initialize instance.

        :param name: Name of datacenter.
        :param vcenter: VCenter.
        """
        self._name = name
        self._vcenter = vcenter

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> "vim.Datacenter":
        """Content of datacenter in API."""
        return get_obj_from_iter(
            self.vcenter.create_view(self.vcenter.content.rootFolder, [vim.Datacenter]),
            self.name,
        )

    @property
    def name(self) -> str:
        """Get name of datacenter."""
        return self._name

    @property
    def network_folder(self) -> "vim.Folder":
        """Get network folder of datacenter."""
        return self.content.networkFolder

    def destroy(self) -> None:
        """Remove datacenter from VCenter."""
        try:
            self.vcenter.wait_for_tasks([self.content.Destroy()])
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except VCenterResourceMissing:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Datacenter: {self.name} does not exist.",
            )

    @property
    def vcenter(self) -> "VCenter":
        """Get VCenter for this datacenter."""
        return self._vcenter

    @property
    def dswitches(self) -> Generator["DSwitch", Any, None]:
        """Get all dswitches."""
        return (
            DSwitch(ds.name, self)
            for ds in self.vcenter.create_view(self.content.networkFolder, [vim.dvs.VmwareDistributedVirtualSwitch])
        )

    def get_dswitch_by_name(self, name: str) -> "DSwitch":
        """
        Get specific DSwitch from datacenter.

        :param name: Name of DSwitch.
        :return: DSwitch.
        """
        return get_obj_from_iter(self.dswitches, name)

    def add_dswitch(
        self,
        name: str,
        uplinks: int = ESXI_UPLINK_NUMBER,
        version: str = "6.0.0",
        networkIO: bool = True,
    ) -> "DSwitch":
        """
        Add new DSwitch to datacenter.

        :param name: Name of DSwitch
        :param uplinks: Number of uplinks
        :param version: Version of DSwitch
        :param networkIO: enable Network I/O

        :return: New DSwitch.
        """
        version = version_parse(version)
        try:
            dswitch = self.get_dswitch_by_name(name)
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"DSwitch: {name} already exist return existing",
            )
            return dswitch
        except VCenterResourceMissing:
            pass

        create_spec = vim.DistributedVirtualSwitch.CreateSpec()
        config_spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()

        config_spec.name = name
        config_spec.uplinkPortPolicy = vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()

        uplink_port_names = []
        for i in range(1, uplinks + 1):
            uplink_port_names.append(ESXI_UPLINK_FORMAT % i)

        config_spec.uplinkPortPolicy.uplinkPortName = uplink_port_names

        if version != version_parse("5.0.0") and version != version_parse("5.1.0"):
            config_spec.lacpApiVersion = vim.dvs.VmwareDistributedVirtualSwitch.LacpApiVersion.multipleLag

        create_spec.configSpec = config_spec
        create_spec.productInfo = vim.dvs.ProductSpec(version=version.base_version)

        task = self.content.networkFolder.CreateDistributedVirtualSwitch(create_spec)
        self.vcenter.wait_for_tasks([task])
        dswitch = DSwitch(name, self)
        dswitch.networkIO = networkIO
        return dswitch

    @property
    def clusters(self) -> Generator["Cluster", Any, None]:
        """Gat all clusters from datacenter."""
        return (
            Cluster(cluster.name, self)
            for cluster in self.vcenter.create_view(self.content.hostFolder, [vim.ClusterComputeResource])
        )

    def get_cluster_by_name(self, name: str) -> "Cluster":
        """
        Get specific cluster from datacenter.

        :param name: Name of cluster.

        :return: Cluster.
        """
        return get_obj_from_iter(self.clusters, name)

    def add_cluster(self, name: str) -> "Cluster":
        """
        Add new Cluster to datacenter.

        :param name: Name of Cluster.

        :return: New Cluster.
        """
        try:
            cluster_spec = vim.cluster.ConfigSpecEx()

            self.content.hostFolder.CreateClusterEx(name=name, spec=cluster_spec)
        except vim.fault.DuplicateName:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Cluster: {name} already exist return existing",
            )
        return Cluster(name, self)

    @property
    def hosts(self) -> Iterable["Host"]:
        """Get all hosts from datacenter."""
        hosts = (
            Host(host.name, self)
            for host in self.vcenter.create_view(self.content.hostFolder, [vim.ComputeResource])
            if not isinstance(host, vim.ClusterComputeResource)
        )

        return chain(hosts, *(cluster.hosts for cluster in self.clusters))

    def get_host_by_ip(self, ip: str) -> "Host":
        """
        Get specific host from datacenter.

        :param ip: Host IP address.

        :return: Host.
        """
        return get_obj_from_iter(self.hosts, ip)

    def add_host(self, ip: str, login: str, password: str, fingerprint: str) -> "Host":
        """
        Add standalone host to datacenter.

        :param ip: Host IP address
        :param login: Login to the host
        :param password: Password for the host
        :param fingerprint: Fingerprint for the host

        :return: New host.
        """
        spec = vim.host.ConnectSpec(
            hostName=ip,
            userName=login,
            password=password,
            force=True,
            sslThumbprint=fingerprint,
        )

        try:
            self.vcenter.wait_for_tasks([self.content.hostFolder.AddStandaloneHost(spec=spec, addConnected=True)])
        except vim.fault.DuplicateName:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Host: {ip} already exist return existing",
            )
        if get_first_match_from_iter(self.hosts, lambda h: h.name == ip) is None:
            raise VCenterResourceSetupError(f"Host@{ip}")
        return Host(ip, self)

    @property
    def datastores(self) -> Iterable["Datastore"]:
        """Get all datastores in VCenter."""
        return chain(*(host.datastores for host in self.hosts))
