# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""VCenter wrapper."""
import logging
from itertools import chain
from http.client import HTTPException
from socket import error as socket_error
from atexit import register as exit_register
from typing import List, Union, Any, Generator, Iterable, Optional, Type, TYPE_CHECKING
from pyVim import connect as pyvmomi_connect
from pyVmomi import vim
from pyVmomi import vmodl
from packaging.version import parse as version_parse, Version

from mfd_common_libs import log_levels, add_logging_level
from .datacenter import Datacenter
from .utils import get_obj_from_iter
from .exceptions import VCenterInvalidLogin, VCenterSocketError

if TYPE_CHECKING:
    from .cluster import Cluster
    from .host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class VCenter:
    """VCenter wrapper."""

    def __init__(self, ip: str, login: str, password: str, port: int = 443):
        """
        Initialize instance.

        :param ip: VCenter IP address.
        :param login: Login name.
        :param password: Password.
        :param port: Port number.
        """
        self.__service = None
        self._content = None
        self._ip = ip
        self._login = login
        self._password = password
        self._port = port

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self._ip}')"

    @property
    def content(self) -> "vim.ServiceInstance":
        """Get content of VCenter in API."""
        try:
            if self.__service:
                if self._content.sessionManager.currentSession:
                    return self._content
                else:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"{self._ip} the session has expired",
                    )
        except (HTTPException, ConnectionError):
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"{self._ip} HTTP connection error, reconnecting",
            )

        self._content = self._reconnect()
        return self._content

    def wait_for_tasks(self, tasks: List["vim.Task"]) -> None:  # noqa: C901
        """
        Wait for task to end.

        :param tasks: List of task to process.
        """
        task_list = [str(task) for task in tasks]
        if task_list:
            # Create filter
            obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task) for task in tasks]
            property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task, pathSet=[], all=True)
            filter_spec = vmodl.query.PropertyCollector.FilterSpec()
            filter_spec.objectSet = obj_specs
            filter_spec.propSet = [property_spec]
            pcfilter = self.content.propertyCollector.CreateFilter(filter_spec, True)
            try:
                version, state = None, None
                # Loop looking for updates till the state moves to a completed state.
                while len(task_list):
                    update = self.content.propertyCollector.WaitForUpdates(version)
                    for filter_set in update.filterSet:
                        for obj_set in filter_set.objectSet:
                            task = obj_set.obj
                            for change in obj_set.changeSet:
                                if change.name == "info":
                                    state = change.val.state
                                elif change.name == "info.state":
                                    state = change.val
                                else:
                                    continue

                                if not str(task) in task_list:
                                    continue

                                if state == vim.TaskInfo.State.success:
                                    # Remove task from taskList
                                    task_list.remove(str(task))
                                elif state == vim.TaskInfo.State.error:
                                    raise task.info.error
                    # Move to next version
                    version = update.version
            finally:
                if pcfilter:
                    pcfilter.Destroy()

    @property
    def datacenters(self) -> Generator["Datacenter", Any, None]:
        """Get all datacenters."""
        return (Datacenter(dc.name, self) for dc in self.create_view(self.content.rootFolder, [vim.Datacenter]))

    def get_datacenter_by_name(self, name: str) -> "Datacenter":
        """Get specific datacenter from VCenter.

        :param name: Name of datacenter.

        :return: Specific datacenter.
        """
        return get_obj_from_iter(self.datacenters, name)

    def add_datacenter(self, name: str) -> "Datacenter":
        """
        Add new datacenter.

        :param name: Name of datacenter

        :return: New datacenter.
        """
        try:
            self.content.rootFolder.CreateDatacenter(name)
        except vim.fault.DuplicateName:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Datacenter: {name} already exist return existing",
            )
        return Datacenter(name, self)

    @property
    def clusters(self) -> Iterable["Cluster"]:
        """Get all clusters in VCenter."""
        return chain(*(dc.clusters for dc in self.datacenters))

    def get_cluster_by_name(self, name: str) -> "Cluster":
        """
        Get specific cluster from VCenter.

        :param name: Name of cluster.

        :return: Specific cluster.
        """
        return get_obj_from_iter(self.clusters, name)

    @property
    def hosts(self) -> Iterable["Host"]:
        """Get all hosts from VCenter."""
        return chain(*(dc.hosts for dc in self.datacenters))

    def get_host_by_ip(self, ip: str) -> "Host":
        """
        Get specific host from VCenter.

        :param ip: IP of host.

        :return: Specific host.
        """
        return get_obj_from_iter(self.hosts, ip)

    def create_view(
        self,
        folder: Union[
            "vim.Folder",
            "vim.Datacenter",
            "vim.ClusterComputeResource",
            "vim.HostSystem",
        ],
        types: Optional[List[Type["vim.ManagedEntity"]]],
        recursive: bool = False,
    ) -> List[
        Union[
            "vim.dvs.VmwareDistributedVirtualSwitch",
            "vim.Datacenter",
            "vim.ClusterComputeResource",
            "vim.HostSystem",
            "vim.VirtualMachine",
        ]
    ]:
        """
        Create a ContainerView managed object for this session.

        :param folder: A reference to an instance of a Folder, Datacenter, Resource, HostSystem.
        :param types: An optional list of managed entity types.
        :param recursive: Recursive search.

        :return: Container view.
        """
        return self.content.viewManager.CreateContainerView(folder, types, recursive).view

    def _connect(self) -> "vim.ServiceInstance":
        """
        Connect to the specified server using API.

        :return: Service content.
        """
        try:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Connecting to: {self._ip}")

            self.__service = pyvmomi_connect.SmartConnect(
                host=self._ip,
                user=self._login,
                pwd=self._password,
                port=self._port,
                connectionPoolTimeout=-1,
                disableSslCertValidation=True,
            )
            exit_register(self._disconnect)
            return self.__service.RetrieveServiceContent()
        except vim.fault.InvalidLogin:
            raise VCenterInvalidLogin
        except socket_error:
            raise VCenterSocketError

    def _disconnect(self) -> None:
        """Disconnect from server."""
        if self.__service:
            pyvmomi_connect.Disconnect(self.__service)
            self.__service = None
            self._content = None

    def _reconnect(self) -> "vim.ServiceInstance":
        """
        Reconnect to server.

        :return: Service content.
        """
        self._disconnect()
        return self._connect()

    @property
    def version(self) -> Version:
        """Get version of vSphere."""
        return version_parse(self._content.about.apiVersion)
