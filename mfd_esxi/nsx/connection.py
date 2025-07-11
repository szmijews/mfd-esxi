# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Connection to NSX."""
import requests
from packaging.version import Version, parse
from com.vmware import nsx_policy_client, nsx_client

from vmware.vapi.bindings.stub import ApiClient, StubConfiguration
from vmware.vapi.lib import connect
from vmware.vapi.stdlib.client.factories import StubConfigurationFactory

from ..exceptions import UninitializedNsxConnection


class ApiClientWrapper:
    """Wrapper that make NSX SDK just a little more readable."""

    def __init__(self, stub_config: StubConfiguration):
        """
        Initialize instance.

        :param stub_config: NSX API stub configuration.
        """
        self._stub_config = stub_config
        self._infra_client = None
        self._management_client = None

    def initialize(self) -> None:
        """Initialize clients."""
        self._infra_client = ApiClient(nsx_policy_client.StubFactory(self._stub_config))
        self._management_client = ApiClient(nsx_client.StubFactory(self._stub_config))

    @property
    def policy(self) -> ApiClient:
        """Get wrapped infra client."""
        return self._infra_client

    @property
    def management(self) -> ApiClient:
        """Get wrapped management client."""
        return self._management_client


class NsxConnection:
    """Connection to NSX."""

    def __init__(self, address: str, username: str, password: str, tcp_port: int = 443):
        """
        Initialize instance.

        :param address:Address of NSX.
        :param username: Name of user.
        :param password: Password for user.
        :param tcp_port: Port for https connection to NSX.
        """
        self._address = address
        self._username = username
        self._password = password
        self._tcp_port = tcp_port
        self._api = None
        self._version = None

    def __repr__(self):
        """Get string representation."""
        return f"{self.__class__.__name__}('{self._address}')"

    @property
    def api(self) -> ApiClientWrapper:
        """
        Get connection to NSX.

        :return: Connection to NSX.
        """
        if self._api is None:
            raise UninitializedNsxConnection()
        return self._api

    @property
    def version(self) -> Version:
        """Get NSX version."""
        return parse(self._version)

    def _connect_to_nsx(self) -> None:
        session = requests.session()
        session.verify = False
        session.trust_env = False
        requests.packages.urllib3.disable_warnings()

        nsx_url = f"https://{self._address}:{self._tcp_port}"
        resp = session.post(
            nsx_url + "/api/session/create",
            data={"j_username": self._username, "j_password": self._password},
        )
        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()

        session.headers["Cookie"] = resp.headers.get("Set-Cookie")
        session.headers["X-XSRF-TOKEN"] = resp.headers.get("X-XSRF-TOKEN")

        connector = connect.get_requests_connector(session=session, msg_protocol="rest", url=nsx_url)
        stub_config = StubConfigurationFactory.new_runtime_configuration(connector)
        self._api = ApiClientWrapper(stub_config)
        self._api.initialize()
        self._version = self._api.management.node.Version.get().node_version

    @classmethod
    def with_connection(
        cls: "NsxConnection",
        address: str,
        username: str,
        password: str,
        tcp_port: int = 443,
    ) -> "NsxConnection":
        """
        Initialize connection to NSX using stub factory.

        :param address:Address of NSX.
        :param username: Name of user.
        :param password: Password for user.
        :param tcp_port: Port for https connection to NSX.
        """
        instance = cls(address, username, password, tcp_port)
        instance._connect_to_nsx()
        return instance
