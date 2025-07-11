# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT


class TestDatastore:
    def test_repr(self, datastore):
        assert f"{datastore}" == "Datastore('PY-Datastore')"
