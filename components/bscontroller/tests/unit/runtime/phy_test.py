# Copyright 2026 Xiaomi Corporation
# SPDX-License-Identifier: Apache-2.0

import pytest

from bscontroller.runtime.phy import find_phy


def test_find_phy_uses_babblesim_output_path(monkeypatch, tmp_path):
    binary = tmp_path / 'build' / 'bin' / 'bs_2G4_phy_v1'
    binary.parent.mkdir(parents=True)
    binary.touch(mode=0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('BSIM_OUT_PATH', 'build')

    assert find_phy() == binary


def test_find_phy_accepts_explicit_build_override(monkeypatch, tmp_path):
    binary = tmp_path / 'bin' / 'bs_2G4_phy_v1'
    binary.parent.mkdir()
    binary.touch(mode=0o755)
    monkeypatch.setenv('BSIM_OUT_PATH', str(tmp_path / 'other-build'))

    assert find_phy(tmp_path) == binary


@pytest.mark.parametrize('value', [None, ''])
def test_find_phy_requires_configured_output(monkeypatch, value):
    if value is None:
        monkeypatch.delenv('BSIM_OUT_PATH', raising=False)
    else:
        monkeypatch.setenv('BSIM_OUT_PATH', value)

    with pytest.raises(ValueError, match='set BSIM_OUT_PATH'):
        find_phy()


@pytest.mark.parametrize('mode', [None, 0o644])
def test_find_phy_rejects_missing_or_nonexecutable_binary(monkeypatch, tmp_path, mode):
    binary = tmp_path / 'bin' / 'bs_2G4_phy_v1'
    if mode is not None:
        binary.parent.mkdir()
        binary.touch(mode=mode)
    monkeypatch.setenv('BSIM_OUT_PATH', str(tmp_path))

    with pytest.raises(ValueError, match='PHY executable missing'):
        find_phy()
