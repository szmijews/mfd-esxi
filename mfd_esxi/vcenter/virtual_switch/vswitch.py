# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""VSwitch wrapper."""
import logging
from typing import Union, Any, Generator, Dict, Set, TYPE_CHECKING
from pyVmomi import vim

from mfd_common_libs import log_levels, add_logging_level
from ..utils import get_obj_from_iter
from ..exceptions import VCenterResourceMissing, VCenterResourceInUse
from ..virtual_switch.portgroup import VSPortgroup

if TYPE_CHECKING:
    from ..host import Host

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class VSwitch(object):
    """VSwitch wrapper."""

    _MTU_LOOKUP = {"default": 1500, "4k": 4074, "9k": 9000}

    def __init__(self, name: str, host: "Host"):
        """
        Initialize instance.

        :param name: Name of VSwitch.
        :param host: Host.
        """
        self._name = name
        self._host = host

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self.name}')"

    @property
    def name(self) -> str:
        """Name of vSwitch."""
        return self._name

    @property
    def content(self) -> vim.host.VirtualSwitch:
        """Content of vSwitch in API."""
        for vs in self._host.content.config.network.vswitch:
            if vs.name == self._name and isinstance(vs, vim.host.VirtualSwitch):
                return vs
        raise VCenterResourceMissing(self)

    def destroy(self) -> None:
        """Remove vSwitch form host."""
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Removing VSwitch: {self.name}")
        try:
            for pg in self.portgroups:
                pg.destroy()
            self._host.content.configManager.networkSystem.RemoveVirtualSwitch(self.name)
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"VSwitch {self.name} destroyed")
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
        except vim.fault.NotFound:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Nothing to remove. vSwitch: {self.name} does not exist.",
            )

    @property
    def mtu(self) -> int:
        """Get MTU value from vSwitch."""
        return self.content.mtu

    @mtu.setter
    def mtu(self, value: Union[int, str]) -> None:
        """
        Set MTU value for vSwitch.

        :param value: MTU value.
        :type value: int|str
        """
        spec = self.content.spec
        spec.mtu = self._MTU_LOOKUP.get(value) if value in self._MTU_LOOKUP.keys() else int(value)
        self._host.content.configManager.networkSystem.UpdateVirtualSwitch(self.name, spec)

    @property
    def portgroups(self) -> Generator["VSPortgroup", Any, None]:
        """Get all portgroups from vSwitch."""
        return (
            VSPortgroup(pg.spec.name, self._host)
            for pg in self._host.content.config.network.portgroup
            if pg.spec.vswitchName == self.name
        )

    def get_portgroup_by_name(self, name: str) -> "VSPortgroup":
        """
        Specific portgroup from vSwitch.

        :param name: Name of portgroup.

        :return: Portgroup object.
        """
        return get_obj_from_iter(self.portgroups, name)

    def add_portgroup(self, name: str) -> "VSPortgroup":
        """
        Add new portgroup to vSwitch.

        :param name: Name for new portgroup.

        :return: New portgroup.
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Adding portgroup: {name} to VSwitch {self.name}",
        )
        spec = vim.host.PortGroup.Specification()
        spec.name = name
        spec.vswitchName = self.name

        policy = vim.host.NetworkPolicy.SecurityPolicy()
        policy.allowPromiscuous = True
        policy.forgedTransmits = True
        policy.macChanges = False

        spec.policy = vim.host.NetworkPolicy(security=policy)
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"New portgroup: {name} for VSwitch {self.name} spec\n{spec}",
        )
        try:
            self._host.content.configManager.networkSystem.AddPortGroup(portgrp=spec)
        except vim.fault.AlreadyExists:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Portgroup: {name} already exist return existing.",
            )
        return VSPortgroup(name, self._host)

    @property
    def nics(self) -> Dict[str, Set[Union[str]]]:
        """Get all nics assigned to vSwitch grouped by active, standby, unused."""
        spec = self.content.spec
        if spec.bridge:
            nics = {
                "active": set(spec.policy.nicTeaming.nicOrder.activeNic),
                "standby": set(spec.policy.nicTeaming.nicOrder.standbyNic),
            }
            nics["unused"] = set(spec.bridge.nicDevice) - nics["active"] - nics["standby"]
            return nics
        return {"active": set(), "standby": set(), "unused": set()}

    @nics.setter
    def nics(self, value: Dict[str, Set[Union[str]]]) -> None:
        """
        Set nics to vSwitch.

        :param value: Dict of set.
        """
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Set NIC {value} on VSwitch: {self.name}",
        )
        new_nics = {"unused": set(), "active": set(), "standby": set()}
        new_nics.update(value)
        all_nics = new_nics["active"] | new_nics["standby"] | new_nics["unused"]

        spec = self.content.spec
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"VSwitch {self.name} old spec\n{spec}")

        if not spec.bridge and all_nics:
            spec.bridge = vim.host.VirtualSwitch.BondBridge()

        spec.bridge.nicDevice = list(all_nics)
        if not all_nics:
            spec.bridge = None

        spec.policy.nicTeaming.nicOrder.activeNic = list(new_nics["active"])
        spec.policy.nicTeaming.nicOrder.standbyNic = list(new_nics["standby"])
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"VSwitch {self.name} new spec\n{spec}")

        try:
            self._host.content.configManager.networkSystem.UpdateVirtualSwitch(self.name, spec)
        except vim.fault.ResourceInUse as e:
            raise VCenterResourceInUse(self, e.msg)
