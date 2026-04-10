"""
Simple pub/sub event system for cache invalidation.

When new data arrives from ETL (e.g., updated GPA for a course),
publish an event so that cached recommendations and course data
are invalidated across all layers.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventType(Enum):
    COURSE_UPDATED = "course_updated"
    PROFESSOR_UPDATED = "professor_updated"
    GRADES_UPDATED = "grades_updated"
    REVIEWS_UPDATED = "reviews_updated"
    SECTIONS_UPDATED = "sections_updated"
    REQUIREMENTS_UPDATED = "requirements_updated"
    CACHE_INVALIDATE = "cache_invalidate"


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # e.g., "planetterp_etl", "umdio_etl"


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """In-process async event bus for pub/sub communication.

    Subscribers register handlers for specific event types.
    Publishers fire events which are dispatched to all matching handlers.
    """

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers.

        Handlers run concurrently. Failures in one handler don't
        affect others (fire-and-forget with error logging).
        """
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return

        tasks = [self._safe_call(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler failed for {event.type.value}: {e}")


# Global event bus instance
event_bus = EventBus()
