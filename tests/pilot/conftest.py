from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _stop_marketplace_stubs():
    """Undo patchers left running by tests/pilot/marketplace_registry.publish."""
    yield
    mock.patch.stopall()
