"""Shared test fixtures and tolerances."""

import pytest

from physbound.engines.constants import Q_, ureg

FLOAT_TOL = 1e-6  # for comparing exact constants
DB_TOL = 0.01  # 0.01 dB tolerance for RF calculations


@pytest.fixture
def unit_registry():
    return ureg


@pytest.fixture
def quantity():
    return Q_
