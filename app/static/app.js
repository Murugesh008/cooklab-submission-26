document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch of service status
    fetchServiceStatus();

    // Event listeners
    document.getElementById('refreshBtn').addEventListener('click', fetchServiceStatus);
    document.getElementById('orderForm').addEventListener('submit', handleOrderSubmit);

    // Auto-refresh service statuses every 5 seconds
    setInterval(fetchServiceStatus, 5000);
});

// Fetch & Update Service Statuses
async function fetchServiceStatus() {
    try {
        const response = await fetch('/api/admin/services/status');
        if (!response.ok) return;
        const statuses = await response.json();

        for (const [service, info] of Object.entries(statuses)) {
            const statusEl = document.getElementById(`status-${service}`);
            const cardEl = document.getElementById(`card-${service}`);
            if (!statusEl || !cardEl) continue;

            if (!info.online) {
                statusEl.textContent = '● DOWN (Offline)';
                statusEl.className = 'status-indicator offline';
            } else if (info.is_failed) {
                statusEl.textContent = '🔴 SIMULATING FAILURE';
                statusEl.className = 'status-indicator offline';
            } else {
                statusEl.textContent = '● UP';
                statusEl.className = 'status-indicator online';
            }
        }
    } catch (err) {
        console.error('Error fetching service status:', err);
    }
}

// Simulate Failure on Service
async function simulateFailure(serviceName) {
    try {
        const res = await fetch(`/api/admin/services/${serviceName}/simulate-failure`, { method: 'POST' });
        const data = await res.json();
        fetchServiceStatus();
    } catch (err) {
        alert(`Failed to simulate failure for ${serviceName}: ${err}`);
    }
}

// Recover Service
async function recoverService(serviceName) {
    try {
        const res = await fetch(`/api/admin/services/${serviceName}/recover`, { method: 'POST' });
        const data = await res.json();
        fetchServiceStatus();
    } catch (err) {
        alert(`Failed to recover ${serviceName}: ${err}`);
    }
}

// Handle Order Form Submission
async function handleOrderSubmit(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Executing Orchestrated Workflow...';

    const customerEmail = document.getElementById('customerEmail').value;
    const sku = document.getElementById('sku').value;
    const quantity = parseInt(document.getElementById('quantity').value);

    // Reset pipeline UI
    resetPipeline();

    try {
        const response = await fetch('/api/order/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ customer_email: customerEmail, sku, quantity })
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.detail || 'Order creation failed');
        }

        document.getElementById('queryOrderId').value = result.order_id;
        await loadOrderHistory(result.order_id);

    } catch (err) {
        const resultMsg = document.getElementById('workflowResultMsg');
        resultMsg.textContent = `❌ Workflow Execution Failed: ${err.message}`;
        resultMsg.style.borderColor = 'var(--accent-red)';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '🚀 Start Workflow Execution';
    }
}

// Query Order History
async function queryOrderHistory() {
    const orderId = document.getElementById('queryOrderId').value.trim();
    if (!orderId) {
        alert('Please enter an Order ID');
        return;
    }
    await loadOrderHistory(orderId);
}

