# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX IP Pool."""
from time import sleep, time

from com.vmware.nsx_policy.model_client import (
    IpAddressPoolStaticSubnet,
    ChildIpAddressPoolSubnet,
    IpAddressPool,
    IpPoolRange,
    ChildIpAddressPool,
    Infra,
)
from com.vmware.vapi.std.errors_client import InvalidRequest

from ..exceptions import NsxResourceRemoveError
from .utils import api_call
from .base import NsxEntity


class NsxIpPool(NsxEntity):
    """NSX IP Pool."""

    @api_call
    def _get_content(self) -> IpAddressPool:
        return self._connection.api.policy.infra.IpPools.get(self.name)

    @api_call
    def add(self, start_range: str, end_range: str, cidr: str, timeout: int = 60) -> None:
        """
        Add IP Pool to NSX. It is supposed to work with Overlay ONLY.

        :param start_range: First IP address in pool.
        :param end_range: Last IP address in pool.
        :param cidr: CIDR.
        :param timeout: Maximum time operation can take to resolve.

        :returns: Added IP pool ID.
        """
        if self.content is not None:
            return

        pool_range = IpPoolRange(start=start_range, end=end_range)
        address_subnet = IpAddressPoolStaticSubnet(allocation_ranges=[pool_range], cidr=cidr, id=self.name)
        child_subnet = ChildIpAddressPoolSubnet(
            ip_address_pool_subnet=address_subnet,
            resource_type=ChildIpAddressPoolSubnet.__name__,
        )

        ip_pool = IpAddressPool(
            display_name=self.name,
            children=[child_subnet],
            description=f"IP Pool {self.name}",
            resource_type=IpAddressPool.__name__,
            id=self.name,
        )
        payload = ChildIpAddressPool(ip_address_pool=ip_pool, resource_type=ChildIpAddressPool.__name__)
        infra_payload = Infra(resource_type=Infra.__name__, children=[payload])
        t_end = timeout + time()
        while time() < t_end:
            try:
                self._connection.api.policy.Infra.patch(infra_payload)
                return
            except InvalidRequest as e:
                # "proper" way to get exception data. No comment.
                if e.to_dict().get("data").get("error_code") == 500045:
                    # Pool is being removed, and not all nodes were notified. Add will retry
                    sleep(10)
                    continue
                raise e

    @api_call
    def delete(self, timeout: int = 60) -> None:
        """
        Delete IP pool.

        :param timeout: Maximum time operation can take to resolve. If None resolution is skipped.
        """
        if self.content is not None:
            payload = ChildIpAddressPool(
                ip_address_pool=self.content,
                resource_type=ChildIpAddressPool.__name__,
                marked_for_delete=True,
            )
            infra_payload = Infra(resource_type=Infra.__name__, children=[payload])
            self._connection.api.policy.Infra.patch(infra_payload)
            t_end = timeout + time()
            while time() < t_end:
                if self.content is None:
                    return
                sleep(10)
            raise NsxResourceRemoveError(f"Timeout on remove Ip Pool {self.name}")
