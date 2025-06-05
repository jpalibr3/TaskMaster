# Replit Project: OpenAI to Zapier MCP for Salesforce Interaction

This project enables you to send natural language commands from a Python script in Replit to your Zapier MCP (Meta-Call Protocol) server. Zapier then interprets these commands and performs actions on your connected Salesforce account.

## Setup Steps:

### 1. Replit Secrets Configuration:
Navigate to the "Secrets" tab (look for a padlock icon on the left sidebar in your Replit workspace). You **must** add the following secrets:

- Key: `OPENAI_API_KEY`
  Value: Your_Actual_OpenAI_API_Key_Here

- Key: `ZAPIER_MCP_SERVER_URL`
  Value: Your_Zapier_Provided_MCP_Server_URL
  (Example from Zapier setup: `https://mcp.zapier.com/api/mcp/mcp` or a more specific one like `https://mcp.zapier.com/api/mcp/s/your-unique-id/mcp`)

- Key: `ZAPIER_MCP_API_KEY`
  Value: Your_Zapier_Provided_MCP_API_Key_Bearer_Token
  (This is the API Key/Bearer token shown in your Zapier MCP setup page for OpenAI)

**CRITICAL:** Replace the placeholder values with your actual credentials. The script will not work without these.

### 2. Python Package Installation:
The `openai` library is required. The `pyproject.toml` file is configured for Replit's Python (Poetry) environment. Replit should automatically detect this and install the package when you run the application. If you encounter issues, you can manually install via the Replit Shell: `pip install openai` or `poetry add openai`.

### 3. Running the Application:
- After setting secrets and ensuring `main.py` and `pyproject.toml` are populated, click the main "Run" button at the top of the Replit interface.
- Alternatively, you can open the "Shell" tab and execute `python main.py`.
- The script will ask for your command to send to Salesforce via Zapier.

### 4. Zapier MCP & Salesforce Configuration:
- This script assumes your Zapier account is already connected to your Salesforce account.
- The effectiveness of your commands depends on the Salesforce actions Zapier has exposed via its MCP interface and how well Zapier's AI can interpret your natural language commands.
- Experiment with phrasing for your commands to achieve the desired Salesforce actions.

## Example Commands:
- 'Find Salesforce contact with email team@example.com'
- 'Create a new Salesforce lead: Name Test Lead, Email test.lead@example.com, Company Test Inc.'
- 'Update Salesforce opportunity My Big Deal stage to Closed Won'
- 'List all open opportunities in Salesforce'
- 'Create a Salesforce task: Follow up with lead John Doe'

## Troubleshooting:
- Verify all API keys and the Zapier MCP URL in Replit Secrets are correct
- Ensure your OpenAI account has sufficient credits/quota
- Check that the Zapier MCP integration for Salesforce is active and correctly set up in your Zapier account
- The command you provided might not be understood by Zapier or may not correspond to a configured action
