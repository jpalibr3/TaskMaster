import os
import json
import logging
import requests
from openai import OpenAI

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_environment():
    """
    Validates that all required environment variables are set.
    Returns tuple of (success: bool, missing_vars: list)
    """
    required_vars = ['OPENAI_API_KEY', 'ZAPIER_MCP_SERVER_URL', 'ZAPIER_MCP_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars

def display_welcome_message():
    """Displays welcome message and usage examples to the user."""
    print("\n" + "="*60)
    print("🚀 Salesforce Command Center (via Zapier MCP)")
    print("="*60)
    print("Describe the action you want to perform in Salesforce using natural language.")
    print("\n📋 Example commands:")
    print("  • 'Find Salesforce contact with email team@example.com'")
    print("  • 'Create a new Salesforce lead: Name Test Lead, Email test.lead@example.com, Company Test Inc.'")
    print("  • 'Update Salesforce opportunity My Big Deal stage to Closed Won'")
    print("  • 'List all open opportunities in Salesforce'")
    print("  • 'Create a Salesforce task: Follow up with lead John Doe'")
    print("="*60)

def get_user_command():
    """
    Prompts user for Salesforce command and validates input.
    Returns the command string or None if invalid.
    """
    try:
        command = input("\n> What would you like to do in Salesforce? ").strip()
        
        if not command:
            print("❌ No command provided. Please enter a valid command.")
            return None
            
        if len(command) < 5:
            print("❌ Command too short. Please provide a more detailed command.")
            return None
            
        return command
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        return None
    except Exception as e:
        print(f"❌ Error reading input: {e}")
        return None

def call_zapier_mcp_via_openai(client, command, zapier_mcp_url, zapier_mcp_api_key):
    """
    Calls Zapier MCP via OpenAI chat completions with function calling.
    Returns the response or raises an exception.
    """
    logger.info(f"Sending command to Zapier MCP: {command}")
    logger.info(f"Using Zapier MCP Server URL: {zapier_mcp_url}")
    
    # Create a system message that instructs the AI to use the Zapier MCP tool
    system_message = """You are an AI assistant that helps users interact with Salesforce through Zapier's MCP integration. 
    When a user provides a Salesforce command, you should use the zapier_mcp_tool to execute the action.
    Always provide clear feedback about what action was attempted and the results."""
    
    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
    # do not change this unless explicitly requested by the user
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Please execute this Salesforce command via Zapier MCP: {command}"}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "zapier_mcp_tool",
                        "description": "Execute Salesforce actions via Zapier MCP integration",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "The Salesforce action to perform"
                                },
                                "parameters": {
                                    "type": "object",
                                    "description": "Parameters for the Salesforce action"
                                }
                            },
                            "required": ["action"]
                        }
                    }
                }
            ],
            tool_choice="auto"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise

