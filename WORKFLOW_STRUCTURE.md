# Workflow Orchestration Structure - Documentation

This document describes the **structural foundation** for the Fault-Tolerant Multi-System Workflow Orchestration system built on the existing FastAPI boilerplate.

## Architecture Overview

The system implements a **pipeline-oriented workflow** where an Order triggers a multi-step orchestration process:

```
Order → Orchestrator → Inventory → CRM → Notification
```

### Key Principles

1. **Separation of Concerns**: Each service owns its own database, API, and business logic
2. **No Direct Service Communication**: All inter-service communication flows through the orchestrator
3. **Audit Trail**: Complete event history for all workflow executions
4. **Retry Capability**: Configurable retry policies for failure recovery
5. **Idempotency Ready**: Structure for safe replay of operations

---

## Directory Structure

```
app/
├── workflows/                    # Orchestration engine
│   ├── models.py                # Workflow & AuditLog models
│   ├── orchestrator.py          # Workflow execution logic
│   ├── step.py                  # Step abstraction & definitions
│   ├── retry.py                 # [Reserved] Retry policy model
│   ├── idempotency.py           # [Reserved] Idempotency service
│   ├── transforms.py            # Data transformation layer
│   └── clients/
│       ├── base.py              # Base HTTP client
│       └── services.py          # Inventory, CRM, Notification clients
│
├── services/                     # Independent business services
│   ├── inventory/
│   │   ├── models.py            # InventoryItem
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── service.py           # Business logic
│   │   └── routers.py           # API endpoints
│   ├── crm/
│   │   ├── models.py            # CRMRecord
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── service.py           # Business logic
│   │   └── routers.py           # API endpoints
│   └── notification/
│       ├── models.py            # Notification
│       ├── schemas.py           # Pydantic schemas
│       ├── service.py           # Business logic
│       └── routers.py           # API endpoints
│
├── order/                        # Order entry point
│   ├── models.py                # Order model
│   ├── schemas.py               # Pydantic schemas
│   ├── service.py               # Order service & workflow triggering
│   └── routers.py               # API endpoints
│
├── static/                       # Frontend
│   ├── index.html               # Dashboard
│   ├── style.css                # Styling
│   └── app.js                   # JavaScript interaction
│
├── core/                         # Existing configuration
│   ├── config.py                # Environment settings
│   ├── security.py              # JWT authentication
│   └── deps.py                  # Dependency injection
│
├── db/                           # Database configuration
│   └── database.py              # SQLAlchemy setup
│
├── models/                       # Existing user model
│   └── user.py
│
├── routers/                      # Existing routers
│   ├── auth.py
│   └── health.py
│
└── main.py                       # Application entry point
```

---

## Core Components

### 1. Workflow Model (`workflows/models.py`)

**Workflow** — Represents mutable execution state:
- `id` — Unique workflow ID
- `external_id` — Reference to order ID
- `status` — PENDING / RUNNING / WAITING_RETRY / COMPLETED / FAILED / DEAD_LETTER
- `current_step` — Which step is executing
- `payload` — Current data being processed
- `attempt_count` — Retry counter
- `created_at`, `updated_at`

**AuditLog** — Immutable event history:
- `workflow_id` — Reference to workflow
- `event_type` — WORKFLOW_STARTED, STEP_STARTED, STEP_SUCCEEDED, STEP_FAILED, RETRY_SCHEDULED, etc.
- `step` — Step name (e.g., "inventory")
- `timestamp` — When event occurred
- `attempt` — Which retry attempt
- `error_message` — Failure details
- `event_data` — Arbitrary metadata

**Separation**: Workflow state is mutable and current. AuditLog is immutable and historical. This distinction is critical for understanding what happened vs. what's currently happening.

### 2. Step Abstraction (`workflows/step.py`)

**StepDefinition** — Describes a workflow step:
```python
StepDefinition(
    name="inventory",
    service_endpoint="http://localhost:8000/api/inventory/process",
    retry_policy=RetryPolicy(max_attempts=2),
    transform_request=lambda p: extract_inventory_fields(p),
    transform_response=lambda r: update_payload(r),
)
```

**StepRequest/StepResponse** — Standardized inter-service communication:
- Services receive `StepRequest` with workflow context
- Services return `StepResponse` with success flag and result

This decouples service contracts from internal workflow payload structure.

### 3. Orchestrator (`workflows/orchestrator.py`)

The **WorkflowOrchestrator** owns the execution engine:

```python
orchestrator = WorkflowOrchestrator(db)
workflow = orchestrator.create_workflow(external_id="ORD-123", payload={...})
workflow = orchestrator.execute_workflow(workflow, [inventory_step, crm_step, notification_step])
```

