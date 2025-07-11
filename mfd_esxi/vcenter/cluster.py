# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Cluster wrapper."""
import logging
from packaging.version import parse as version_parse
from typing import Any, Generator, TYPE_CHECKING
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from .host import Host
from .exceptions import VCenterResourceInUse, VCenterResourceSetupError
from .utils import get_obj_from_iter, get_first_match_from_iter

if TYPE_CHECKING:
    from .vcenter import VCenter
    from .datacenter import Datacenter


logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class Cluster(object):
    """Cluster wrapper."""

    def __init__(self, name: str, datacenter: "Datacenter"):
        """
        Initialize instance.

        :param name: Name of cluster.
        :param datacenter: Datacenter.
        """
        self._name = name
        self._datacenter = datacenter

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def content(self) -> "vim.ClusterComputeResource":
        """Get content of cluster in API."""
        return get_obj_from_iter(
            self.vcenter.create_view(self._datacenter.content.hostFolder, [vim.ClusterComputeResource]),
            self.name,
        )

    @property
    def name(self) -> str:
        """Get name of cluster."""
        return self._name

    def destroy(self) -> None:
        """Remove cluster from datacenter."""
        try:
            self.vcenter.wait_for_tasks([self.content.Destroy()])
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. Cluster: {self.name} does not exist.",
            )

    @property
    def vcenter(self) -> "VCenter":
        """Get VCenter for this cluster."""
        return self._datacenter.vcenter

    @property
    def hosts(self) -> Generator["Host", Any, None]:
        """Get all hosts from cluster."""
        return (
            Host(host.name, self._datacenter, self)
            for host in self.vcenter.create_view(self.content, [vim.HostSystem])
        )

    def get_host_by_ip(self, ip: str) -> "Host":
        """
        Get specific host from cluster.

        :param ip: Host IP address.

        :return: Specific host form cluster.
        """
        return get_obj_from_iter(self.hosts, ip)

    def add_host(self, ip: str, login: str, password: str, fingerprint: str) -> "Host":
        """
        Add host to cluster.

        :param ip: Host IP address.
        :param login: Login to the host.
        :param password: Password for the host.
        :param fingerprint: Fingerprint for the host.

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
            self.vcenter.wait_for_tasks([self.content.AddHost(spec=spec, asConnected=True)])
        except vim.fault.DuplicateName:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Host: {ip} already exist return existing",
            )
        if get_first_match_from_iter(self.hosts, lambda h: h.name == ip) is None:
            raise VCenterResourceSetupError(self)

        host = Host(ip, self._datacenter, self)
        # vSphere from version 7.0.3 should be configured to change system VM location
        if self.vcenter.version >= version_parse("7.0.3"):
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"vCenter is in version {self.vcenter.version}, system VM will be reconfigured",
            )
            self.reconfigure_system_vm(host)
        return host

    def set_evc(self, value: str = "intel-sandybridge") -> None:
        """
        Set Enhanced vMotion Compatibility.

        :param value: CPU compatibility mode.
        """
        mgr = self.content.EvcManager()
        task = mgr.ConfigureEvc(value)
        self.vcenter.wait_for_tasks([task])

    def reconfigure_system_vm(self, host: "Host") -> None:
        """
        Reconfigure host to use its local datastore for system VM.

        :param host: Host which should be reconfigured.
        """
        cluster_spec = vim.cluster.ConfigSpecEx()
        system_vm_spec = vim.cluster.SystemVMsConfigSpec()
        local_datastore_name = get_first_match_from_iter(host.datastores, lambda ds: "datastore" in ds.name).name
        local_datastore_spec = get_first_match_from_iter(
            self.content.datastore, lambda x: x.name == local_datastore_name
        )

        allowed_datastore_spec = vim.cluster.DatastoreUpdateSpec(operation="add", datastore=local_datastore_spec)

        system_vm_spec.allowedDatastores.append(allowed_datastore_spec)
        cluster_spec.systemVMsConfig = system_vm_spec

        self.vcenter.wait_for_tasks([self.content.ReconfigureEx(spec=cluster_spec, modify=True)])
