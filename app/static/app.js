/**
 * Frontend application for workflow orchestration demo.
 * 
 * Provides:
 * - Order creation form
 * - Real-time workflow status visualization
 * - Execution log display
 * - Query/lookup for existing workflows
 */

class WorkflowDashboard {
    constructor() {
        this.orderForm = document.getElementById('orderForm');
        this.queryForm = document.getElementById('queryForm');
        this.statusPanel = document.getElementById('statusPanel');
        this.logPanel = document.getElementById('logPanel');
        
        this.logs = [];
        this.currentWorkflowId = null;
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.orderForm.addEventListener('submit', (e) => this.handleOrderSubmit(e));
        this.queryForm.addEventListener('submit', (e) => this.handleQuerySubmit(e));
    }

    async handleOrderSubmit(e) {
        e.preventDefault();
        
        const formData = new FormData(this.orderForm);
        const payload = {
            customer_email: formData.get('customerEmail'),
            sku: formData.get('sku'),
            quantity: parseInt(formData.get('quantity')),
        };

        this.logs = [];
        this.addLog('info', 'Creating order and executing workflow...');
        this.showLoading();

        try {
            const response = await fetch('/api/order/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();
            this.currentWorkflowId = result.workflow_id;
            const orderId = result.order_id;

            this.addLog('success', `Workflow executed successfully`);
            this.addLog('info', `Order ID: ${orderId}`);
            this.addLog('info', `Workflow ID: ${result.workflow_id}`);
            this.addLog('info', `Status: ${result.status}`);

            // Fetch detailed history
            await this.fetchWorkflowHistory(orderId);
        } catch (error) {
            this.addLog('error', `Failed to create order: ${error.message}`);
        } finally {
            this.renderLog();
        }
    }

    async handleQuerySubmit(e) {
        e.preventDefault();
        
        const orderId = document.getElementById('orderId').value;
        this.logs = [];
        this.addLog('info', `Querying order: ${orderId}...`);
        this.showLoading();

        try {
            await this.fetchWorkflowHistory(orderId);
        } catch (error) {
            this.addLog('error', `Failed to fetch workflow: ${error.message}`);
        } finally {
            this.renderLog();
        }
    }

    async fetchWorkflowHistory(orderId) {
        try {
            const response = await fetch(`/api/order/history/${orderId}`);
            
            if (!response.ok) {
                throw new Error(`Workflow not found: ${response.status}`);
            }

            const history = await response.json();
            this.renderWorkflowStatus(history);
            this.renderExecutionHistory(history);
        } catch (error) {
            throw error;
        }
    }

    renderWorkflowStatus(history) {
        const steps = ['inventory', 'crm', 'notification'];
        const stepStatus = {};

        // Initialize all steps as pending
        steps.forEach(step => {
            stepStatus[step] = { status: 'pending', timestamp: null };
        });

        // Map events to steps
        history.events.forEach(event => {
            if (event.step && event.step in stepStatus) {
                if (event.event_type === 'STEP_SUCCEEDED') {
                    stepStatus[event.step].status = 'completed';
                } else if (event.event_type === 'STEP_FAILED') {
                    stepStatus[event.step].status = 'failed';
                } else if (event.event_type === 'STEP_STARTED') {
                    stepStatus[event.step].status = 'running';
                }
                stepStatus[event.step].timestamp = event.timestamp;
            }
        });

        const html = `
            <div class="status-header" style="margin-bottom: 20px;">
                <h3>Workflow #${history.workflow_id}</h3>
                <span class="status-badge ${this.getStatusClass(history.status)}">${history.status}</span>
            </div>
            <div style="display: grid; gap: 10px;">
                ${steps.map(step => this.renderStepStatus(step, stepStatus[step])).join('')}
            </div>
        `;

        this.statusPanel.innerHTML = html;
    }

    renderStepStatus(stepName, step) {
        const statusClass = step.status === 'completed' ? 'completed' : 
                          step.status === 'running' ? 'running' : 
                          step.status === 'failed' ? 'failed' : 'pending';
        
        const icon = step.status === 'completed' ? '✓' :
                    step.status === 'running' ? '⟳' :
                    step.status === 'failed' ? '✗' : '-';
        
        const badgeClass = step.status === 'completed' ? 'success' :
                          step.status === 'running' ? 'warning' :
                          step.status === 'failed' ? 'error' : 'pending';

        return `
            <div class="status-item ${statusClass}">
                <div class="status-header">
                    <span class="status-name">${icon} ${stepName.toUpperCase()}</span>
                    <span class="status-badge ${badgeClass}">${step.status.toUpperCase()}</span>
                </div>
                ${step.timestamp ? `<div style="font-size: 0.85em; color: #999;">${new Date(step.timestamp).toLocaleTimeString()}</div>` : ''}
            </div>
        `;
    }

    renderExecutionHistory(history) {
        this.logs = [];
        this.addLog('info', `Workflow #${history.workflow_id} - ${history.status}`);
        this.addLog('info', '---');

        history.events.forEach((event, idx) => {
            const time = new Date(event.timestamp).toLocaleTimeString();
            const stepInfo = event.step ? ` [${event.step}]` : '';
            const attemptInfo = event.attempt > 0 ? ` (attempt ${event.attempt})` : '';
            
            const level = event.event_type.includes('FAILED') ? 'error' :
                         event.event_type.includes('SUCCEEDED') ? 'success' :
                         event.event_type.includes('STARTED') ? 'info' : 'warning';
            
            const message = `${event.event_type}${stepInfo}${attemptInfo}`;
            
            if (event.error_message) {
                this.addLog(level, `${time} - ${message}`);
                this.addLog('error', `   Error: ${event.error_message}`);
            } else {
                this.addLog(level, `${time} - ${message}`);
            }
        });

        this.renderLog();
    }

    addLog(level, message) {
        this.logs.push({ level, message, timestamp: new Date() });
    }

    renderLog() {
        if (this.logs.length === 0) {
            this.logPanel.innerHTML = '<p class="placeholder">No logs yet</p>';
            return;
        }

        const html = this.logs.map(log => {
            const time = log.timestamp.toLocaleTimeString();
            return `
                <div class="log-entry">
                    <span class="log-timestamp">${time}</span>
                    <span class="log-level ${log.level}">[${log.level.toUpperCase()}]</span>
                    ${log.message}
                </div>
            `;
        }).join('');

        this.logPanel.innerHTML = html;
        this.logPanel.scrollTop = this.logPanel.scrollHeight;
    }

    showLoading() {
        this.statusPanel.innerHTML = '<p class="placeholder"><span class="loading"></span> Processing...</p>';
    }

    getStatusClass(status) {
        if (status === 'COMPLETED') return 'success';
        if (status === 'FAILED') return 'error';
        if (status === 'RUNNING') return 'warning';
        return 'pending';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new WorkflowDashboard();
});
