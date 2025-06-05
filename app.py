#!/usr/bin/env python3
"""
Web-based Salesforce AI Assistant
Flask backend for handling Salesforce interactions via Zapier MCP and OpenAI
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration for primary fields display
PRIMARY_CONTACT_FIELDS = ['Id', 'Name', 'FirstName', 'LastName', 'Email', 'Phone', 'MobilePhone', 'Title', 'AccountId']
PRIMARY_ACCOUNT_FIELDS = ['Id', 'Name', 'Type', 'Industry', 'Phone', 'Website', 'BillingCity', 'BillingState']
PRIMARY_OPPORTUNITY_FIELDS = ['Id', 'Name', 'StageName', 'Amount', 'CloseDate', 'AccountId', 'OwnerId']
PRIMARY_LEAD_FIELDS = ['Id', 'Name', 'FirstName', 'LastName', 'Email', 'Phone', 'Company', 'Status']

class SalesforceWebAssistant:
    def __init__(self):
        self.client = None
        self.zapier_mcp_url = None
        self.zapier_mcp_api_key = None
        self.command_history = []
        self.max_history = 10
        
    def initialize_clients(self) -> bool:
        """Initialize OpenAI client and Zapier MCP configuration."""
        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
            self.zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return False
    
    def validate_environment(self) -> tuple[bool, List[str]]:
        """Validate required environment variables."""
        required_vars = ['OPENAI_API_KEY', 'ZAPIER_MCP_SERVER_URL', 'ZAPIER_MCP_API_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        return len(missing_vars) == 0, missing_vars
    
    def add_to_history(self, command: str):
        """Add command to history, maintaining max size."""
        if command and not command.startswith('/'):
            self.command_history.append({
                'command': command,
                'timestamp': datetime.now().isoformat()
            })
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
    
    def parse_sse_response(self, response_text: str) -> List[Dict]:
        """Parse Server-Sent Events response from Zapier MCP."""
        events = []
        lines = response_text.strip().split('\n')
        current_event = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('event:'):
                if current_event:
                    events.append(current_event)
                current_event = {'type': line[6:].strip()}
            elif line.startswith('data:'):
                data = line[5:].strip()
                if data:
                    try:
                        current_event['data'] = json.loads(data)
                    except json.JSONDecodeError:
                        current_event['data'] = data
            elif line == '' and current_event:
                events.append(current_event)
                current_event = {}
        
        if current_event:
            events.append(current_event)
        
        return events
    
    def select_tool(self, action: str, available_tools: List[Dict]) -> Optional[Dict]:
        """Select the most appropriate tool for the given action."""
        action_lower = action.lower()
        
        # Define tool priorities based on action type
        if any(keyword in action_lower for keyword in ['find', 'search', 'get', 'show', 'list']):
            priorities = ['salesforce_find_record', 'salesforce_find_record_by_query', 'salesforce_find_record_s']
        elif any(keyword in action_lower for keyword in ['create', 'add', 'new']):
            priorities = ['salesforce_create_contact', 'salesforce_create_lead', 'salesforce_create_record']
        elif any(keyword in action_lower for keyword in ['update', 'modify', 'change']):
            priorities = ['salesforce_update_record', 'salesforce_update_contact', 'salesforce_update_lead']
        elif any(keyword in action_lower for keyword in ['log', 'call', 'task', 'activity']):
            priorities = ['salesforce_create_note', 'salesforce_create_record']
        else:
            priorities = ['salesforce_find_record', 'salesforce_create_record']
        
        # Find tool by priority
        for priority in priorities:
            for tool in available_tools:
                if tool.get('name') == priority:
                    return tool
        
        # Fallback to first Salesforce tool
        for tool in available_tools:
            if 'salesforce' in tool.get('name', '').lower():
                return tool
        
        return available_tools[0] if available_tools else None
    
    def call_zapier_mcp(self, action: str) -> Dict[str, Any]:
        """Make request to Zapier MCP server."""
        try:
            headers = {
                "Authorization": f"Bearer {self.zapier_mcp_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            
            # Get available tools
            tools_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }
            
            tools_response = requests.post(self.zapier_mcp_url, headers=headers, json=tools_payload, timeout=30)
            
            if tools_response.status_code == 200:
                events = self.parse_sse_response(tools_response.text)
                
                # Find available tools
                available_tools = []
                for event in events:
                    if event.get('type') == 'message' and isinstance(event.get('data'), dict):
                        event_data = event['data']
                        if 'result' in event_data and 'tools' in event_data['result']:
                            available_tools = event_data['result']['tools']
                            break
                
                if available_tools:
                    # Select appropriate tool based on action
                    selected_tool = self.select_tool(action, available_tools)
                    
                    if selected_tool:
                        # Call the selected tool
                        call_payload = {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": selected_tool['name'],
                                "arguments": {
                                    "instructions": action
                                }
                            }
                        }
                        
                        call_response = requests.post(self.zapier_mcp_url, headers=headers, json=call_payload, timeout=60)
                        
                        if call_response.status_code == 200:
                            call_events = self.parse_sse_response(call_response.text)
                            
                            # Extract result
                            for event in call_events:
                                if event.get('type') == 'message' and isinstance(event.get('data'), dict):
                                    event_data = event['data']
                                    if 'result' in event_data:
                                        return {
                                            "success": True,
                                            "data": event_data['result'],
                                            "tool_used": selected_tool['name']
                                        }
                            
                            return {
                                "success": True,
                                "data": call_events,
                                "tool_used": selected_tool['name']
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"Tool call failed: {call_response.status_code} - {call_response.text}"
                            }
                    else:
                        return {
                            "success": False,
                            "error": "No suitable tool found for this action"
                        }
                else:
                    return {
                        "success": False,
                        "error": "No tools available from Zapier MCP"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get tools: {tools_response.status_code} - {tools_response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def parse_salesforce_data(self, data: Any) -> Dict[str, Any]:
        """Parse Salesforce data from various response formats."""
        try:
            # Handle string JSON
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return {"parsed": False, "raw_data": data}
            
            # Look for results in common response structures
            results = []
            
            if isinstance(data, dict):
                # Check for 'results' key
                if 'results' in data:
                    results = data['results']
                # Check for 'records' key
                elif 'records' in data:
                    results = data['records']
                # Check if data itself is a record
                elif 'Id' in data or 'id' in data:
                    results = [data]
                # Check for nested data
                elif 'data' in data:
                    return self.parse_salesforce_data(data['data'])
            elif isinstance(data, list):
                results = data
            
            return {
                "parsed": True,
                "results": results,
                "count": len(results) if isinstance(results, list) else (1 if results else 0)
            }
            
        except Exception as e:
            logger.error(f"Error parsing Salesforce data: {e}")
            return {"parsed": False, "error": str(e), "raw_data": data}
    
    def get_primary_fields(self, record: Dict) -> List[str]:
        """Get primary fields list based on record type."""
        record_type = self.detect_record_type(record)
        
        if record_type == 'Contact':
            return PRIMARY_CONTACT_FIELDS
        elif record_type == 'Account':
            return PRIMARY_ACCOUNT_FIELDS
        elif record_type == 'Opportunity':
            return PRIMARY_OPPORTUNITY_FIELDS
        elif record_type == 'Lead':
            return PRIMARY_LEAD_FIELDS
        else:
            return ['Id', 'Name', 'Email', 'Phone', 'Type', 'Status']
    
    def detect_record_type(self, record: Dict) -> str:
        """Detect the type of Salesforce record."""
        if 'attributes' in record and 'type' in record['attributes']:
            return record['attributes']['type']
        
        # Infer from available fields
        if 'FirstName' in record or 'LastName' in record:
            return 'Contact'
        elif 'Industry' in record or 'BillingCity' in record:
            return 'Account'
        elif 'StageName' in record or 'Amount' in record:
            return 'Opportunity'
        elif 'Company' in record and 'Status' in record:
            return 'Lead'
        else:
            return 'Unknown'
    
    def format_record_for_display(self, record: Dict, show_all: bool = False) -> Dict[str, Any]:
        """Format a record for web display."""
        record_type = self.detect_record_type(record)
        record_name = record.get('Name') or f"{record.get('FirstName', '')} {record.get('LastName', '')}".strip() or record.get('Id', 'Unknown')
        
        # Get primary fields
        primary_fields = self.get_primary_fields(record)
        displayed_fields = set()
        
        primary_data = []
        for field in primary_fields:
            value = record.get(field)
            if value is not None and value != '':
                primary_data.append({
                    'field': self.format_field_name(field),
                    'value': str(value)
                })
                displayed_fields.add(field)
        
        additional_data = []
        if show_all:
            for field, value in record.items():
                if field not in displayed_fields and value is not None and value != '':
                    if not field.startswith('_') and field != 'attributes':
                        additional_data.append({
                            'field': self.format_field_name(field),
                            'value': str(value)
                        })
        
        return {
            'record_type': record_type,
            'record_name': record_name,
            'record_id': record.get('Id', ''),
            'primary_data': primary_data,
            'additional_data': additional_data,
            'raw_record': record
        }
    
    def format_field_name(self, field: str) -> str:
        """Format field names for better display."""
        field_mappings = {
            'Id': 'Salesforce ID',
            'FirstName': 'First Name',
            'LastName': 'Last Name',
            'Email': 'Email Address',
            'Phone': 'Phone',
            'MobilePhone': 'Mobile Phone',
            'AccountId': 'Account ID',
            'BillingCity': 'Billing City',
            'BillingState': 'Billing State',
            'StageName': 'Stage',
            'CloseDate': 'Close Date',
            'OwnerId': 'Owner ID'
        }
        
        return field_mappings.get(field, field)
    
    def get_follow_up_actions(self, record: Dict) -> List[Dict[str, str]]:
        """Get contextual follow-up actions based on record type."""
        record_type = self.detect_record_type(record)
        record_name = record.get('Name') or f"{record.get('FirstName', '')} {record.get('LastName', '')}".strip()
        
        if record_type == 'Contact':
            return [
                {'id': 'log_call', 'label': f'Log a call for {record_name}'},
                {'id': 'create_task', 'label': f'Create a follow-up task for {record_name}'},
                {'id': 'view_account', 'label': 'View linked Account details'}
            ]
        elif record_type == 'Account':
            return [
                {'id': 'find_contacts', 'label': f'Find contacts at {record_name}'},
                {'id': 'view_opportunities', 'label': f'View opportunities for {record_name}'},
                {'id': 'log_activity', 'label': f'Log activity for {record_name}'}
            ]
        elif record_type == 'Opportunity':
            return [
                {'id': 'update_stage', 'label': 'Update opportunity stage'},
                {'id': 'log_activity', 'label': f'Log activity for {record_name}'},
                {'id': 'view_account', 'label': 'View related account'}
            ]
        else:
            return [
                {'id': 'create_task', 'label': 'Create a related task'},
                {'id': 'update_record', 'label': 'Update this record'}
            ]

# Initialize the assistant
assistant = SalesforceWebAssistant()

@app.route('/')
def index():
    """Serve the main chat interface."""
    return render_template('index.html')

@app.route('/api/send_command', methods=['POST'])
def send_command():
    """Process user commands and return structured responses."""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                'success': False,
                'error': 'No command provided'
            })
        
        # Validate environment
        env_valid, missing_vars = assistant.validate_environment()
        if not env_valid:
            return jsonify({
                'success': False,
                'error': f'Missing environment variables: {", ".join(missing_vars)}'
            })
        
        # Initialize clients
        if not assistant.initialize_clients():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize API clients'
            })
        
        # Add to history
        assistant.add_to_history(command)
        
        # Check if action requires confirmation
        requires_confirmation = any(keyword in command.lower() for keyword in ['create', 'update', 'delete', 'log'])
        
        if requires_confirmation and not data.get('confirmed', False):
            return jsonify({
                'success': True,
                'requires_confirmation': True,
                'command': command,
                'message': f"You're about to perform the action: '{command}'. Are you sure you want to proceed?"
            })
        
        # Process the command
        result = assistant.call_zapier_mcp(command)
        
        if result['success']:
            parsed_data = assistant.parse_salesforce_data(result['data'])
            
            if parsed_data['parsed']:
                results = parsed_data['results']
                count = parsed_data['count']
                
                if count == 0:
                    return jsonify({
                        'success': True,
                        'message': 'No records found matching your query.',
                        'type': 'no_results'
                    })
                elif count == 1:
                    # Single record found
                    record = results[0] if isinstance(results, list) else results
                    formatted_record = assistant.format_record_for_display(record)
                    follow_ups = assistant.get_follow_up_actions(record)
                    
                    return jsonify({
                        'success': True,
                        'type': 'single_record',
                        'record': formatted_record,
                        'follow_ups': follow_ups,
                        'message': f"Found {formatted_record['record_name']}"
                    })
                else:
                    # Multiple records found
                    record_summaries = []
                    for i, record in enumerate(results):
                        name = record.get('Name') or f"{record.get('FirstName', '')} {record.get('LastName', '')}".strip()
                        email = record.get('Email', '')
                        record_id = record.get('Id', '')
                        
                        record_summaries.append({
                            'index': i,
                            'name': name,
                            'email': email,
                            'id': record_id,
                            'display': f"{name} ({email})" if email else name
                        })
                    
                    return jsonify({
                        'success': True,
                        'type': 'multiple_records',
                        'records': record_summaries,
                        'count': count,
                        'message': f"Found {count} records matching your query"
                    })
            else:
                return jsonify({
                    'success': True,
                    'type': 'raw_response',
                    'message': 'Received response from Salesforce',
                    'data': parsed_data.get('raw_data', 'No data')
                })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            })
            
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        })

@app.route('/api/get_record_details', methods=['POST'])
def get_record_details():
    """Get full details for a specific record from a multiple results list."""
    try:
        data = request.get_json()
        record_index = data.get('record_index')
        original_command = data.get('original_command', '')
        
        if record_index is None:
            return jsonify({
                'success': False,
                'error': 'Record index not provided'
            })
        
        # Re-execute the original command to get the data
        result = assistant.call_zapier_mcp(original_command)
        
        if result['success']:
            parsed_data = assistant.parse_salesforce_data(result['data'])
            
            if parsed_data['parsed'] and parsed_data['results']:
                results = parsed_data['results']
                
                if 0 <= record_index < len(results):
                    record = results[record_index]
                    formatted_record = assistant.format_record_for_display(record)
                    follow_ups = assistant.get_follow_up_actions(record)
                    
                    return jsonify({
                        'success': True,
                        'record': formatted_record,
                        'follow_ups': follow_ups
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid record index'
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Could not parse record data'
                })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            })
            
    except Exception as e:
        logger.error(f"Error getting record details: {e}")
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        })

@app.route('/api/show_more_details', methods=['POST'])
def show_more_details():
    """Show additional details for a record."""
    try:
        data = request.get_json()
        record_data = data.get('record')
        
        if not record_data:
            return jsonify({
                'success': False,
                'error': 'Record data not provided'
            })
        
        formatted_record = assistant.format_record_for_display(record_data['raw_record'], show_all=True)
        
        return jsonify({
            'success': True,
            'additional_data': formatted_record['additional_data']
        })
        
    except Exception as e:
        logger.error(f"Error showing more details: {e}")
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        })

@app.route('/api/get_history', methods=['GET'])
def get_history():
    """Get command history."""
    try:
        return jsonify({
            'success': True,
            'history': assistant.command_history
        })
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        })

@app.route('/api/save_record', methods=['POST'])
def save_record():
    """Save record details to a file and provide download."""
    try:
        data = request.get_json()
        record_data = data.get('record')
        filename = data.get('filename', 'salesforce_record.txt')
        
        if not record_data:
            return jsonify({
                'success': False,
                'error': 'Record data not provided'
            })
        
        # Generate file content
        content = f"Salesforce Record Export\n"
        content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "="*50 + "\n\n"
        content += f"Record Type: {record_data['record_type']}\n"
        content += f"Record Name: {record_data['record_name']}\n\n"
        
        # Add primary data
        content += "Primary Information:\n"
        content += "-" * 20 + "\n"
        for item in record_data['primary_data']:
            content += f"{item['field']}: {item['value']}\n"
        
        # Add additional data if available
        if record_data.get('additional_data'):
            content += "\nAdditional Details:\n"
            content += "-" * 20 + "\n"
            for item in record_data['additional_data']:
                content += f"{item['field']}: {item['value']}\n"
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        temp_file.write(content)
        temp_file.close()
        
        return jsonify({
            'success': True,
            'download_url': f'/api/download_file/{os.path.basename(temp_file.name)}',
            'filename': filename
        })
        
    except Exception as e:
        logger.error(f"Error saving record: {e}")
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}'
        })

@app.route('/api/download_file/<filename>')
def download_file(filename):
    """Download a saved file."""
    try:
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        if os.path.exists(temp_path):
            return send_file(temp_path, as_attachment=True, download_name='salesforce_record.txt')
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'error': 'Download failed'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)