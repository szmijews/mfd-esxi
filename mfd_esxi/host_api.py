# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""ESXi host support for API/pyvmomi."""
import logging
from atexit import register as exit_register
from OpenSSL.crypto import load_certificate, FILETYPE_PEM
from packaging.version import Version
from http.client import HTTPException
from socket import error as socket_error
from time import sleep
from typing import List, Dict, Union, Tuple
from pyVim import connect
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from mfd_network_adapter.network_interface import NetworkInterface
from .exceptions import ESXiAPIInvalidLogin, ESXiAPISocketError

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class ESXiHostAPI(object):
    """ESXi SOAP API wrapper."""

    def __init__(self, ip: str, login: str, password: str, port: int = 443):
        """
        Init object.

        :param ip: VCenter IP address
        :param login: Login name
        :param password: Password
        :param port: Port number
        """
        self.__service = None
        self.__content = None
        self._ip = ip
        self._login = login
        self._password = password
        self._port = port
        self._fingerprint = None

    def __repr__(self) -> str:
        """Return string representation of an object.

        :return: class name and IP address
        """
        return f"{self.__class__.__name__}('{self._ip}')"

    @property
    def _content(self) -> vim.ServiceInstance:
        """Content of VCenter in API.

        :return: Service content
        """
        try:
            if self.__service:
                if self.__content.sessionManager.currentSession:
                    return self.__content
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

        self.__content = self._reconnect()
        return self.__content

    def _connect(self) -> vim.ServiceInstance:
        """Connect to the specified server using API.

        :return: Service content
        :raise AgatVCenterInvalidLogin: Invalid login for VCenter
        :raise AgatVCenterSocketError: Error with connection
        """
        try:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Connecting to: {self._ip}")

            self.__service = connect.SmartConnect(
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
            raise ESXiAPIInvalidLogin
        except socket_error:
            raise ESXiAPISocketError

    def _disconnect(self) -> None:
        """Disconnect from server."""
        if self.__service:
            connect.Disconnect(self.__service)
            self.__service = None
            self.__content = None

    def _reconnect(self) -> vim.ServiceInstance:
        """Reconnect server.

        :return: Service content
        """
        self._disconnect()
        return self._connect()

    @property
    def version(self) -> "Version":
        """Return version of vSphere as float.

        :return: version object
        """
        return Version(self._content.about.apiVersion)

    def get_host(self) -> "vim.HostSystem":
        """Get host object from local content.

        :return: host object
        """
        return self._content.viewManager.CreateContainerView(self._content.rootFolder, [vim.HostSystem], True).view[0]

    def get_lldp_status(self, adapter: "NetworkInterface") -> "vim.host.PhysicalNic.LldpInfo":
        """Get LLDP status.

        :param adapter: Device Interface
        :return: LLDP info of the interface
        """
        esxi_host = self.get_host()
        network_system = esxi_host.configManager.networkSystem
        for hint in network_system.QueryNetworkHint(device=[adapter.name]):
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"LLDP info for {hint.device} is {hint.lldpInfo}",
            )
            return hint.lldpInfo

    def set_adapters_sriov(
        self,
        adapters: Union[List["NetworkInterface"], List[str]],
        num_vf: int = 0,
        wait: bool = True,
    ) -> None:
        """Update SRIOV settings.

        :param adapters: list of adapters or list of pci addresses on which VFs will be set
        :param num_vf: number of Virtual Functions
        :param wait: wait for driver to parse new VFs
        """
        esxi_host = self.get_host()
        pci_passthru_system = esxi_host.configManager.pciPassthruSystem
        for adapter in adapters:
            if isinstance(adapter, NetworkInterface):
                pci = adapter.pci_address.lspci
            else:
                pci = adapter

            config = vim.host.SriovConfig()
            config.sriovEnabled = True if num_vf > 0 else False
            config.numVirtualFunction = num_vf
            config.id = pci

            pci_passthru_system.UpdatePassthruConfig([config])

            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Number of Virtual Functions has been updated to {num_vf} on {pci}",
            )

        if wait:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg="Wait extra 30 seconds to initialize driver features",
            )
            sleep(30)

    def get_adapters_sriov_info(
        self, adapters: List["NetworkInterface"], all_ports: bool = False
    ) -> Dict[str, Dict[str, Union[bool, int]]]:
        """Get info about SR-IOV properties of adapter.

        :param adapters: NetworkInterface
        :param all_ports: get all ports of adapter
        :return: dict with adapters info
        """
        adapters_info = {}
        adapters_lspci = set()
        if not all_ports:
            for adapter in adapters:
                adapters_lspci.add(adapter.pci_address.lspci.split(".")[0] + ".")
        else:
            for adapter in adapters:
                adapters_lspci.add(adapter.pci_address.lspci)

        esxi_host = self.get_host()
        pci_passthru_system = esxi_host.configManager.pciPassthruSystem

        for device in pci_passthru_system.pciPassthruInfo:
            lspci = device.id
            if not all_ports:
                lspci = lspci.split(".")[0] + "."
            for adapter in adapters_lspci:
                if lspci == adapter:
                    try:
                        max_vfs = device.maxVirtualFunctionSupported
                        num_vfs = device.numVirtualFunction
                        req_vfs = device.numVirtualFunctionRequested
                        enabled = device.sriovEnabled
                        adapters_info[device.id] = {
                            "max_vfs": max_vfs,
                            "num_vfs": num_vfs,
                            "req_vfs": req_vfs,
                            "enabled": enabled,
                        }
                    except AttributeError:
                        # Adapter not supporting SR-IOV do not have maxVirtualFunctionSupported
                        adapters_info[device.id] = {
                            "max_vfs": 0,
                            "num_vfs": 0,
                            "req_vfs": 0,
                            "enabled": False,
                        }
                    adapters_lspci.remove(adapter)
                    break
        return adapters_info

    @staticmethod
    def get_performance_metrics_keys(
        perf_manager: vim.PerformanceManager,
    ) -> Dict[str, int]:
        """Get all possible counters and their keys.

        :param perf_manager: performance manager
        :return: all possible system counters and their keys
        """
        counter_info = {}
        for counter in perf_manager.perfCounter:
            full_name = f"{counter.groupInfo.key}.{counter.nameInfo.key}.{counter.rollupType}"
            counter_info[full_name] = counter.key
        return counter_info

    @staticmethod
    def get_performance_metrics_stats(
        metrics: List[Tuple[vim.PerformanceManager.MetricId, str]],
        esxi_host: vim.HostSystem,
        perf_manager: vim.PerformanceManager,
    ) -> List:
        """Gather stats from metrics.

        :param metrics: metrics to gather
        :param esxi_host: host instance
        :param perf_manager: performance manager
        :return: gathered performance stats
        """
        stats = []
        for metric, name in metrics:
            query = vim.PerformanceManager.QuerySpec(entity=esxi_host, metricId=[metric])
            stats.append((perf_manager.QueryPerf(querySpec=[query]), name))
        return stats

    @staticmethod
    def create_performance_metrics_table(
        columns: List[str], stats: List, create_chart: bool = True
    ) -> Union[str, Dict]:
        """Create table with performance stats.

        :param columns: column names
        :param stats: gathered performance stats
        :param create_chart: indicates if table with metrics should be created
        :return: table with performance stats to be printed
        """
        # Create nested dicts with stat results
        lines = {}
        for stat, name in stats:
            count = 0
            try:
                for value in stat[0].value[0].value:
                    val = float(value / 100)
                    stamp = stat[0].sampleInfo[count].timestamp

                    # Update line of chart with stat value
                    line = lines.get(stamp, {})
                    line[name] = val
                    lines[stamp] = line

                    count += 1
            except IndexError:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Error getting data, skipping row {name}",
                )

        if not create_chart:
            return lines

        # Create output chart
        line = " " * 30
        for column in columns:
            line += " " * (12 - len(column)) + column
        chart = [line]
        for line in sorted(lines.keys()):
            np = str(line) + " - "
            output = f"{np:30}"
            for column in columns:
                value = lines[line].get(column, float("NaN"))
                output += f"{value:12.2f}"
            chart.append(output)

        return "\n".join(chart)

    def get_performance_metrics(
        self, adapters: List["NetworkInterface"], create_chart: bool = True
    ) -> Union[str, Dict]:
        """Get performance data from performance manager.

        :param adapters: adapters to gather throughput
        :param create_chart: indicates if table with metrics should be created
        :return: table with gathered performance metrics
        """
        esxi_host = self.get_host()
        perf_manager = self._content.perfManager

        # Get all possible counters
        counter_info = self.get_performance_metrics_keys(perf_manager)

        # Get keys of interesting counters
        key_c = counter_info["cpu.usage.average"]
        key_r = counter_info["net.received.average"]
        key_t = counter_info["net.transmitted.average"]

        # Prepare columns and metrics
        metrics = [(vim.PerformanceManager.MetricId(counterId=key_c, instance=""), "CPU")]
        columns = ["CPU"]
        for adapter in adapters:
            name = adapter.name + "-Rx"
            columns.append(name)
            metrics.append(
                (
                    vim.PerformanceManager.MetricId(counterId=key_r, instance=adapter.name),
                    name,
                )
            )
            name = adapter.name + "-Tx"
            columns.append(name)
            metrics.append(
                (
                    vim.PerformanceManager.MetricId(counterId=key_t, instance=adapter.name),
                    name,
                )
            )

        # Gather stats from metrics
        stats = self.get_performance_metrics_stats(metrics=metrics, esxi_host=esxi_host, perf_manager=perf_manager)

        return self.create_performance_metrics_table(columns=columns, stats=stats, create_chart=create_chart)

    @property
    def fingerprint(self) -> str:
        """Get fingerprint of host certificate."""
        if self._fingerprint is None:
            self._fingerprint = self.get_fingerprint()
        return self._fingerprint

    def get_fingerprint(self, digest: str = "sha1") -> str:
        """Get fingerprint of host certificate using digest algorithm.

        :param digest: Name of digest algorithm.

        :return: Fingerprint of host certificate.
        """
        cert_bytes = bytes(self.get_host().config.certificate)
        cert = load_certificate(FILETYPE_PEM, cert_bytes)
        fingerprint_bytes = cert.digest(digest)
        return fingerprint_bytes.decode("UTF-8")
