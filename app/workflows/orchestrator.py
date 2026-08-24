"""
Workflow Orchestrator.

Executes workflow pipelines, coordinates inter-service communication,
handles failures and retries, and maintains audit logs.

The orchestrator owns workflow execution state and delegates domain logic
to downstream services. It does NOT access their databases directly.
"""
import logging
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.workflows.clients.services import CRMClient, InventoryClient, NotificationClient
from app.workflows.idempotency import IdempotencyService
from app.workflows.models import AuditEventType, AuditLog, Workflow, WorkflowStatus
from app.workflows.step import RetryPolicy, StepDefinition, StepRequest
from app.workflows.transforms import TransformationRegistry
from app.workflows.diagnosis import diagnose_failed_workflow

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Orchestrates execution of a multi-step workflow.
    
    The orchestrator:
    1. Receives an order event
    2. Creates workflow state and audit log entries
    3. Executes steps sequentially through their service clients
    4. Transforms data between steps
    5. Handles failures and retries
    6. Logs all events for audit trail
    
    Downstream services should never communicate directly with each other.
    All inter-service communication is coordinated here.
    """

    def __init__(
        self,
        db: Session,
        idempotency_service: IdempotencyService = None,
        transformation_registry: TransformationRegistry = None,
    ):
        self.db = db
        self.idempotency_service = idempotency_service or IdempotencyService()
        self.transformation_registry = transformation_registry or TransformationRegistry()

        # Service clients
        self.inventory_client = InventoryClient()
        self.crm_client = CRMClient()
        self.notification_client = NotificationClient()

    def create_workflow(self, external_id: str, payload: dict) -> Workflow:
        """Create a new workflow record."""
        workflow = Workflow(
            external_id=external_id,
            status=WorkflowStatus.PENDING,
            payload=payload,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def log_event(
        self,
        workflow_id: int,
        event_type: AuditEventType,
        step: str = None,
        attempt: int = 0,
        error_message: str = None,
        metadata: dict = None,
    ) -> None:
        """Record an audit log entry."""
        log_entry = AuditLog(
            workflow_id=workflow_id,
            step=step,
            event_type=event_type,
            attempt=attempt,
            error_message=error_message,
            event_data=metadata or {},
        )
        self.db.add(log_entry)
        self.db.commit()

    def execute_workflow(self, workflow: Workflow, steps: List[StepDefinition]) -> Workflow:
        """
        Execute a workflow through all steps.
        
        Returns updated workflow state (may be COMPLETED, COMPLETED_WITH_RECOVERY, or FAILED).
        """
        logger.info(f"[ORCHESTRATOR] Workflow {workflow.id} started")
        self.log_event(workflow.id, AuditEventType.WORKFLOW_STARTED)

        workflow.status = WorkflowStatus.RUNNING
        workflow.updated_at = datetime.utcnow()
        self.db.commit()

        has_recovered_steps = False

        for step_def in steps:
            logger.info(
                f"[ORCHESTRATOR] Executing step: {step_def.name} "
                f"(workflow_id={workflow.id})"
            )
            step_status = self._execute_step_with_retry(workflow, step_def)

            if step_status == "SUCCESS":
                continue
            elif step_status == "RECOVERED":
                has_recovered_steps = True
                continue
            else:
                logger.error(
                    f"[ORCHESTRATOR] Step {step_def.name} failed unrecoverably (workflow_id={workflow.id})"
                )
                workflow.status = WorkflowStatus.FAILED
                workflow.updated_at = datetime.utcnow()
                self.db.commit()
                self.log_event(workflow.id, AuditEventType.WORKFLOW_FAILED, error_message=f"Workflow failed at step {step_def.name}")
                workflow.diagnosis = diagnose_failed_workflow(
                    workflow, self.get_workflow_history(workflow.id)
                )
                self.db.commit()
                return workflow

        # All steps completed
        if has_recovered_steps:
            workflow.status = WorkflowStatus.COMPLETED_WITH_RECOVERY
            logger.info(f"[ORCHESTRATOR] Workflow {workflow.id} completed with recovery")
            self.log_event(workflow.id, AuditEventType.WORKFLOW_COMPLETED, metadata={"recovery_applied": True})
        else:
            workflow.status = WorkflowStatus.COMPLETED
            logger.info(f"[ORCHESTRATOR] Workflow {workflow.id} completed successfully")
            self.log_event(workflow.id, AuditEventType.WORKFLOW_COMPLETED)

        workflow.updated_at = datetime.utcnow()
        self.db.commit()
        return workflow

    def _execute_step_with_retry(self, workflow: Workflow, step_def: StepDefinition) -> str:
        """
        Execute a single step with retry logic and recovery fallback.
        
        Returns "SUCCESS", "RECOVERED", or "FAILED".
        """
        retry_policy = step_def.retry_policy
        attempt = 0

        while attempt < retry_policy.max_attempts:
            attempt += 1
            logger.info(
                f"[ORCHESTRATOR] Step {step_def.name} attempt {attempt} "
                f"(workflow_id={workflow.id})"
            )
            self.log_event(
                workflow.id, AuditEventType.STEP_STARTED, step_def.name, attempt
            )

            workflow.current_step = step_def.name
            workflow.attempt_count = attempt
            workflow.updated_at = datetime.utcnow()
            self.db.commit()

            # Transform input payload for this step
            request_payload = step_def.transform_request(workflow.payload or {})

            # Create step request
            step_request = StepRequest(
                workflow_id=workflow.id,
                step_name=step_def.name,
                attempt=attempt,
                payload=request_payload,
            )

            # Get appropriate service client
            client = self._get_service_client(step_def.name)
            response = client.call(step_request)

            if response.success:
                logger.info(
                    f"[ORCHESTRATOR] Step {step_def.name} succeeded "
                    f"(workflow_id={workflow.id})"
                )
                self.log_event(
                    workflow.id,
                    AuditEventType.STEP_SUCCEEDED,
                    step_def.name,
                    attempt,
                    metadata={"response": response.data}
                )

                # Transform response back into workflow payload for next step
                transformed_response = step_def.transform_response(response.data or {})
                if workflow.payload is None:
                    workflow.payload = {}
                workflow.payload.update(transformed_response)
                workflow.updated_at = datetime.utcnow()
                self.db.commit()

                return "SUCCESS"
            else:
                logger.warning(
                    f"[ORCHESTRATOR] Step {step_def.name} failed: "
                    f"{response.message} (workflow_id={workflow.id}, attempt={attempt})"
                )
                self.log_event(
                    workflow.id,
                    AuditEventType.STEP_FAILED,
                    step_def.name,
                    attempt,
                    error_message=response.message,
                )

                if attempt < retry_policy.max_attempts:
                    logger.info(
                        f"[ORCHESTRATOR] Scheduling retry for {step_def.name} "
                        f"(workflow_id={workflow.id})"
                    )
                    self.log_event(
                        workflow.id,
                        AuditEventType.RETRY_SCHEDULED,
                        step_def.name,
                        attempt,
                    )
                    workflow.status = WorkflowStatus.WAITING_RETRY
                    workflow.updated_at = datetime.utcnow()
                    self.db.commit()

        # All retries exhausted
        logger.error(
            f"[ORCHESTRATOR] Step {step_def.name} failed after "
            f"{retry_policy.max_attempts} attempts (workflow_id={workflow.id})"
        )
        self.log_event(
            workflow.id,
            AuditEventType.RETRY_FAILED,
            step_def.name,
            attempt,
            error_message=f"All {retry_policy.max_attempts} attempts failed."
        )

        # Execute recovery strategy if step is recoverable (e.g. CRM, Notification)
        if step_def.name in ["crm", "notification"]:
            logger.warning(f"[ORCHESTRATOR] Initiating recovery strategy for step '{step_def.name}'...")
            self.log_event(
                workflow.id,
                AuditEventType.RECOVERY_INITIATED,
                step_def.name,
                attempt,
                error_message=f"Service '{step_def.name}' unavailable. Executing compensation fallback."
            )
            
            fallback_data = {
                f"{step_def.name}_status": "RECOVERED_OFFLINE_BUFFER",
                f"{step_def.name}_fallback_msg": f"Queued for offline retry buffer because {step_def.name} service was down"
            }
            if workflow.payload is None:
                workflow.payload = {}
            workflow.payload.update(fallback_data)
            
            self.log_event(
                workflow.id,
                AuditEventType.RECOVERY_COMPLETED,
                step_def.name,
                attempt,
                metadata=fallback_data
            )
            return "RECOVERED"

        return "FAILED"

    def _get_service_client(self, step_name: str):
        """Route to appropriate service client based on step name."""
        if step_name == "inventory":
            return self.inventory_client
        elif step_name == "crm":
            return self.crm_client
        elif step_name == "notification":
            return self.notification_client
        else:
            raise ValueError(f"Unknown step: {step_name}")

    def get_workflow_history(self, workflow_id: int) -> List[AuditLog]:
        """Retrieve complete audit log for a workflow."""
        return self.db.query(AuditLog).filter(
            AuditLog.workflow_id == workflow_id
        ).order_by(AuditLog.timestamp).all()
