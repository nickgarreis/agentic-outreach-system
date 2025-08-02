#!/bin/bash
# Script to get Vercel project and organization IDs
# Run this after you've authenticated with `vercel login`

echo "Getting Vercel project information..."
echo ""

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend" || exit 1

# Check if already linked
if [ -f ".vercel/project.json" ]; then
    echo "✅ Project already linked!"
    echo ""
    echo "Project Information:"
    echo "==================="
    cat .vercel/project.json | jq '.'
    echo ""
    echo "IDs for GitHub Secrets:"
    echo "======================"
    echo "VERCEL_ORG_ID=$(cat .vercel/project.json | jq -r '.orgId')"
    echo "VERCEL_PROJECT_ID=$(cat .vercel/project.json | jq -r '.projectId')"
else
    echo "❌ Project not linked yet."
    echo ""
    echo "To link your project:"
    echo "1. Run: vercel login"
    echo "2. Run: vercel link"
    echo "3. Run this script again"
fi