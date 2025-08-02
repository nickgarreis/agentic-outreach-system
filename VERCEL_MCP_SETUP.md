# Vercel MCP Server Setup Instructions

## ✅ Configuration Complete!

I've successfully added the Vercel MCP server to your Claude configuration. Here's what you need to do next:

## 1. Restart Claude

You need to completely restart the Claude desktop app for the changes to take effect:
- Quit Claude completely (CMD+Q on macOS)
- Start Claude again

## 2. Start a New Conversation

After restarting Claude, start a fresh conversation. The Vercel MCP tools will be available.

## 3. First-Time Authentication

When you first use a Vercel MCP tool in the new conversation, you'll be prompted to authenticate:

1. Claude will show an authentication prompt
2. Click "Allow" to authorize the connection
3. You'll be redirected to Vercel's OAuth login
4. Sign in with your Vercel account
5. Authorize Claude to access your Vercel projects

## 4. Available Vercel MCP Tools

Once authenticated, I'll have access to tools that can:
- List all your Vercel projects
- Get project details (including project ID and organization ID)
- Manage deployments
- View deployment logs
- Search Vercel documentation
- And more!

## 5. Example Usage

In your next conversation, you can ask me to:
- "List all my Vercel projects"
- "Get the project ID for my frontend project"
- "Show me recent deployments"
- "Check deployment logs for errors"

## Configuration Details

The Vercel MCP server has been added to:
`/Users/nick/Library/Application Support/Claude/claude_desktop_config.json`

With the following configuration:
```json
"vercel": {
  "command": "npx",
  "args": [
    "-y",
    "mcp-remote",
    "https://mcp.vercel.com"
  ]
}
```

## Security Notes

- The Vercel MCP server uses OAuth for secure authentication
- Your credentials are never stored in the configuration
- Access can be revoked at any time from your Vercel account settings
- Only approved AI clients (like Claude) can connect to this server

## Troubleshooting

If the Vercel tools don't appear:
1. Make sure Claude was completely restarted
2. Check that the configuration file was saved correctly
3. Try starting a completely new conversation
4. Look for any error messages in Claude

## What This Replaces

With the Vercel MCP server, you no longer need to:
- Manually look up project IDs in `.vercel/project.json`
- Use the Vercel SDK to fetch IDs programmatically
- Copy/paste IDs from the Vercel dashboard

Everything can now be done directly through conversation!