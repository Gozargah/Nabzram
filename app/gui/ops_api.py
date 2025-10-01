"""Operations API - GUI adapter layer that delegates to ops modules."""

import logging
from typing import Any

from app.ops import appearance, logs, servers, settings, subscriptions, system, updates


class OperationsApi:
    """Full in-process Operations API."""

    def __init__(self, window) -> None:
        self.window = window
        self.logger = logging.getLogger(__name__)

    # ──────────────────────────────
    # Settings
    # ──────────────────────────────
    def get_settings(self) -> dict[str, Any]:
        return settings.get_settings()

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return settings.update_settings(payload)

    # ──────────────────────────────
    # Appearance
    # ──────────────────────────────
    def get_appearance(self) -> dict[str, Any]:
        return appearance.get_appearance()

    def update_appearance(self, payload: dict[str, Any]) -> dict[str, Any]:
        return appearance.update_appearance(payload)

    # ──────────────────────────────
    # Subscriptions
    # ──────────────────────────────
    def list_subscriptions(self) -> list[dict[str, Any]]:
        return subscriptions.list_subscriptions()

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return subscriptions.get_subscription(subscription_id)

    def create_subscription(self, payload: dict[str, Any]) -> dict[str, Any]:
        return subscriptions.create_subscription(payload)

    def update_subscription(
        self,
        subscription_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return subscriptions.update_subscription(subscription_id, payload)

    def delete_subscription(self, subscription_id: str) -> dict[str, Any]:
        return subscriptions.delete_subscription(subscription_id)

    def refresh_subscription_servers(self, subscription_id: str) -> dict[str, Any]:
        return subscriptions.refresh_subscription_servers(subscription_id)

    # ──────────────────────────────
    # Server management
    # ──────────────────────────────
    def start_server(self, subscription_id: str, server_id: str) -> dict[str, Any]:
        return servers.start_server(subscription_id, server_id)

    def stop_server(self) -> dict[str, Any]:
        return servers.stop_server()

    def get_server_status(self) -> dict[str, Any]:
        return servers.get_server_status()

    def test_subscription_servers(self, subscription_id: str) -> dict[str, Any]:
        return servers.test_subscription_servers(subscription_id)

    # ──────────────────────────────
    # System
    # ──────────────────────────────
    def get_xray_status(self) -> dict[str, Any]:
        return system.get_xray_status()

    # ──────────────────────────────
    # Updates
    # ──────────────────────────────
    def get_xray_version_info(self) -> dict[str, Any]:
        return updates.get_xray_version_info()

    def update_xray(self, payload: dict[str, Any]) -> dict[str, Any]:
        return updates.update_xray(payload)

    def update_geodata(self) -> dict[str, Any]:
        return updates.update_geodata()

    # ──────────────────────────────
    # Logs
    # ──────────────────────────────
    def get_log_snapshot(self, limit: int = 200) -> dict[str, Any]:
        return logs.get_log_snapshot(limit)

    def get_log_stream_batch(
        self,
        since_ms: int | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        return logs.get_log_stream_batch(since_ms, limit)
