# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Various utilities."""

from typing import TypeVar, Iterable, Optional, Any

from mfd_esxi.vcenter.exceptions import VCenterResourceMissing

T = TypeVar("T")

MiB = 1024 * 1024


def get_obj_from_iter(iter_obj: Iterable[T], name: str, raise_if_missing: bool = True) -> Optional[T]:
    """
    Get object from iterable object by name.

    :param iter_obj: Iterable object.
    :param name: Name for the object.
    :param raise_if_missing: If true exception will be raised when object is not found.

    :return: Object.
    :raise VCenterResourceMissing: Exception when object was not found.
    """
    for obj in iter_obj:
        if obj.name == name:
            return obj
    iter_obj = list(iter_obj)
    if raise_if_missing:
        raise VCenterResourceMissing(f"{name} in:{iter_obj}")
    else:
        return None


def get_first_match_from_iter(
    iter_obj: Iterable[T], predicate: Any = lambda o: True, default: Optional[T] = None
) -> Optional[T]:
    """
    Get object from iterable object by predicate.

    :param iter_obj: Iterable object.
    :param predicate: Predicate applied to iterable object.
    :param default: Default value returned if no match will occur.

    :return: First predicate match from iterable object.
    """
    return next(filter(predicate, iter_obj), default)