def call_zapier_mcp_directly(action, parameters, zapier_mcp_url, zapier_mcp_api_key):
    """
    Makes actual HTTP request to Zapier MCP server.
    """
    logger.info(f"Calling Zapier MCP - Action: {action}, Parameters: {parameters}")
    
    try:
        headers = {
            "Authorization": f"Bearer {zapier_mcp_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        # First, let's discover what tools are available
        tools_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        
        logger.info("Discovering available Zapier MCP tools...")
        tools_response = requests.post(zapier_mcp_url, headers=headers, json=tools_payload, timeout=30)
        
        logger.info(f"Tools response status: {tools_response.status_code}")
        logger.info(f"Tools response headers: {tools_response.headers}")
        logger.info(f"Tools response text: {tools_response.text}")
        
        if tools_response.status_code == 200:
            try:
                tools_data = tools_response.json()
                logger.info(f"Available tools: {tools_data}")
            except Exception as e:
                logger.error(f"Failed to parse tools response as JSON: {e}")
                return {
                    "success": False,
                    "action": action,
                    "message": f"Failed to parse Zapier MCP response: {e}",
                    "data": {"response_text": tools_response.text, "status_code": tools_response.status_code}
                }
            
            # Try to find a suitable tool for the action
            if 'result' in tools_data and 'tools' in tools_data['result']:
                available_tools = tools_data['result']['tools']
                tool_names = [tool.get('name', 'unknown') for tool in available_tools]
                logger.info(f"Tool names: {tool_names}")
                
                # Use the first available tool that seems related to Salesforce
                salesforce_tool = None
                for tool in available_tools:
                    tool_name = tool.get('name', '').lower()
                    if 'salesforce' in tool_name or 'search' in tool_name or 'find' in tool_name:
                        salesforce_tool = tool
                        break
                
                if not salesforce_tool and available_tools:
                    salesforce_tool = available_tools[0]  # Use first available tool
                
                if salesforce_tool:
                    tool_name = salesforce_tool.get('name')
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": {
                                "instructions": action
                            }
                        }
                    }
                else:
                    return {
                        "success": False,
                        "action": action,
                        "message": f"No suitable Salesforce tools found. Available tools: {tool_names}",
                        "data": tools_data
                    }
            else:
                return {
                    "success": False,
                    "action": action,
                    "message": f"Could not retrieve tools list: {tools_data}",
                    "data": tools_data
                }
        else:
            logger.error(f"Tools list request failed: {tools_response.status_code} - {tools_response.text}")
            # Fallback to a generic approach
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "natural_language_action",
                    "arguments": {
                        "instructions": action
                    }
                }
            }
        
        logger.info(f"Making request to {zapier_mcp_url}")
        response = requests.post(zapier_mcp_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result_data = response.json()
            return {
                "success": True,
                "action": action,
                "message": "Successfully retrieved data from Salesforce via Zapier MCP",
                "data": result_data
            }
        else:
            logger.error(f"Zapier MCP request failed: {response.status_code} - {response.text}")
            return {
                "success": False,
                "action": action,
                "message": f"Zapier MCP request failed: {response.status_code} - {response.text}",
                "data": None
            }
            
    except requests.exceptions.Timeout:
        logger.error("Zapier MCP request timed out")
        return {
            "success": False,
            "action": action,
            "message": "Request to Zapier MCP timed out",
            "data": None
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Zapier MCP request error: {e}")
        return {
            "success": False,
            "action": action,
            "message": f"Request error: {e}",
            "data": None
        }
    except Exception as e:
        logger.error(f"Unexpected error calling Zapier MCP: {e}")
        return {
            "success": False,
            "action": action,
            "message": f"Unexpected error: {e}",
            "data": None
        }

def process_openai_response(response):
    """
    Processes the OpenAI response and handles tool calls.
    Returns formatted result for display.
    """
    try:
        message = response.choices[0].message
        
        # Check if there are tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            results = []
            for tool_call in message.tool_calls:
                if tool_call.function.name == "zapier_mcp_tool":
                    # Parse the function arguments
                    args = json.loads(tool_call.function.arguments)
                    action = args.get("action", "unknown")
                    parameters = args.get("parameters", {})
                    
                    # Make actual call to Zapier MCP
                    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
                    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
                    mcp_result = call_zapier_mcp_directly(action, parameters, zapier_mcp_url, zapier_mcp_api_key)
                    results.append(mcp_result)
            
            return results
        else:
            # No tool calls, return the message content
            return [{"message": message.content, "type": "text_response"}]
            
    except Exception as e:
        logger.error(f"Error processing OpenAI response: {e}")
        return [{"error": str(e), "type": "error"}]

def display_results(results):
    """Displays the results from Zapier MCP operations."""
    print("\n" + "🔄 Response from Zapier MCP (via OpenAI)".center(60, "-"))
    
    for i, result in enumerate(results, 1):
        if result.get("type") == "error":
            print(f"❌ Error {i}: {result.get('error', 'Unknown error')}")
        elif result.get("type") == "text_response":
            print(f"💬 Response {i}: {result.get('message', 'No message')}")
        else:
            print(f"✅ Result {i}:")
            if result.get("success"):
                print(f"   Action: {result.get('action', 'Unknown')}")
                print(f"   Status: {result.get('message', 'Completed successfully')}")
                if result.get("data"):
                    print(f"   Data: {json.dumps(result.get('data'), indent=4)}")
            else:
                print(f"   ❌ Failed: {result.get('message', 'Unknown error')}")
    
    print("-" * 60)

def display_troubleshooting_help():
    """Displays troubleshooting information for common issues."""
    print("\n🔧 Troubleshooting suggestions:")
    print("  • Verify all API keys and the Zapier MCP URL in Replit Secrets are correct")
    print("  • Ensure your OpenAI account has sufficient credits/quota")
    print("  • Check that the Zapier MCP integration for Salesforce is active in your Zapier account")
    print("  • Try rephrasing your command - be more specific about the action you want")
    print("  • Ensure your Salesforce account is properly connected to Zapier")
    print("  • Check Zapier logs for any integration errors")

def run_salesforce_command_via_zapier_mcp():
    """
    Main function that orchestrates the entire process:
    1. Validates environment
    2. Initializes OpenAI client
    3. Gets user input
    4. Calls OpenAI with Zapier MCP integration
    5. Displays results
    """
    
    # Validate environment variables
    env_valid, missing_vars = validate_environment()
    if not env_valid:
        print("❌ Missing required environment variables in Replit Secrets:")
        for var in missing_vars:
            print(f"   • {var}")
        print("\nPlease check the 'Secrets' tab in your Replit workspace and add the missing variables.")
        return

    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set in Replit Secrets.")
        return

    # Get Zapier MCP configuration
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")

    # Display welcome message
    display_welcome_message()

    # Main interaction loop
    while True:
        try:
            # Get user command
            command = get_user_command()
            if command is None:
                break

            print(f"\n🚀 Processing command: '{command}'")
            
            # Call OpenAI with Zapier MCP integration
            response = call_zapier_mcp_via_openai(
                client, command, zapier_mcp_url, zapier_mcp_api_key
            )
            
            # Process and display results
            results = process_openai_response(response)
            display_results(results)

            # Ask if user wants to continue
            print("\n" + "="*60)
            continue_choice = input("Would you like to run another command? (y/n): ").strip().lower()
            if continue_choice not in ['y', 'yes']:
                print("👋 Goodbye!")
                break

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"\n❌ An error occurred: {e}")
            display_troubleshooting_help()
            
            # Ask if user wants to try again
            retry_choice = input("\nWould you like to try again? (y/n): ").strip().lower()
            if retry_choice not in ['y', 'yes']:
                break

if __name__ == "__main__":
    run_salesforce_command_via_zapier_mcp()
