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
        
        # Available Zapier Salesforce Tools for NLU reference
        self.available_zapier_tools = [
            "Salesforce: Find Record",
            "Salesforce: Find Record(s)", 
            "Salesforce: Find Record(s) by Query",
            "Salesforce: Find Record by Query",
            "Salesforce: Get Record Attachments",
            "Salesforce: Add Contact to Campaign",
            "Salesforce: Add Lead to Campaign", 
            "Salesforce: Convert Lead to Contact",
            "Salesforce: Create Child Records (with line item support)",
            "Salesforce: Create Contact",
            "Salesforce: Find Child Records",
            "Salesforce: Create Lead",
            "Salesforce: Create Note",
            "Salesforce: Create Record",
            "Salesforce: Create Record (UTC)",
            "Salesforce: Send Email",
            "Salesforce: Update Contact",
            "Salesforce: Update Lead", 
            "Salesforce: Update Record",
            "Salesforce: Update Record (UTC)",
            "Salesforce: API Request (Beta)"
        ]
        
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
    
    def get_optimized_zapier_input(self, raw_user_query: str, available_zapier_tools: List[str]) -> str:
        """
        NLU pre-processing function that transforms raw user queries into optimized Zapier inputs.
        Uses OpenAI to analyze the query and generate explicit instructions for Zapier MCP.
        """
        try:
            # Ensure client is initialized
            if not self.client:
                logger.error("OpenAI client not initialized")
                return raw_user_query
                
            # Construct the system prompt for NLU analysis
            system_prompt = f"""You are an AI that translates raw user Salesforce queries into optimized inputs for a Zapier MCP tool.

Available Zapier Tools:
{chr(10).join(f"- {tool}" for tool in available_zapier_tools)}

Your task is to analyze the user's raw query and transform it into simple, natural language that mimics how humans would phrase searches, allowing Zapier's MCP to correctly infer the operator and isolate the search value.

Guidelines for optimization:
1. Identify the core intent (find single record, find multiple records, create, update, etc.)
2. Determine the target Salesforce Object (Account, Contact, Opportunity, Lead, etc.)
3. Extract relevant field names, values, and search operators
4. Determine if the user expects single or multiple results
5. Generate output using simple, natural phrasing that avoids explicit operator keywords

CRITICAL: Your output MUST be a simple, natural language string that helps Zapier correctly parse the object, field, and search value. Avoid using explicit operator words like "contains", "equals" that confuse Zapier's search value extraction.

For direct lookups (equals/exact matches):
- Pattern: "Find [Object] [field]: [Value]"
- Pattern: "Find [Object] with the [field] [Value]"

For contains searches:
- Pattern: "Find [Object] [field]: [Value]" (let Zapier infer contains from partial match)
- Pattern: "[Object] [field]: [Value]"

Template Guidelines:
- Use natural, human-like phrasing
- Always enclose search values in single quotes to help Zapier isolate them
- Use plural forms (records, accounts, contacts) for multiple results
- Use singular forms for unique lookups
- Map user terms to proper field names (name → Account Name, email → Email)

Examples:
- Raw: "show me accounts with zapier in the name" 
  → Optimized: "Find Account name: Zapier"

- Raw: "find john smith contact"
  → Optimized: "Find Contact name: John Smith"

- Raw: "get the QA testing account"
  → Optimized: "Find Account name: QA"

- Raw: "contact email chris@alibre.com"
  → Optimized: "Find Contact email: chris@alibre.com"

- Raw: "account QA TESTING"
  → Optimized: "Find Account name: QA TESTING"

- Raw: "create new lead for jane doe at acme corp"
  → Optimized: "Create new Salesforce Lead record with FirstName 'Jane', LastName 'Doe', Company 'Acme Corp'"

If the query is unclear or missing critical information, return: "I need more specific information. Could you specify the Salesforce object type (Account, Contact, etc.) and search criteria?"

Respond only with the optimized input string, nothing else."""

            # Make the NLU call to OpenAI
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Raw query: {raw_user_query}"}
                ],
                max_tokens=300,
                temperature=0.1  # Low temperature for consistent, focused responses
            )
            
            # Safely extract the response content
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                optimized_input = response.choices[0].message.content.strip()
            else:
                logger.error("Invalid response from OpenAI")
                return raw_user_query
            
            # Check if the NLU model couldn't understand the query
            if "I need more specific information" in optimized_input or "Could you specify" in optimized_input:
                return optimized_input
            
            logger.info(f"NLU Transform: '{raw_user_query}' → '{optimized_input}'")
            return optimized_input
            
        except Exception as e:
            logger.error(f"NLU pre-processing failed: {e}")
            # Fallback to original query if NLU fails
            return raw_user_query
    
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
    
    def prepare_tool_arguments(self, action: str, selected_tool: Dict) -> Dict[str, Any]:
        """Prepare specific arguments for Salesforce tools based on the action."""
        action_lower = action.lower()
        tool_name = selected_tool.get('name', '')
        
        # Extract search parameters from the action
        search_params = self.extract_search_parameters(action_lower)
        
        # Default arguments
        args = {
            "instructions": action
        }
        
        # Add specific parameters based on tool requirements
        if 'find_record' in tool_name:
            if search_params['object_type']:
                args['object'] = search_params['object_type']
            
            if search_params['search_field'] and search_params['search_value']:
                args['searchField'] = search_params['search_field']
                args['searchValue'] = search_params['search_value']
                # Use 'contains' for partial matches, 'equals' for exact matches
                if 'zapier' in action_lower or 'contains' in action_lower or 'with' in action_lower:
                    args['operator'] = 'contains'
                else:
                    args['operator'] = 'equals'
            
            # Add second search field if available
            if search_params['search_field2'] and search_params['search_value2']:
                args['searchField2'] = search_params['search_field2']
                args['searchValue2'] = search_params['search_value2']
        
        elif 'by_query' in tool_name:
            if search_params['object_type']:
                args['object'] = search_params['object_type']
            
            # Build SOQL query
            if search_params['search_field'] and search_params['search_value']:
                query = f"SELECT Id, Name FROM {search_params['object_type']} WHERE {search_params['search_field']} LIKE '%{search_params['search_value']}%'"
                args['query'] = query
        
        return args
    
    def extract_search_parameters(self, action: str) -> Dict[str, str]:
        """Extract search parameters from natural language action."""
        import re
        
        # Determine object type
        object_type = 'Account'  # default
        if any(word in action for word in ['contact', 'person', 'people']):
            object_type = 'Contact'
        elif any(word in action for word in ['account', 'company', 'organization']):
            object_type = 'Account'
        elif any(word in action for word in ['opportunity', 'deal', 'sale']):
            object_type = 'Opportunity'
        elif any(word in action for word in ['lead', 'prospect']):
            object_type = 'Lead'
        
        # Extract search field and value
        search_field = None
        search_value = None
        search_field2 = None
        search_value2 = None
        
        # Email search - improved pattern
        email_match = re.search(r'email[:\s]*([^\s]+@[^\s]+)', action, re.IGNORECASE)
        if email_match:
            search_field = 'Email'
            search_value = email_match.group(1)
        
        # Specific name searches
        elif 'zapier' in action.lower():
            search_field = 'Name'
            search_value = 'Zapier'
        
        # Name search
        elif 'name' in action:
            name_patterns = [
                r'name[:\s]+(["\']([^"\']+)["\'])',  # quoted name
                r'name[:\s]+(\w+(?:\s+\w+)*)',       # unquoted name
                r'with.*name[:\s]+(["\']([^"\']+)["\'])',
                r'called[:\s]+(["\']([^"\']+)["\'])',
                r'called[:\s]+(\w+(?:\s+\w+)*)'
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, action, re.IGNORECASE)
                if match:
                    search_field = 'Name'
                    search_value = match.group(2) if len(match.groups()) > 1 and match.group(2) else match.group(1)
                    search_value = search_value.strip('\'"')
                    break
        
        # Company/Account search
        elif any(word in action for word in ['at ', 'company ', 'account ']):
            company_patterns = [
                r'at\s+(["\']([^"\']+)["\'])',
                r'at\s+(\w+(?:\s+\w+)*)',
                r'company[:\s]+(["\']([^"\']+)["\'])',
                r'company[:\s]+(\w+(?:\s+\w+)*)',
                r'account[:\s]+(["\']([^"\']+)["\'])',
                r'account[:\s]+(\w+(?:\s+\w+)*)'
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, action, re.IGNORECASE)
                if match:
                    if object_type == 'Contact':
                        search_field = 'Account.Name'
                    else:
                        search_field = 'Name'
                    search_value = match.group(2) if len(match.groups()) > 1 and match.group(2) else match.group(1)
                    search_value = search_value.strip('\'"')
                    break
        
        # Generic "with" search
        elif 'with' in action:
            # Extract anything after "with"
            with_match = re.search(r'with\s+(.+)', action, re.IGNORECASE)
            if with_match:
                search_field = 'Name'
                search_value = with_match.group(1).strip()
        
        # If no specific field found, try to extract any quoted text or last words
        if not search_field and not search_value:
            # Look for quoted text
            quote_match = re.search(r'["\']([^"\']+)["\']', action)
            if quote_match:
                search_field = 'Name'
                search_value = quote_match.group(1)
            else:
                # Extract last meaningful words
                words = action.split()
                if len(words) >= 2:
                    search_field = 'Name'
                    search_value = ' '.join(words[-2:])
        
        return {
            'object_type': object_type,
            'search_field': search_field,
            'search_value': search_value,
            'search_field2': search_field2,
            'search_value2': search_value2
        }
    
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
                        # Call the selected tool with better parameters
                        tool_args = self.prepare_tool_arguments(action, selected_tool)
                        
                        call_payload = {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": selected_tool['name'],
                                "arguments": tool_args
                            }
                        }
                        
                        call_response = requests.post(self.zapier_mcp_url, headers=headers, json=call_payload, timeout=60)
                        
                        if call_response.status_code == 200:
                            call_events = self.parse_sse_response(call_response.text)
                            
                            # Extract result and handle various response formats
                            for event in call_events:
                                if event.get('type') == 'message' and isinstance(event.get('data'), dict):
                                    event_data = event['data']
                                    if 'result' in event_data:
                                        result = event_data['result']
                                        # Check if result contains actual data or follow-up questions
                                        if isinstance(result, dict) and 'content' in result:
                                            content = result['content']
                                            if isinstance(content, list) and len(content) > 0:
                                                first_content = content[0]
                                                if isinstance(first_content, dict) and 'text' in first_content:
                                                    text_content = first_content['text']
                                                    # Try to parse as JSON if it looks like JSON
                                                    try:
                                                        parsed_content = json.loads(text_content)
                                                        if 'followUpQuestion' in parsed_content:
                                                            # Handle follow-up questions by providing a default response
                                                            logger.info(f"Received follow-up question: {parsed_content['followUpQuestion']}")
                                                            return {
                                                                "success": False,
                                                                "error": f"Zapier requires more specific parameters. {parsed_content['followUpQuestion']}"
                                                            }
                                                        else:
                                                            return {
                                                                "success": True,
                                                                "data": parsed_content,
                                                                "tool_used": selected_tool['name']
                                                            }
                                                    except json.JSONDecodeError:
                                                        # Return text content as is
                                                        return {
                                                            "success": True,
                                                            "data": text_content,
                                                            "tool_used": selected_tool['name']
                                                        }
                                        
                                        return {
                                            "success": True,
                                            "data": result,
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
                # Check for 'results' key (Zapier MCP format)
                if 'results' in data:
                    raw_results = data['results']
                    
                    # Filter out Zapier status records that don't contain actual Salesforce data
                    if isinstance(raw_results, list):
                        for result in raw_results:
                            if isinstance(result, dict):
                                # Skip records that only contain Zapier status metadata
                                if ('_zap_search_was_found_status' in result and 
                                    len([k for k in result.keys() if not k.startswith('_zap')]) == 0):
                                    continue
                                # Include records that have actual Salesforce fields
                                if any(key in result for key in ['Id', 'Name', 'FirstName', 'LastName', 'Email', 'Account']):
                                    results.append(result)
                                # Include any record with substantive non-Zapier data
                                elif len([k for k in result.keys() if not k.startswith('_zap')]) > 0:
                                    results.append(result)
                    else:
                        results = raw_results
                        
                # Check for 'records' key (standard Salesforce format)
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
            
            # Log detailed parsing results for debugging
            logger.info(f"Parsed {len(results) if isinstance(results, list) else 0} valid Salesforce records from response")
            if isinstance(results, list) and len(results) == 0:
                logger.warning("No valid Salesforce records found in response - may indicate Zapier MCP connection issue")
            
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
        
        # Add original command to history
        assistant.add_to_history(command)
        
        # NLU Pre-processing: Transform raw query into optimized Zapier input
        logger.info(f"Processing raw query: {command}")
        optimized_command = assistant.get_optimized_zapier_input(command, assistant.available_zapier_tools)
        
        # Check if NLU couldn't understand the query
        if "I need more specific information" in optimized_command or "Could you specify" in optimized_command:
            return jsonify({
                'success': False,
                'error': optimized_command,
                'type': 'clarification_needed'
            })
        
        # Check if action requires confirmation
        requires_confirmation = any(keyword in optimized_command.lower() for keyword in ['create', 'update', 'delete', 'log'])
        
        if requires_confirmation and not data.get('confirmed', False):
            return jsonify({
                'success': True,
                'requires_confirmation': True,
                'command': command,
                'optimized_command': optimized_command,
                'message': f"You're about to perform the action: '{optimized_command}'. Are you sure you want to proceed?"
            })
        
        # Process the optimized command with Zapier MCP
        logger.info(f"Sending optimized command to Zapier: {optimized_command}")
        result = assistant.call_zapier_mcp(optimized_command)
        
        # Debug logging for Zapier response
        logger.info(f"Zapier response success: {result.get('success')}")
        if result.get('success'):
            logger.info(f"Zapier response data type: {type(result.get('data'))}")
            logger.info(f"Zapier response data preview: {str(result.get('data'))[:500]}...")
        
        if result['success']:
            parsed_data = assistant.parse_salesforce_data(result['data'])
            
            if parsed_data['parsed']:
                results = parsed_data['results']
                count = parsed_data['count']
                
                if count == 0:
                    return jsonify({
                        'success': True,
                        'message': f'No records found matching your query: "{command}". Try using broader search terms or check if the record exists in your Salesforce instance.',
                        'type': 'no_results',
                        'suggestion': 'Try searching with partial names or different field values.'
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