"""
Status indicator utilities for fetching and calculating system health.
"""
import asyncio
from typing import Dict, List, Literal, Optional, TypedDict
import httpx
from datetime import datetime, timezone

from constants import (
    uptime_kuma_base_url,
    uptime_kuma_slug,
    status_page_url,
    STATUS_GROUP_CRITICALITY,
    UPTIME_KUMA_STATUS_UP,
    is_status_indicator_enabled,
)


# =============================================================================
# Type Definitions
# =============================================================================

class MonitorInfo(TypedDict):
    id: int
    name: str


class GroupInfo(TypedDict):
    id: int
    name: str
    weight: int
    monitorList: List[MonitorInfo]


class HeartbeatEntry(TypedDict):
    status: int
    time: str
    ping: Optional[int]


StatusLevel = Literal["operational", "degraded", "down", "unknown"]


class StatusResult(TypedDict):
    status: StatusLevel
    timestamp: str
    status_page_url: Optional[str]


# =============================================================================
# Public API
# =============================================================================

async def get_status() -> StatusResult:
    """
    Fetch system status from Uptime Kuma.

    Returns:
        StatusResult with overall status, timestamp, and status page URL.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if not is_status_indicator_enabled():
        return {
            "status": "unknown",
            "timestamp": timestamp,
            "status_page_url": status_page_url,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch both endpoints in parallel
            config_url = f"{uptime_kuma_base_url}/api/status-page/{uptime_kuma_slug}"
            heartbeat_url = f"{uptime_kuma_base_url}/api/status-page/heartbeat/{uptime_kuma_slug}"

            config_response, heartbeat_response = await asyncio.gather(
                client.get(config_url),
                client.get(heartbeat_url),
            )

            if config_response.status_code != 200 or heartbeat_response.status_code != 200:
                return {
                    "status": "unknown",
                    "timestamp": timestamp,
                    "status_page_url": status_page_url,
                }

            config_data = config_response.json()
            heartbeat_data = heartbeat_response.json()

            status = _calculate_overall_status(
                groups=config_data.get("publicGroupList", []),
                heartbeats=heartbeat_data.get("heartbeatList", {}),
            )

            return {
                "status": status,
                "timestamp": timestamp,
                "status_page_url": status_page_url,
            }

    except Exception:
        # Fail-safe: assume down if we can't reach the monitoring service
        return {
            "status": "down",
            "timestamp": timestamp,
            "status_page_url": status_page_url,
        }


# =============================================================================
# Internal Functions
# =============================================================================

def _calculate_overall_status(
    groups: List[GroupInfo],
    heartbeats: Dict[str, List[HeartbeatEntry]],
) -> StatusLevel:
    """
    Calculate overall status based on group criticality and monitor health.

    Rules:
    - Any essential group monitor down -> "down"
    - Any non-essential group monitor down -> "degraded"
    - All monitors up -> "operational"
    - No data -> "unknown"
    """
    if not groups or not heartbeats:
        return "unknown"

    has_essential_down = False
    has_non_essential_down = False

    for group in groups:
        group_name = group.get("name", "")
        # Unmapped groups default to essential (fail-safe)
        criticality = STATUS_GROUP_CRITICALITY.get(group_name, "essential")

        for monitor in group.get("monitorList", []):
            monitor_id = str(monitor.get("id"))
            monitor_heartbeats = heartbeats.get(monitor_id, [])

            if not monitor_heartbeats:
                # No heartbeat data - treat as unknown/potentially down
                if criticality == "essential":
                    has_essential_down = True
                else:
                    has_non_essential_down = True
                continue

            # Check latest heartbeat status (last element is most recent)
            latest_status = monitor_heartbeats[-1].get("status")
            if latest_status != UPTIME_KUMA_STATUS_UP:
                if criticality == "essential":
                    has_essential_down = True
                else:
                    has_non_essential_down = True

    if has_essential_down:
        return "down"
    if has_non_essential_down:
        return "degraded"
    return "operational"
