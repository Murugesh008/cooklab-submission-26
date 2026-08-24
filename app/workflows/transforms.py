"""
Transformation layer for workflow data mapping.

This module provides the boundary for transforming data between workflow
stages and service payloads. Keeps service integration details isolated
so changes to one service's format don't require changes throughout
the orchestration logic.
"""
from typing import Any, Callable, Dict


class Transformer:
    """
    Base transformer - can be subclassed for service-specific mappings
    or used with explicit transformation functions.
    """

    def transform_request(self, workflow_payload: dict) -> dict:
        """Transform workflow payload into service request payload."""
        return workflow_payload

    def transform_response(self, service_response: dict) -> dict:
        """Transform service response into next workflow payload."""
        return service_response


class IdentityTransformer(Transformer):
    """Transformer that passes data through unchanged."""
    pass


class CallableTransformer(Transformer):
    """Transformer using explicit transformation functions."""

    def __init__(
        self,
        request_fn: Callable[[dict], dict] = None,
        response_fn: Callable[[dict], dict] = None,
    ):
        self.request_fn = request_fn or (lambda x: x)
        self.response_fn = response_fn or (lambda x: x)

    def transform_request(self, workflow_payload: dict) -> dict:
        return self.request_fn(workflow_payload)

    def transform_response(self, service_response: dict) -> dict:
        return self.response_fn(service_response)


class TransformationRegistry:
    """
    Registry mapping step names to their transformers.
    
    Allows transformation configuration to be changed independently
    without modifying orchestration or business logic.
    """

    def __init__(self):
        self._transformers: Dict[str, Transformer] = {}

    def register(self, step_name: str, transformer: Transformer) -> None:
        """Register a transformer for a step."""
        self._transformers[step_name] = transformer

    def get_transformer(self, step_name: str) -> Transformer:
        """Retrieve transformer for a step; defaults to identity if not registered."""
        return self._transformers.get(step_name, IdentityTransformer())
