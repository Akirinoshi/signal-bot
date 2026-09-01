"""Outbound integrations the handlers talk to."""

from .tak_service import TakDeliveryError, TakService

__all__ = ["TakDeliveryError", "TakService"]