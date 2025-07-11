# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for exceptions."""
import subprocess


class ESXiVersionException(Exception):
    """Unable to recognize version."""


class ESXiNotFound(Exception):
    """Unable to find the name provided."""


class ESXiNotSupported(Exception):
    """Not supported feature selected."""


class ESXiNameException(Exception):
    """Wrong name."""


class ESXiWrongParameter(Exception):
    """Wrong parameter supplied."""


class ESXiRuntimeError(Exception):
    """Error during execution."""


class ESXiVMCopyTimeout(Exception):
    """Timeout copying VM disk."""


class ESXiVMNotRun(Exception):
    """VM is not running."""


class ESXiVFUnavailable(Exception):
    """No VF available."""


class ESXiAPISocketError(Exception):
    """Unable to communicate with API."""


class ESXiAPIInvalidLogin(Exception):
    """Wrong credentials."""


class UninitializedNsxConnection(Exception):
    """Connection to NSX is not initialized."""


class UnsupportedNsxEntity(Exception):
    """NSX entity is not supported."""


class MissingNsxEntity(Exception):
    """NSX entity is missing."""


class NsxApiCallError(Exception):
    """NSX api call failed."""


class NsxResourceSetupError(Exception):
    """NSX resource setup error."""


class NsxResourcePartialSuccessSetupError(Exception):
    """NSX resource partial success setup error."""


class NsxResourceRemoveError(Exception):
    """NSX resource remove error."""


class VswitchError(subprocess.CalledProcessError, Exception):
    """Vswitch error."""
