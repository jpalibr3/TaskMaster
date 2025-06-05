// Salesforce AI Assistant JavaScript
class SalesforceAI {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        
        // Modals
        this.confirmationModal = document.getElementById('confirmationModal');
        this.recordSelectionModal = document.getElementById('recordSelectionModal');
        this.historyModal = document.getElementById('historyModal');
        
        this.pendingCommand = null;
        this.currentRecords = [];
        this.originalCommand = '';
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Send message on button click or Enter key
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // History button
        document.getElementById('historyButton').addEventListener('click', () => this.showHistory());
        
        // Clear chat button
        document.getElementById('clearButton').addEventListener('click', () => this.clearChat());
        
        // Confirmation modal buttons
        document.getElementById('confirmYes').addEventListener('click', () => this.confirmAction());
        document.getElementById('confirmNo').addEventListener('click', () => this.hideModal('confirmationModal'));
        
        // Record selection modal buttons
        document.getElementById('newSearchBtn').addEventListener('click', () => {
            this.hideModal('recordSelectionModal');
            // Clear state when starting new search
            this.currentRecords = [];
            this.originalCommand = '';
            console.log('Cleared currentRecords and originalCommand after clicking New Search.');
        });
        
        // History modal button
        document.getElementById('closeHistoryBtn').addEventListener('click', () => this.hideModal('historyModal'));
        
        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModal(modal.id);
                    // Clear state when record selection modal is dismissed
                    if (modal.id === 'recordSelectionModal') {
                        this.currentRecords = [];
                        this.originalCommand = '';
                        console.log('Cleared currentRecords and originalCommand after closing recordSelectionModal via overlay.');
                    }
                }
            });
        });
    }
    
    async sendMessage(confirmedCommand = null) {
        const command = confirmedCommand || this.messageInput.value.trim();
        
        if (!command) return;
        
        // Clear input if not a confirmed command
        if (!confirmedCommand) {
            this.messageInput.value = '';
        }
        
        // Add user message to chat
        this.addMessage(command, 'user');
        
        // Show loading
        this.showLoading();
        this.sendButton.disabled = true;
        
        try {
            const response = await fetch('/api/send_command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    command: command,
                    confirmed: !!confirmedCommand
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.handleSuccessResponse(data, command);
            } else {
                this.addMessage(`Error: ${data.error}`, 'ai', 'error');
            }
        } catch (error) {
            this.addMessage(`Connection error: ${error.message}`, 'ai', 'error');
        } finally {
            this.hideLoading();
            this.sendButton.disabled = false;
        }
    }
    
    handleSuccessResponse(data, command) {
        if (data.requires_confirmation) {
            this.showConfirmation(data.message, command);
            return;
        }
        
        switch (data.type) {
            case 'single_record':
                this.displaySingleRecord(data.record, data.follow_ups, data.message);
                break;
            case 'multiple_records':
                this.displayMultipleRecords(data.records, data.message, command, data.object_type);
                break;
            case 'no_results':
                this.addMessage(data.message, 'ai');
                break;
            case 'raw_response':
                this.addMessage(`${data.message}: ${data.data}`, 'ai');
                break;
            default:
                this.addMessage(data.message || 'Command completed successfully.', 'ai');
        }
    }
    
    displaySingleRecord(record, followUps, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        
        let html = `
            <div class="message-content">
                <strong>🤖 Salesforce AI:</strong> ${message}
                <div class="record-display">
                    <div class="record-header">
                        ${record.record_type}: ${record.record_name}
                    </div>
                    <div class="record-data">
        `;
        
        // Display primary data
        record.primary_data.forEach(field => {
            html += `
                <div class="field-row">
                    <div class="field-label">${field.field}</div>
                    <div class="field-value">${field.value}</div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
                <div class="action-buttons">
                    <button class="btn btn-outline" onclick="salesforceAI.showMoreDetails(${JSON.stringify(record).replace(/"/g, '&quot;')})">
                        ✨ Show More Details
                    </button>
                    <button class="btn btn-success" onclick="salesforceAI.saveRecord(${JSON.stringify(record).replace(/"/g, '&quot;')})">
                        💾 Save Details
                    </button>
                </div>
        `;
        
        // Add follow-up actions
        if (followUps && followUps.length > 0) {
            html += `
                <div style="margin-top: 15px;">
                    <strong>What would you like to do next?</strong>
                    <div class="action-buttons" style="margin-top: 10px;">
            `;
            
            followUps.forEach(action => {
                html += `
                    <button class="btn btn-primary" onclick="salesforceAI.executeFollowUp('${action.id}', ${JSON.stringify(record).replace(/"/g, '&quot;')})">
                        ${action.label}
                    </button>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        messageDiv.innerHTML = html;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    displayMultipleRecords(records, message, originalCommand, objectType = null) {
        this.currentRecords = records;
        this.originalCommand = originalCommand;
        this.currentRecordsObjectType = objectType;
        
        this.addMessage(message, 'ai');
        this.showRecordSelection(records);
    }
    
    showRecordSelection(records) {
        const recordList = document.getElementById('recordList');
        recordList.innerHTML = '';
        
        records.forEach((record, index) => {
            const recordDiv = document.createElement('div');
            recordDiv.className = 'record-item';
            recordDiv.innerHTML = `
                <strong>${record.name}</strong><br>
                <small>${record.email || 'No email'} • ID: ${record.id.substring(0, 8)}...</small>
            `;
            recordDiv.addEventListener('click', () => this.selectRecord(index));
            recordList.appendChild(recordDiv);
        });
        
        this.showModal('recordSelectionModal');
    }
    
    async selectRecord(index) {
        this.hideModal('recordSelectionModal');
        this.showLoading();
        
        const selectedRecord = this.currentRecords[index];
        if (!selectedRecord || !selectedRecord.id) {
            this.addMessage('Error: Could not retrieve the ID for the selected record.', 'ai', 'error');
            this.hideLoading();
            return;
        }
        
        const recordId = selectedRecord.id;
        const recordType = this.currentRecordsObjectType || 'Asset'; // Default to Asset if not specified
        
        try {
            const response = await fetch('/api/get_record_details', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    record_id: recordId,
                    record_type: recordType
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displaySingleRecord(data.record, data.follow_ups, `Details for: ${data.record.record_name}`);
            } else {
                this.addMessage(`Error retrieving details: ${data.error}`, 'ai', 'error');
            }
        } catch (error) {
            this.addMessage(`Connection error while getting details: ${error.message}`, 'ai', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    async showMoreDetails(record) {
        this.showLoading();
        
        try {
            const response = await fetch('/api/show_more_details', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ record: record })
            });
            
            const data = await response.json();
            
            if (data.success && data.additional_data.length > 0) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message ai-message';
                
                let html = `
                    <div class="message-content">
                        <strong>🤖 Salesforce AI:</strong> Additional details for ${record.record_name}:
                        <div class="record-display">
                            <div class="record-header">Additional Information</div>
                            <div class="record-data">
                `;
                
                data.additional_data.forEach(field => {
                    html += `
                        <div class="field-row">
                            <div class="field-label">${field.field}</div>
                            <div class="field-value">${field.value}</div>
                        </div>
                    `;
                });
                
                html += `
                            </div>
                        </div>
                    </div>
                `;
                
                messageDiv.innerHTML = html;
                this.chatMessages.appendChild(messageDiv);
                this.scrollToBottom();
            } else {
                this.addMessage('No additional details available for this record.', 'ai');
            }
        } catch (error) {
            this.addMessage(`Error loading additional details: ${error.message}`, 'ai', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    async saveRecord(record) {
        const filename = prompt('Enter filename (optional):', `${record.record_name.replace(/\s+/g, '_')}_details.txt`);
        
        if (filename === null) return; // User cancelled
        
        this.showLoading();
        
        try {
            const response = await fetch('/api/save_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    record: record,
                    filename: filename || 'salesforce_record.txt'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Trigger download
                const link = document.createElement('a');
                link.href = data.download_url;
                link.download = data.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                this.addMessage(`💾 Record details saved and downloaded as ${data.filename}`, 'ai', 'success');
            } else {
                this.addMessage(`Error saving record: ${data.error}`, 'ai', 'error');
            }
        } catch (error) {
            this.addMessage(`Error saving record: ${error.message}`, 'ai', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    executeFollowUp(actionId, record) {
        let command = '';
        
        switch (actionId) {
            case 'log_call':
                const callDetails = prompt(`Enter call details for ${record.record_name}:`);
                if (callDetails) {
                    command = `Log a call for Salesforce contact ${record.record_name} (ID: ${record.record_id}) regarding: ${callDetails}`;
                }
                break;
            case 'create_task':
                const taskDetails = prompt(`Enter task details for ${record.record_name}:`);
                if (taskDetails) {
                    command = `Create a follow-up task for Salesforce contact ${record.record_name} (ID: ${record.record_id}): ${taskDetails}`;
                }
                break;
            case 'view_account':
                const accountId = record.raw_record.AccountId;
                if (accountId) {
                    command = `Find Salesforce account with ID ${accountId}`;
                }
                break;
            case 'find_contacts':
                command = `Find all contacts at Salesforce account ${record.record_name}`;
                break;
            case 'view_opportunities':
                command = `Find all opportunities for Salesforce account ${record.record_name}`;
                break;
            case 'log_activity':
                const activityDetails = prompt(`Enter activity details for ${record.record_name}:`);
                if (activityDetails) {
                    command = `Log activity for Salesforce account ${record.record_name} (ID: ${record.record_id}): ${activityDetails}`;
                }
                break;
            case 'update_stage':
                const newStage = prompt('Enter new opportunity stage:');
                if (newStage) {
                    command = `Update Salesforce opportunity ${record.record_name} stage to ${newStage}`;
                }
                break;
            case 'update_record':
                const updateDetails = prompt(`Enter update details for ${record.record_name}:`);
                if (updateDetails) {
                    command = `Update Salesforce record ${record.record_name} (ID: ${record.record_id}): ${updateDetails}`;
                }
                break;
        }
        
        if (command) {
            this.sendMessage(command);
        }
    }
    
    showConfirmation(message, command) {
        document.getElementById('confirmationMessage').textContent = message;
        this.pendingCommand = command;
        this.showModal('confirmationModal');
    }
    
    confirmAction() {
        this.hideModal('confirmationModal');
        if (this.pendingCommand) {
            this.sendMessage(this.pendingCommand);
            this.pendingCommand = null;
        }
    }
    
    async showHistory() {
        try {
            const response = await fetch('/api/get_history');
            const data = await response.json();
            
            if (data.success) {
                const historyList = document.getElementById('historyList');
                historyList.innerHTML = '';
                
                if (data.history.length === 0) {
                    historyList.innerHTML = '<div class="no-results">No command history available</div>';
                } else {
                    data.history.forEach((item, index) => {
                        const historyDiv = document.createElement('div');
                        historyDiv.className = 'history-item';
                        historyDiv.innerHTML = `
                            <div class="history-command">${item.command}</div>
                            <div class="history-time">${new Date(item.timestamp).toLocaleString()}</div>
                        `;
                        historyDiv.addEventListener('click', () => {
                            this.messageInput.value = item.command;
                            this.hideModal('historyModal');
                            this.messageInput.focus();
                        });
                        historyList.appendChild(historyDiv);
                    });
                }
                
                this.showModal('historyModal');
            } else {
                this.addMessage(`Error loading history: ${data.error}`, 'ai', 'error');
            }
        } catch (error) {
            this.addMessage(`Error loading history: ${error.message}`, 'ai', 'error');
        }
    }
    
    clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            // Keep only the welcome message
            const messages = this.chatMessages.querySelectorAll('.message');
            for (let i = 1; i < messages.length; i++) {
                messages[i].remove();
            }
        }
    }
    
    addMessage(content, sender, type = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        let messageClass = 'message-content';
        if (type === 'error') messageClass += ' error-message';
        if (type === 'success') messageClass += ' success-message';
        
        const prefix = sender === 'user' ? '➡️ You: ' : '🤖 Salesforce AI: ';
        
        messageDiv.innerHTML = `
            <div class="${messageClass}">
                <strong>${prefix}</strong>${content}
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    showLoading() {
        this.loadingOverlay.classList.add('show');
    }
    
    hideLoading() {
        this.loadingOverlay.classList.remove('show');
    }
    
    showModal(modalId) {
        document.getElementById(modalId).classList.add('show');
    }
    
    hideModal(modalId) {
        document.getElementById(modalId).classList.remove('show');
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.salesforceAI = new SalesforceAI();
});