**Responsibilities**:
- Create workflow state in database
- Execute steps sequentially
- Transform data between steps
- Handle failures and log events
- Coordinate retries
- Maintain audit trail

**Key Design**:
- Steps are executed in order
- If any step fails after retries, workflow fails
- Each step is independent — no direct DB access to other services
- All communication through HTTP service clients

### 4. Service Clients (`workflows/clients/`)

**ServiceClient** — Base HTTP client for inter-service calls:
```python
class InventoryClient(ServiceClient):
    service_name = "inventory"
    service_url = "http://localhost:8000"
```

The orchestrator uses these clients to call downstream services. This isolates HTTP details from orchestration logic.

### 5. Transformation Layer (`workflows/transforms.py`)

**Transformer** — Isolates input/output mapping for each step:
```python
transformer = CallableTransformer(
    request_fn=lambda p: {"sku": p["sku"], "quantity": p["quantity"]},
    response_fn=lambda r: {"inventory_status": r["status"]}
)
```

Changes to one service's data format don't require changes throughout the orchestrator.

### 6. Retry Policy (`workflows/step.py`)

**RetryPolicy** — Configurable retry behavior:
```python
RetryPolicy(
    max_attempts=3,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    backoff_seconds=5,
    max_backoff_seconds=300
)
```

Currently a structural placeholder. The orchestrator checks `max_attempts` but doesn't yet implement backoff scheduling.

### 7. Idempotency (`workflows/idempotency.py`)

**IdempotencyService** — Manages safe replay:
```python
key = IdempotencyService.generate_key(workflow_id=1, step_name="inventory", attempt=1)
```

Structural boundary for future distributed idempotency. Services can cache results under these keys to detect and reject duplicate operations.

---

## Service Structure (Inventory / CRM / Notification)

Each downstream service follows the same pattern:

### Database Model
```python
class InventoryItem(Base):
    __tablename__ = "inventory_items"
    workflow_id: int       # Reference to workflow
    idempotency_key: str   # For replay detection
    # Domain-specific fields
    sku: str
    quantity_reserved: int
```

Each service has its **own SQLite database** (locally) or **separate Postgres schema** (in production).

### Service Class
```python
class InventoryService:
    def process_inventory_request(self, workflow_id, sku, quantity) -> dict:
        # Domain logic: reserve inventory, validate, etc.
        # Returns result dict
```

Business logic is isolated in the service class. It receives the workflow request and returns a result.

### API Endpoint
```python
@router.post("/process")
def process_inventory_step(request: StepRequest) -> StepResponse:
    # Parse StepRequest
    # Call InventoryService
    # Return StepResponse
```

The orchestrator calls this endpoint. The endpoint translates between the workflow protocol and domain logic.

---

## Order Service (`order/`)

**Entry Point** for workflow execution. When an order is created:

1. Order is saved to database
2. WorkflowOrchestrator.create_workflow() is called
3. Workflow steps (Inventory → CRM → Notification) are defined
4. WorkflowOrchestrator.execute_workflow() is called
5. Results are returned to the frontend

This is where the workflow "starts" — from an order creation request.

---

## Frontend (`static/`)

**Minimal vanilla HTML/CSS/JS dashboard**:
- Order creation form
- Real-time workflow status visualization  
- Execution log display
- Query/lookup for existing workflows

The frontend fetches workflow history from `/api/order/history/{order_id}` and renders the complete audit trail.

---

## API Endpoints

### Order Service
- `POST /api/order/create` — Create order & execute workflow
- `GET /api/order/status/{order_id}` — Get order + workflow status
- `GET /api/order/history/{order_id}` — Get complete audit trail

### Inventory Service
- `POST /api/inventory/process` — Process inventory step
- `GET /api/inventory/workflow/{workflow_id}` — Get workflow inventory state

### CRM Service
- `POST /api/crm/process` — Process CRM step
- `GET /api/crm/workflow/{workflow_id}` — Get workflow CRM state

### Notification Service
- `POST /api/notification/process` — Process notification step
- `GET /api/notification/workflow/{workflow_id}` — Get workflow notification state

### Health & Auth (Existing)
- `GET /api/health` — Health check
- `POST /api/auth/register` — User registration
- `POST /api/auth/login` — User login
- `GET /api/auth/me` — Get current user

---

## Database Setup

All models are auto-created on startup via `Base.metadata.create_all(bind=engine)`.

**Local Development**: Single SQLite file (`app.db`) with all tables
**Production (Render)**: Connects to Postgres via `DATABASE_URL` env variable