// Load and Render History & Update Pipeline
async function loadOrderHistory(orderId) {
    try {
        const response = await fetch(`/api/order/history/${orderId}`);
        if (!response.ok) {
            alert('Order history not found');
            return;
        }
        const data = await response.json();
        renderDiagnosis(data.diagnosis);

        // Update overall badge
        const badge = document.getElementById('workflowStatusBadge');
        badge.textContent = data.status;

        if (data.status === 'COMPLETED') {
            badge.className = 'badge badge-success';
        } else if (data.status === 'COMPLETED_WITH_RECOVERY') {
            badge.className = 'badge badge-recovery';
        } else if (data.status === 'FAILED') {
            badge.className = 'badge badge-danger';
        } else {
            badge.className = 'badge badge-warning';
        }

        // Render Audit Logs
        const tableBody = document.getElementById('auditTableBody');
        tableBody.innerHTML = '';

        if (!data.events || data.events.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-row">No events logged.</td></tr>';
            return;
        }

        let inventoryState = 'PENDING';
        let crmState = 'PENDING';
        let notificationState = 'PENDING';

        data.events.forEach(evt => {
            const tr = document.createElement('tr');
            
            // Format timestamp
            const dateStr = new Date(evt.timestamp).toLocaleTimeString();
            
            // Determine badge class
            let eventBadgeClass = 'badge-info';
            if (evt.event_type.includes('SUCCEEDED') || evt.event_type.includes('COMPLETED')) {
                eventBadgeClass = 'badge-success';
            } else if (evt.event_type.includes('FAILED')) {
                eventBadgeClass = 'badge-danger';
            } else if (evt.event_type.includes('RETRY')) {
                eventBadgeClass = 'badge-warning';
            } else if (evt.event_type.includes('RECOVERY')) {
                eventBadgeClass = 'badge-recovery';
            }

            tr.innerHTML = `
                <td>${dateStr}</td>
                <td><strong>${evt.step ? evt.step.toUpperCase() : 'ORCHESTRATOR'}</strong></td>
                <td><span class="badge ${eventBadgeClass}">${evt.event_type}</span></td>
                <td>Attempt #${evt.attempt}</td>
                <td>${evt.error_message || 'Completed successfully'}</td>
            `;
            tableBody.appendChild(tr);

            // Track step statuses for live diagram
            if (evt.step === 'inventory') {
                if (evt.event_type === 'STEP_SUCCEEDED') inventoryState = 'SUCCESS';
                else if (evt.event_type === 'STEP_FAILED' || evt.event_type === 'RETRY_FAILED') inventoryState = 'FAILED';
            }
            if (evt.step === 'crm') {
                if (evt.event_type === 'STEP_SUCCEEDED') crmState = 'SUCCESS';
                else if (evt.event_type === 'RECOVERY_COMPLETED') crmState = 'RECOVERED';
                else if (evt.event_type === 'STEP_FAILED' || evt.event_type === 'RETRY_FAILED') crmState = 'FAILED';
            }
            if (evt.step === 'notification') {
                if (evt.event_type === 'STEP_SUCCEEDED') notificationState = 'SUCCESS';
                else if (evt.event_type === 'RECOVERY_COMPLETED') notificationState = 'RECOVERED';
                else if (evt.event_type === 'STEP_FAILED' || evt.event_type === 'RETRY_FAILED') notificationState = 'FAILED';
            }
        });

        // Update pipeline nodes
        updatePipelineStep('step-order', 'success', 'COMPLETED');
        updatePipelineStep('step-inventory', inventoryState.toLowerCase(), inventoryState);
        updatePipelineStep('step-crm', crmState.toLowerCase(), crmState);
        updatePipelineStep('step-notification', notificationState.toLowerCase(), notificationState);

        const resultMsg = document.getElementById('workflowResultMsg');
        if (data.status === 'COMPLETED_WITH_RECOVERY') {
            resultMsg.textContent = `⚡ Workflow ${data.order_id} completed via Recovery Policy! CRM was offline, retried, and compensated without halting workflow execution.`;
            resultMsg.style.borderColor = 'var(--accent-purple)';
        } else if (data.status === 'COMPLETED') {
            resultMsg.textContent = `✅ Workflow ${data.order_id} completed successfully across all independent services!`;
            resultMsg.style.borderColor = 'var(--accent-green)';
        } else {
            resultMsg.textContent = `❌ Workflow ${data.order_id} failed: ${data.status}`;
            resultMsg.style.borderColor = 'var(--accent-red)';
        }

    } catch (err) {
        console.error('Error loading history:', err);
    }
}

function renderDiagnosis(diagnosis) {
    const card = document.getElementById('diagnosisCard');
    if (!card) return;
    if (!diagnosis) {
        card.hidden = true;
        return;
    }
    card.hidden = false;
    document.getElementById('diagnosisStep').textContent = diagnosis.failed_step;
    document.getElementById('diagnosisType').textContent = diagnosis.failure_type;
    document.getElementById('diagnosisConfidence').textContent = `${Math.round(diagnosis.confidence * 100)}%`;
    document.getElementById('diagnosisRootCause').textContent = diagnosis.root_cause;
    document.getElementById('diagnosisActions').innerHTML = diagnosis.recommended_actions.map(action => `<li>${action}</li>`).join('');
    document.getElementById('diagnosisMessage').textContent = diagnosis.maintenance_message;
}

function updatePipelineStep(stepId, stateClass, statusText) {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.className = `pipeline-step ${stateClass}`;
    const statusEl = el.querySelector('.step-status');
    if (statusEl) statusEl.textContent = statusText;
}

function resetPipeline() {
    ['step-inventory', 'step-crm', 'step-notification'].forEach(id => {
        updatePipelineStep(id, '', 'PENDING');
    });
    document.getElementById('workflowStatusBadge').textContent = 'RUNNING';
    document.getElementById('workflowStatusBadge').className = 'badge badge-warning';
    document.getElementById('workflowResultMsg').textContent = 'Executing workflow steps...';
}
