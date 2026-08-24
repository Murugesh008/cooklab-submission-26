"""Service clients for Inventory, CRM, and Notification services."""

from app.workflows.clients.base import ServiceClient


class InventoryClient(ServiceClient):
    """HTTP client for Inventory service."""
    service_name = "inventory"
    # Local development: all services run on same app (localhost:8000)
    # Production: set via environment variable or config
    service_url = "http://localhost:8000"


class CRMClient(ServiceClient):
    """HTTP client for CRM service."""
    service_name = "crm"
    # Local development: all services run on same app (localhost:8000)
    # Production: set via environment variable or config
    service_url = "http://localhost:8000"


class NotificationClient(ServiceClient):
    """HTTP client for Notification service."""
    service_name = "notification"
    # Local development: all services run on same app (localhost:8000)
    # Production: set via environment variable or config
    service_url = "http://localhost:8000"
