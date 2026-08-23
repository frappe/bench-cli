from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pilot.config import RedisConfig
from pilot.exceptions import BenchError
from pilot.managers.redis import RedisManager


def test_verify_installed_passes_when_redis_is_available() -> None:
    manager = RedisManager(RedisConfig(), MagicMock())

    with patch.object(manager, "is_installed", return_value=True):
        manager.verify_installed()


def test_verify_installed_raises_actionable_error_when_redis_is_missing() -> None:
    manager = RedisManager(RedisConfig(), MagicMock())

    with (
        patch.object(manager, "is_installed", return_value=False),
        pytest.raises(BenchError, match="Redis is not installed") as exc,
    ):
        manager.verify_installed()

    message = str(exc.value)
    assert "install.sh" in message
    assert "Redis/Valkey" in message


def test_verify_installed_never_attempts_package_installation() -> None:
    manager = RedisManager(RedisConfig(), MagicMock())

    with (
        patch.object(manager, "is_installed", return_value=False),
        patch("pilot.managers.redis.get_package_manager") as get_package_manager,
        pytest.raises(BenchError),
    ):
        manager.verify_installed()

    get_package_manager.assert_not_called()
