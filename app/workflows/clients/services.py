import os
from app.workflows.clients.base import ServiceClient


class InventoryClient(ServiceClient):
    """HTTP client for Inventory service."""
    service_name = "inventory"
    service_url = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8001")


class CRMClient(ServiceClient):
    """HTTP client for CRM service."""
    service_name = "crm"
    service_url = os.getenv("CRM_SERVICE_URL", "http://localhost:8002")


class NotificationClient(ServiceClient):
    """HTTP client for Notification service."""
    service_name = "notification"
    service_url = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8003")

