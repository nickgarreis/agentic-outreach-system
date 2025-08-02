# Disabling Vercel Git Integration

Since we're now using GitHub Actions to deploy with custom environment variable management (Option 3), you need to disable Vercel's automatic Git integration to prevent double deployments.

## Steps to Disable Vercel Git Integration:

1. **Go to your Vercel Dashboard**
   - Navigate to https://vercel.com/dashboard
   - Select your project

2. **Access Project Settings**
   - Click on the "Settings" tab
   - Navigate to "Git" in the left sidebar

3. **Disable Git Integration**
   - Find the "Connected Git Repository" section
   - Click "Disconnect" or "Manage Git Integration"
   - Confirm disconnection

4. **Alternative: Pause Deployments**
   If you want to keep the Git connection but prevent automatic deployments:
   - In the same Git settings page
   - Find "Ignored Build Step"
   - Add a command that always returns false: `exit 0`
   - Or find "Deploy Hooks" and disable automatic deployments

## Why This is Important:

- **Prevents Double Deployments**: Without disabling, both Vercel's automatic integration and our GitHub Actions workflow would trigger deployments
- **Cost Efficiency**: Avoids unnecessary build minutes and deployments
- **Single Source of Truth**: GitHub Actions becomes the only deployment method
- **Environment Variable Control**: Ensures environment variables are only set through our CLI method

## Verification:

After disabling:
1. Push a commit to the `main` branch
2. Check that only ONE deployment is triggered (via GitHub Actions)
3. Verify the deployment has the correct environment variables

## GitHub Secrets Required:

Make sure these secrets are added to your GitHub repository (Settings → Secrets → Actions):

- `VERCEL_TOKEN`: Your Vercel access token from https://vercel.com/account/tokens
- `VERCEL_ORG_ID`: Found in your Vercel project settings
- `VERCEL_PROJECT_ID`: Found in your Vercel project settings  
- `NEXT_PUBLIC_SUPABASE_URL`: https://dmfniygxoaijrnjornaq.supabase.co
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY`: sb_publishable_FRzSSp0eor3QnuvR1xm9Iw__MTjWqfx

## Deployment Command:

Our GitHub Actions workflow now uses this command to deploy with environment variables:

```bash
vercel deploy --prebuilt --prod \
  --token=${{ secrets.VERCEL_TOKEN }} \
  -e NEXT_PUBLIC_SUPABASE_URL="${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}" \
  -e NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY="${{ secrets.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY }}"
```

This gives us full control over which environment variables are deployed and when.