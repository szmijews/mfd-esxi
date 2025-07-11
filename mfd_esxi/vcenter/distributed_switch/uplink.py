# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""DSUplink wrapper."""
import logging
from typing import Dict, Union, Optional
from pyVmomi import vim
from time import sleep
from typing import TYPE_CHECKING

from mfd_common_libs import log_levels, add_logging_level
from ..exceptions import VCenterDistributedSwitchUplinkRemovalFailed

if TYPE_CHECKING:
    from .dswitch import DSwitch
    from ..host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class DSUplink(object):
    """DSUplink wrapper."""

    def __init__(self, name: str, number: int, dswitch: "DSwitch"):
        """
        Initialize instance.

        :param name: Name of uplink.
        :param number: Number of uplink.
        :param dswitch: Distributed Switch.
        """
        self._name = name
        self._number = number
        self._dswitch = dswitch

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def name(self) -> str:
        """Get name for DSUplink."""
        return self._name

    @property
    def nics(self) -> Dict[str, Dict[str, Union[str, vim.dvs.HostMember]]]:
        """Get all nics from uplink."""
        nics = {}
        for host in self._dswitch.content.config.host:
            port_key = int(host.uplinkPortKey[0])
            for nic in host.config.backing.pnicSpec:
                if int(nic.uplinkPortKey) - port_key == self._number:
                    name = host.config.host.name
                    nics[name] = {
                        "nic": nic.pnicDevice,
                        "host": self._dswitch.get_host(name),
                    }
        return nics

    def add_nic(self, host: "Host", nic: str) -> None:
        """
        Assign new nic from host to uplink.

        :param host: Host from we get NIC.
        :param nic: Name NIC e.g vmnic1.
        """
        self._set_nic_repeat(host, nic)

    def del_nic(self, host: "Host") -> None:
        """
        Remove new nic from host to uplink.

        :param host: Host from we remove NIC.
        """
        self._set_nic_repeat(host, None)

    def del_all_nics(self) -> None:
        """Remove all nics from this uplink."""
        for host in self._dswitch.hosts:
            self.del_nic(host)

    def _set_nic_repeat(self, host: "Host", nic: Optional[str]) -> None:
        """
        Set host nic for uplink repeating in case of exception.

        :param host: Host.
        :param nic: Name nic to set or None to remove.
        """
        for time in range(1, 6):
            try:
                self._set_nic(host, nic)
                return
            except vim.fault.ConcurrentAccess:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Cannot complete operation due to concurrent operation. Sleeping {time} seconds.",
                )
                sleep(time)
            except vim.fault.DvsOperationBulkFault as ex:
                if nic is None:
                    logger.log(level=log_levels.MODULE_DEBUG, msg=ex)
                    raise VCenterDistributedSwitchUplinkRemovalFailed()
                else:
                    raise ex

        self._set_nic(host, nic)

    def _set_nic(self, host: "Host", nic: str) -> None:
        """
        Set host nic for uplink.

        :param host: Host.
        :param nic: Name nic to set or None to remove.
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Setup NIC: {nic} {host} on uplink {self.name} for {self._dswitch.name}",
        )
        for ds_host in self._dswitch.content.config.host:
            if ds_host.config.host.name == host.name:
                ds_spec = self._dswitch.get_ds_config_spec()
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"DSwitch {self.name} old spec\n{ds_spec}",
                )
                host_spec = self._dswitch.get_ds_host_config_spec(host, vim.ConfigSpecOperation.edit)

                host_spec.backing = ds_host.config.backing  # vim.dvs.HostMember.PnicBacking()
                if nic:
                    for nr, ps in enumerate(host_spec.backing.pnicSpec):
                        if str(ps.uplinkPortKey) == str(self._number):
                            del host_spec.backing.pnicSpec[nr]
                            break
                    nic_spec = vim.dvs.HostMember.PnicSpec()
                    nic_spec.pnicDevice = nic
                    nic_spec.uplinkPortKey = ds_host.uplinkPortKey[self._number]
                    host_spec.backing.pnicSpec.append(nic_spec)
                else:
                    for nr, ps in enumerate(host_spec.backing.pnicSpec):
                        if str(ps.uplinkPortKey) == str(self._number):
                            del host_spec.backing.pnicSpec[nr]
                            break
                    else:
                        return

                ds_spec.host = [host_spec]
                self._dswitch.vcenter.wait_for_tasks([self._dswitch.content.ReconfigureDvs_Task(ds_spec)])
                break