No Alembic migrations needed for this hackathon setup.

---

## Logging

The entire workflow is logged to stdout in a readable format:

```
[ORCHESTRATOR] Workflow 1 started
[ORCHESTRATOR] Executing step: inventory (workflow_id=1)
[INVENTORY] Received request for workflow 1
[INVENTORY] Processing inventory operation
[INVENTORY] Request completed successfully
[ORCHESTRATOR] Step inventory completed
[ORCHESTRATOR] Executing step: crm (workflow_id=1)
...
[ORCHESTRATOR] Workflow 1 completed successfully
```

Services and the orchestrator log their actions with context (workflow_id, step, attempt).

---

## Future Extensions (Structural Support In Place)

### Retry Scheduling
Implement actual backoff in `WorkflowOrchestrator._execute_step_with_retry()`:
- Linear backoff: wait = base + (attempt × increment)
- Exponential backoff: wait = base × (multiplier ^ attempt)
- Jitter to avoid thundering herd

### Idempotency Guarantees
Implement in `IdempotencyService`:
- Store result of each step under idempotency_key
- Downstream services check keys and return cached results
- Prevents duplicate charges, double-sends, etc.

### Dead-Letter Queue
Create new model `DeadLetterEvent` for workflow.status == DEAD_LETTER:
- Store workflows that are permanently failed
- Re-process manually or via scheduled jobs

### Crash Recovery
On startup, query for workflows with status == RUNNING:
- Resume execution from current_step
- Or implement saga pattern for rollback

### Enhanced Transformations
Extend `TransformationRegistry`:
- Conditional transformations based on workflow context
- Composite transformations chaining multiple operations
- Schema validation before/after transformations

### Workflow Definition Registry
Instead of hardcoding steps in order service:
- Store workflow definitions in a table
- Load and instantiate steps dynamically
- Enable rapid workflow configuration changes

### Observability
Extend logging:
- Metrics/counters for step success/failure rates
- Distributed tracing (e.g., Jaeger integration)
- Dashboard for workflow health monitoring

---

## Running the Application

```bash
cd hackathon-boilerplate
pip install -r requirements.txt
cp .env.example .env
# Generate a SECRET_KEY if needed:
# python -c "import secrets; print(secrets.token_hex(32))"

# Start the server
uvicorn app.main:app --reload

# Open browser to:
# http://127.0.0.1:8000/static/index.html
```

The dashboard allows you to create orders and watch the workflow execute in real-time.

---

## Key Design Decisions

1. **Single Database for MVP**: Local development uses one SQLite file. Each service's table is logically isolated even though they share the file. Extend to separate databases per service later.

2. **No Message Queue**: Orchestrator executes steps synchronously. Requests timeout after 30 seconds. Future: use Celery, RabbitMQ, or SQS for async execution.

3. **No Saga Pattern Yet**: If a step fails, workflow fails. No compensating transactions to undo completed steps. Future: implement saga for rollback.

4. **JWT Auth Preserved**: User authentication is unchanged. Workflows are not yet user-scoped. Future: associate orders/workflows with authenticated users.

5. **Simple Logging**: Structured logs go to stdout. Future: ElasticSearch, Splunk, or DataDog for centralized logging.

6. **No Service Mesh**: Direct HTTP calls. Future: consider Istio or Consul for advanced routing/resilience patterns.

---

## Testing The System

### Create Order & Execute Workflow

```bash
curl -X POST http://localhost:8000/api/order/create \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "customer@example.com",
    "sku": "ITEM-001",
    "quantity": 5
  }'
```

Response:
```json
{
  "order_id": "ORD-ABC12345",
  "workflow_id": 1,
  "status": "COMPLETED",
  "message": "Order processed and workflow executed"
}
```

### Query Workflow History

```bash
curl http://localhost:8000/api/order/history/ORD-ABC12345
```

Response shows complete audit trail with timestamps and step results.

### Interactive Dashboard

Open [http://127.0.0.1:8000/static/index.html](http://127.0.0.1:8000/static/index.html) to:
- Create orders via form
- View real-time workflow status
- Browse execution log
- Query existing workflows

---

## Summary

This structure provides a **solid foundation** for a fault-tolerant, multi-service workflow system:

✅ Clean separation between orchestration and domain logic  
✅ Independent services with isolated databases  
✅ Extensible step/retry/transform abstractions  
✅ Complete audit trail for compliance/debugging  
✅ Idempotency boundaries for safe replay  
✅ Simple to run locally, configurable for production  

The MVP (fault tolerance, retries, dead-letter handling) can be implemented incrementally on this foundation without major restructuring.
