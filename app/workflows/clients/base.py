"""
Base HTTP client for inter-service communication.

Service clients inherit from this to handle HTTP request/response details,
keeping orchestration logic clean and decoupled from transport specifics.
"""
from typing import Any, Optional

import requests

from app.workflows.step import StepRequest, StepResponse


class ServiceClient:
    """
    Base HTTP client for communicating with downstream services.
    
    Subclasses override service_name and service_url to target specific service endpoints.
    """

    service_name: str = "unknown"
    service_url: str = "http://localhost:8000"  # Override in subclass

    def __call__(self, request: StepRequest) -> StepResponse:
        """Execute the service call. Override in subclass for specific logic."""
        return self.call(request)

    def call(self, request: StepRequest) -> StepResponse:
        """
        Call the downstream service.
        
        Base implementation makes HTTP POST to service_url with the step request.
        Routes to /{service_name}/process endpoint.
        Override for custom transport or behavior.
        """
        try:
            url = f"{self.service_url}/api/{self.service_name}/process"
            response = requests.post(
                url,
                json=request.model_dump(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return StepResponse(**data)
        except requests.RequestException as e:
            return StepResponse(
                success=False, message=f"{self.service_name} call failed: {str(e)}"
            )
        except Exception as e:
            return StepResponse(
                success=False, message=f"{self.service_name} unexpected error: {str(e)}"
            )
