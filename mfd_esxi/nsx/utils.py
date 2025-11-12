# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX utilities."""
import logging

from urllib3.exceptions import ProtocolError
from requests.exceptions import ConnectionError as RequestsConnectionError
from http.client import RemoteDisconnected

from mfd_common_libs import add_logging_level, log_levels
from typing import Callable, Any
from time import sleep

from mfd_esxi.exceptions import NsxApiCallError
from com.vmware.vapi.std.errors_client import Error, Unauthorized, NotFound

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


def api_call(call: Callable) -> Callable:
    """
    Mark method as NSX API call. Provide simple and unified way of handling NSX-specific errors.

    :param call: Method to wrap.
    :return: Wrapped API call.
    """

    def inner_wrapper(*args, **kwargs) -> Any:
        try:
            return call(*args, **kwargs)
        except Unauthorized:
            try:
                # Support both instance and staticmethod usage
                conn = None
                for arg in args:
                    # class instance with _connection attribute
                    if hasattr(arg, "_connection"):
                        conn = arg._connection
                        break
                    # unnamed parameter with _connect_to_nsx method e.g. call(connection)
                    elif hasattr(arg, "_connect_to_nsx"):
                        conn = arg
                        break
                if conn is None:
                    conn = kwargs.get("connection", None)
                if conn is None:
                    raise NsxApiCallError(
                        "Unable to locate connection: "
                        "expected an instance with _connection attribute in args or a connection kwarg."
                    )
                conn._connect_to_nsx()
                return call(*args, **kwargs)
            except Error as e:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Calling {call.__name__} from {call.__module__} failed with:\n {e.to_json()}",
                )
                raise NsxApiCallError()
        except (RequestsConnectionError, ProtocolError, RemoteDisconnected):
            sleep_between_tries = 2
            num_of_retries = 2
            for i in range(1, num_of_retries + 1):
                try:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"Connection error detected, waiting {sleep_between_tries} seconds and "
                            f"trying again ({i}/{num_of_retries}).",
                    )
                    sleep(sleep_between_tries)
                    return call(*args, **kwargs)
                except (RequestsConnectionError, ProtocolError, RemoteDisconnected):
                    continue
            raise NsxApiCallError()
        except NotFound:
            raise
        except Error as e:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Calling {call.__name__} from {call.__module__} failed with:\n {e.to_json()}",
            )
            raise NsxApiCallError()

    return inner_wrapper
