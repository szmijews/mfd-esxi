# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""NSX utilities."""
import logging

from mfd_common_libs import add_logging_level, log_levels
from typing import Callable, Any

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
                args[0]._connection._connect_to_nsx()
                return call(*args, **kwargs)
            except Error as e:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Calling {call.__name__} from {call.__module__} failed with:\n {e.to_json()}",
                )
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
