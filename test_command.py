#!/usr/bin/env python3
"""
Test script to run a single Salesforce command via the main application.
This bypasses the interactive loop for testing purposes.
"""

import os
import sys
from main import (
    validate_environment, 
    call_zapier_mcp_via_openai, 
    process_openai_response, 
    display_results,
    display_troubleshooting_help
)
from openai import OpenAI

def test_salesforce_command(command):
    """
    Test a single Salesforce command without interactive input.
    """
    print(f"Testing command: '{command}'")
    print("=" * 60)
    
    # Validate environment variables
    env_valid, missing_vars = validate_environment()
    if not env_valid:
        print("❌ Missing required environment variables in Replit Secrets:")
        for var in missing_vars:
            print(f"   • {var}")
        return False

    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        print("✅ OpenAI client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")
        return False

    # Get Zapier MCP configuration
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
    
    print(f"🚀 Processing command: '{command}'")
    
    try:
        # Call OpenAI with Zapier MCP integration
        response = call_zapier_mcp_via_openai(
            client, command, zapier_mcp_url, zapier_mcp_api_key
        )
        
        # Process and display results
        results = process_openai_response(response)
        display_results(results)
        
        return True
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        display_troubleshooting_help()
        return False

if __name__ == "__main__":
    # Use command line argument or default test command
    if len(sys.argv) > 1:
        test_command = " ".join(sys.argv[1:])
    else:
        test_command = "Find all accounts that have Zapier in the account name"
    
    success = test_salesforce_command(test_command)
    sys.exit(0 if success else 1)