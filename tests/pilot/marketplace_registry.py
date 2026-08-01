"""Stand in for the on-disk registry cache, so tests can publish apps in memory."""

from unittest.mock import patch

from pilot.integrations.marketplace import Marketplace


def publish(entries: list[dict]) -> None:
    """Serve `entries` as the marketplace registry for the rest of the test. Each
    entry carries its releases inline here; the real registry splits them into
    apps/<name>.json. The `_stop_marketplace_stubs` fixture undoes this."""
    index = [{key: value for key, value in entry.items() if key != "releases"} for entry in entries]
    releases = {
        entry["name"]: Marketplace._newest_first(entry.get("releases") or []) for entry in entries
    }
    patch.object(Marketplace, "registry", staticmethod(lambda: index)).start()
    patch.object(Marketplace, "_load_registry", staticmethod(lambda: index)).start()
    patch.object(Marketplace, "releases", staticmethod(lambda name: releases.get(name, ()))).start()
