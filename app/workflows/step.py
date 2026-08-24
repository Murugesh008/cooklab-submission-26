from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel


class BackoffStrategy(str, Enum):
    """Retry backoff strategies."""
    LINEAR = "LINEAR"
    EXPONENTIAL = "EXPONENTIAL"
    FIXED = "FIXED"


@dataclass
class RetryPolicy:
    """
    Configuration for step retry behavior.
    
    This is a structural boundary - retry logic is isolated here and not
    scattered through orchestration or business code.
    """
    max_attempts: int = 1
    backoff_strategy: BackoffStrategy = BackoffStrategy.FIXED
    backoff_seconds: int = 5  # for FIXED; used as base for EXPONENTIAL/LINEAR
    max_backoff_seconds: int = 300  # cap for exponential backoff


@dataclass
class StepDefinition:
    """
    Describes a single step in the workflow pipeline.
    
    The orchestrator executes steps in order, transforming data between them
    and handling failures according to the retry policy.
    """
    name: str  # e.g., "inventory", "crm", "notification"
    service_endpoint: str  # e.g., "http://localhost:8001/api/inventory/process"
    retry_policy: RetryPolicy = None
    # Callable to transform input_payload → request_payload
    transform_request: Optional[Callable[[dict], dict]] = None
    # Callable to transform response_payload → next_input_payload
    transform_response: Optional[Callable[[dict], dict]] = None
    # Expected status code (default 200)
    expected_status: int = 200

    def __post_init__(self):
        if self.retry_policy is None:
            self.retry_policy = RetryPolicy()
        if self.transform_request is None:
            self.transform_request = lambda x: x  # identity
        if self.transform_response is None:
            self.transform_response = lambda x: x  # identity


class StepRequest(BaseModel):
    """
    Payload sent to each downstream service.
    
    Every service receives this structure, decoupling the service interface
    from the internal workflow payload structure.
    """
    workflow_id: int
    step_name: str
    attempt: int
    payload: dict


class StepResponse(BaseModel):
    """
    Expected response from each downstream service.
    
    Provides a consistent interface for the orchestrator to validate responses.
    """
    success: bool
    message: str = ""
    data: Optional[dict] = None  # The transformed result
