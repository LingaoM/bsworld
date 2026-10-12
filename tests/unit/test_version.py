# Copyright 2026 Xiaomi Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tests for package version discovery."""
from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path

import bsworld


def test_version_matches_installed_distribution() -> None:
    assert bsworld.__version__ == importlib.metadata.version("bsworld")


def test_version_falls_back_without_distribution_metadata(monkeypatch) -> None:
    def missing_distribution(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing_distribution)
    package_init = Path(bsworld.__file__)
    spec = importlib.util.spec_from_file_location("bsworld_without_metadata", package_init)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert module.__version__ == "0+unknown"
