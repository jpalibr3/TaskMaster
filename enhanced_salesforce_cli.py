#!/usr/bin/env python3
"""
Enhanced Salesforce AI Assistant
A conversational CLI tool for interacting with Salesforce via Zapier MCP and OpenAI
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration for primary fields display
PRIMARY_CONTACT_FIELDS = ['Id', 'Name', 'FirstName', 'LastName', 'Email', 'Phone', 'MobilePhone', 'Title', 'AccountId']
PRIMARY_ACCOUNT_FIELDS = ['Id', 'Name', 'Type', 'Industry', 'Phone', 'Website', 'BillingCity', 'BillingState']
PRIMARY_OPPORTUNITY_FIELDS = ['Id', 'Name', 'StageName', 'Amount', 'CloseDate', 'AccountId', 'OwnerId']
PRIMARY_LEAD_FIELDS = ['Id', 'Name', 'FirstName', 'LastName', 'Email', 'Phone', 'Company', 'Status']

class SalesforceAIAssistant:
    def __init__(self):
        self.client = None
        self.zapier_mcp_url = None
        self.zapier_mcp_api_key = None
        self.command_history = []
        self.max_history = 10
        self.current_record = None
        self.current_records = []
        
    def validate_environment(self) -> tuple[bool, List[str]]:
        """Validate required environment variables."""
        required_vars = ['OPENAI_API_KEY', 'ZAPIER_MCP_SERVER_URL', 'ZAPIER_MCP_API_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        return len(missing_vars) == 0, missing_vars
    
    def initialize_clients(self) -> bool:
        """Initialize OpenAI client and Zapier MCP configuration."""
        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
            self.zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize clients: {e}")
            return False
    
    def greet_user(self):
        """Display welcome message and instructions."""
        print("\n" + "="*60)
        print("🤖 Salesforce AI Assistant")
        print("="*60)
        print("Hello! I'm your Salesforce AI Assistant. How can I assist you today?")
        print("\nCommands you can use:")
        print("  • Type natural language requests (e.g., 'find contacts at Acme Corp')")
        print("  • /quit, /exit, /bye - Exit the assistant")
        print("  • /history - View command history")
        print("  • /run <number> - Re-execute a command from history")
        print("="*60)
    
    def get_user_input(self, prompt: str = "➡️ You: ") -> str:
        """Get user input with consistent formatting."""
        try:
            return input(prompt).strip()
        except KeyboardInterrupt:
            return "/quit"
        except Exception:
            return ""
    
    def add_to_history(self, command: str):
        """Add command to history, maintaining max size."""
        if command and not command.startswith('/'):
            self.command_history.append(command)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
    
    def display_history(self):
        """Display command history."""
        if not self.command_history:
            print("🤖 Salesforce AI: No command history available.")
            return
        
        print("🤖 Salesforce AI: --- Command History ---")
        for i, cmd in enumerate(self.command_history, 1):
            print(f"                 {i}. {cmd}")
        print("                 (Enter '/run <number>' to re-execute, or type your next command)")
    
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
            # Generic primary fields
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
    
    def display_single_record(self, record: Dict, show_all: bool = False):
        """Display a single Salesforce record with formatting."""
        record_type = self.detect_record_type(record)
        record_name = record.get('Name') or f"{record.get('FirstName', '')} {record.get('LastName', '')}".strip() or record.get('Id', 'Unknown')
        
        print(f"\n🤖 Salesforce AI: === Record Details for {record_name} ===")
        
        # Display primary fields
        primary_fields = self.get_primary_fields(record)
        displayed_fields = set()
        
        for field in primary_fields:
            value = record.get(field)
            if value is not None and value != '':
                formatted_field = self.format_field_name(field)
                print(f"                 {formatted_field:<15} {value}")
                displayed_fields.add(field)
        
        # Show all other fields if requested
        if show_all:
            print(f"                 \n                 --- Additional Details ---")
            for field, value in record.items():
                if field not in displayed_fields and value is not None and value != '':
                    if not field.startswith('_') and field != 'attributes':
                        formatted_field = self.format_field_name(field)
                        print(f"                 {formatted_field:<15} {value}")
        
        self.current_record = record
    
    def format_field_name(self, field: str) -> str:
        """Format field names for better display."""
        # Common field name mappings
        field_mappings = {
            'Id': 'Salesforce ID:',
            'FirstName': 'First Name:',
            'LastName': 'Last Name:',
            'Email': 'Email Address:',
            'Phone': 'Phone:',
            'MobilePhone': 'Mobile Phone:',
            'AccountId': 'Account ID:',
            'BillingCity': 'Billing City:',
            'BillingState': 'Billing State:',
            'StageName': 'Stage:',
            'CloseDate': 'Close Date:',
            'OwnerId': 'Owner ID:'
        }
        
        return field_mappings.get(field, f"{field}:")
    
    def display_multiple_records(self, records: List[Dict]):
        """Display multiple records with selection option."""
        print(f"\n🤖 Salesforce AI: I found {len(records)} records matching your query:")
        
        for i, record in enumerate(records, 1):
            name = record.get('Name') or f"{record.get('FirstName', '')} {record.get('LastName', '')}".strip()
            email = record.get('Email', '')
            record_id = record.get('Id', '')
            
            if email:
                print(f"                 {i}. {name} ({email}, ID: {record_id[:8]}...)")
            else:
                print(f"                 {i}. {name} (ID: {record_id[:8]}...)")
        
        print("                 Enter the number of the record you're interested in, or type '/new' for a new search.")
        
        self.current_records = records
    
    def handle_record_selection(self, selection: str) -> bool:
        """Handle user selection from multiple records."""
        if selection == '/new':
            return True
        
        try:
            index = int(selection) - 1
            if 0 <= index < len(self.current_records):
                selected_record = self.current_records[index]
                self.display_single_record(selected_record)
                
                # Ask for more details
                show_more = self.get_user_input("\n✨ Want to see all other available (non-null) details for this record? (yes/no): ")
                if show_more.lower() in ['yes', 'y']:
                    self.display_single_record(selected_record, show_all=True)
                
                # Offer contextual follow-ups
                self.offer_follow_ups()
                return True
            else:
                print("🤖 Salesforce AI: Invalid selection. Please try again.")
                return False
        except ValueError:
            print("🤖 Salesforce AI: Please enter a valid number or '/new'.")
            return False
    
    def offer_follow_ups(self):
        """Offer contextual follow-up actions based on current record."""
        if not self.current_record:
            return
        
        record_type = self.detect_record_type(self.current_record)
        record_name = self.current_record.get('Name') or f"{self.current_record.get('FirstName', '')} {self.current_record.get('LastName', '')}".strip()
        
        print(f"\n🤖 Salesforce AI: What would you like to do next with {record_name}?")
        
        if record_type == 'Contact':
            print("                 1. Log a call for this contact")
            print("                 2. Create a follow-up task for this contact")
            print("                 3. View linked Account details")
            print("                 4. Start a new search")
        elif record_type == 'Account':
            print("                 1. Find contacts at this account")
            print("                 2. View opportunities for this account")
            print("                 3. Log an activity for this account")
            print("                 4. Start a new search")
        elif record_type == 'Opportunity':
            print("                 1. Update opportunity stage")
            print("                 2. Log activity for this opportunity")
            print("                 3. View related account")
            print("                 4. Start a new search")
        else:
            print("                 1. Create a related task")
            print("                 2. Update this record")
            print("                 3. Start a new search")
        
        print("                 (Enter number, or type '/quit')")
        
        follow_up = self.get_user_input()
        if follow_up in ['1', '2', '3']:
            self.handle_follow_up_action(follow_up, record_type)
        elif follow_up == '4':
            return
        elif follow_up.lower() in ['/quit', '/exit', '/bye']:
            return '/quit'
    
    def handle_follow_up_action(self, action: str, record_type: str):
        """Handle follow-up actions based on user selection."""
        record_name = self.current_record.get('Name') or f"{self.current_record.get('FirstName', '')} {self.current_record.get('LastName', '')}".strip()
        record_id = self.current_record.get('Id', '')
        
        if record_type == 'Contact':
            if action == '1':  # Log a call
                details = self.get_user_input("Please enter details for the call with {}: ".format(record_name))
                if details:
                    command = f"Log a call for Salesforce contact {record_name} (ID: {record_id}) regarding: {details}"
                    self.process_action_with_confirmation(command)
            elif action == '2':  # Create task
                task_details = self.get_user_input("Please enter task details for {}: ".format(record_name))
                if task_details:
                    command = f"Create a follow-up task for Salesforce contact {record_name} (ID: {record_id}): {task_details}"
                    self.process_action_with_confirmation(command)
            elif action == '3':  # View account
                account_id = self.current_record.get('AccountId')
                if account_id:
                    command = f"Find Salesforce account with ID {account_id}"
                    self.process_command(command)
        
        elif record_type == 'Account':
            if action == '1':  # Find contacts
                command = f"Find all contacts at Salesforce account {record_name}"
                self.process_command(command)
            elif action == '2':  # View opportunities
                command = f"Find all opportunities for Salesforce account {record_name}"
                self.process_command(command)
            elif action == '3':  # Log activity
                activity_details = self.get_user_input("Please enter activity details for {}: ".format(record_name))
                if activity_details:
                    command = f"Log activity for Salesforce account {record_name} (ID: {record_id}): {activity_details}"
                    self.process_action_with_confirmation(command)
    
    def process_action_with_confirmation(self, command: str) -> bool:
        """Process action that requires confirmation."""
        print(f"\n❗ You're about to perform the action: '{command}'. Are you sure you want to proceed? (yes/no)")
        confirmation = self.get_user_input()
        
        if confirmation.lower() in ['yes', 'y']:
            print("✅ Action Confirmed! Processing...")
            return self.process_command(command)
        else:
            print("🤖 Salesforce AI: Action cancelled.")
            return False
    
    def save_record_to_file(self):
        """Save current record details to file."""
        if not self.current_record:
            print("🤖 Salesforce AI: No record to save.")
            return
        
        # Generate default filename
        record_name = self.current_record.get('Name') or f"{self.current_record.get('FirstName', '')} {self.current_record.get('LastName', '')}".strip()
        safe_name = "".join(c for c in record_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{safe_name}_{timestamp}.txt".replace(' ', '_')
        
        filename = self.get_user_input(f"Please enter a filename (default: {default_filename}): ")
        if not filename:
            filename = default_filename
        
        if not filename.endswith('.txt'):
            filename += '.txt'
        
        try:
            with open(filename, 'w') as f:
                f.write(f"Salesforce Record Export\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*50 + "\n\n")
                
                record_type = self.detect_record_type(self.current_record)
                f.write(f"Record Type: {record_type}\n\n")
                
                # Write all non-null fields
                for field, value in self.current_record.items():
                    if value is not None and value != '' and not field.startswith('_') and field != 'attributes':
                        f.write(f"{field}: {value}\n")
            
            print(f"💾 Details saved to {filename}.")
            
        except Exception as e:
            print(f"❌ Error saving file: {e}")
    
    def process_command(self, command: str) -> bool:
        """Process a user command and return success status."""
        if not command:
            return True
        
        # Handle special commands
        if command.lower() in ['/quit', '/exit', '/bye']:
            return False
        
        if command == '/history':
            self.display_history()
            return True
        
        if command.startswith('/run '):
            try:
                history_index = int(command[5:]) - 1
                if 0 <= history_index < len(self.command_history):
                    old_command = self.command_history[history_index]
                    print(f"🤖 Salesforce AI: Re-executing: {old_command}")
                    return self.process_command(old_command)
                else:
                    print("🤖 Salesforce AI: Invalid history index.")
                    return True
            except ValueError:
                print("🤖 Salesforce AI: Invalid command format. Use '/run <number>'.")
                return True
        
        # Add to history
        self.add_to_history(command)
        
        # Check if action requires confirmation
        if any(keyword in command.lower() for keyword in ['create', 'update', 'delete', 'log']):
            return self.process_action_with_confirmation(command)
        
        # Regular command processing
        print("🔍 Searching Salesforce for your request...")
        
        try:
            result = self.call_zapier_mcp(command)
            
            if result['success']:
                parsed_data = self.parse_salesforce_data(result['data'])
                
                if parsed_data['parsed']:
                    results = parsed_data['results']
                    count = parsed_data['count']
                    
                    if count == 0:
                        print("🤖 Salesforce AI: No records found matching your query.")
                    elif count == 1:
                        self.display_single_record(results[0] if isinstance(results, list) else results)
                        
                        # Ask for more details
                        show_more = self.get_user_input("\n✨ Want to see all other available (non-null) details for this record? (yes/no): ")
                        if show_more.lower() in ['yes', 'y']:
                            self.display_single_record(results[0] if isinstance(results, list) else results, show_all=True)
                        
                        # Offer to save
                        save_option = self.get_user_input("\n💾 Would you like to save these details to a file? (yes/no): ")
                        if save_option.lower() in ['yes', 'y']:
                            self.save_record_to_file()
                        
                        # Offer follow-ups
                        follow_up_result = self.offer_follow_ups()
                        if follow_up_result == '/quit':
                            return False
                    else:
                        self.display_multiple_records(results)
                        
                        # Handle record selection
                        while True:
                            selection = self.get_user_input()
                            if selection.lower() in ['/quit', '/exit', '/bye']:
                                return False
                            if self.handle_record_selection(selection):
                                break
                else:
                    print(f"🤖 Salesforce AI: Received response from Salesforce:")
                    print(f"                 {parsed_data.get('raw_data', 'No data')}")
            else:
                print(f"❌ Error: {result['error']}")
                
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            logger.error(f"Command processing error: {e}")
        
        return True
    
    def run(self):
        """Main application loop."""
        # Validate environment
        env_valid, missing_vars = self.validate_environment()
        if not env_valid:
            print("❌ Missing required environment variables:")
            for var in missing_vars:
                print(f"   • {var}")
            print("\nPlease configure these in your Replit Secrets.")
            return
        
        # Initialize clients
        if not self.initialize_clients():
            return
        
        # Greet user
        self.greet_user()
        
        # Main conversation loop
        while True:
            print()  # Blank line for spacing
            user_input = self.get_user_input()
            
            if not self.process_command(user_input):
                break
        
        print("\n🤖 Salesforce AI: Goodbye! Hope I was helpful today.")

if __name__ == "__main__":
    assistant = SalesforceAIAssistant()
    assistant.run()