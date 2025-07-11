# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest

from mfd_esxi.vcenter.exceptions import VCenterResourceMissing
from mfd_esxi.vcenter.utils import get_obj_from_iter, get_first_match_from_iter


def test_get_obj_from_iter_match(vcenter_named_entities):
    match = get_obj_from_iter(vcenter_named_entities, "Named-2")
    assert match is not None
    assert match.name == "Named-2"


def test_get_obj_from_iter_safe_miss(vcenter_named_entities):
    match = get_obj_from_iter(vcenter_named_entities, "unNamed-2", raise_if_missing=False)
    assert match is None


def test_get_obj_from_iter_unsafe_miss(vcenter_named_entities):
    with pytest.raises(VCenterResourceMissing) as exc_info:
        get_obj_from_iter(vcenter_named_entities, "unNamed-2", raise_if_missing=True)
    assert f"{exc_info.value}" == "unNamed-2 in:[Named-1, Named-2, Named-3]"


def test_get_first_match_from_iter_match(vcenter_named_entities):
    match = get_first_match_from_iter(vcenter_named_entities)
    assert match.name == "Named-1"


def test_get_first_match_from_iter_predicate_match(vcenter_named_entities):
    match = get_first_match_from_iter(vcenter_named_entities, lambda o: o.name == "Named-3")
    assert match.name == "Named-3"


def test_get_first_match_from_iter_miss(vcenter_named_entities):
    match = get_first_match_from_iter(vcenter_named_entities, lambda o: False)
    assert match is None


def test_get_first_match_from_iter_default_miss(vcenter_named_entities):
    match = get_first_match_from_iter(vcenter_named_entities, lambda o: False, "Missed")
    assert match == "Missed"
