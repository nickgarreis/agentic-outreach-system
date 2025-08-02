# Frontend Deployment Guide

## Overview
This guide covers deploying the Agentic Outreach System frontend to production at nicode.co using Vercel.

## Prerequisites

1. **Vercel Account**
   - Sign up at https://vercel.com
   - Connect your GitHub account

2. **GitHub Repository**
   - Ensure code is pushed to GitHub
   - Main branch should be protected

3. **Domain Configuration**
   - Domain: nicode.co
   - DNS access for configuration

## Environment Variables

### Production Supabase Configuration
```
NEXT_PUBLIC_SUPABASE_URL=https://dmfniygxoaijrnjornaq.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=sb_publishable_FRzSSp0eor3QnuvR1xm9Iw__MTjWqfx
```

### Development Supabase Configuration
```
NEXT_PUBLIC_SUPABASE_URL=https://tqjyyedrazaimtujdjrw.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=sb_publishable_X80tZQGzoRlM6oIsqGLvhg_ZRKE1fMi
```

## Initial Vercel Setup

1. **Import Project**
   - Go to https://vercel.com/new
   - Import your GitHub repository
   - Select "frontend" as the root directory

2. **Configure Build Settings**
   - Framework Preset: Next.js
   - Build Command: `npm run build`
   - Output Directory: `.next`
   - Install Command: `npm install`

3. **Set Environment Variables**
   - Add production environment variables in Vercel dashboard
   - Settings → Environment Variables
   - Add both NEXT_PUBLIC variables

4. **Configure Domain**
   - Go to Settings → Domains
   - Add nicode.co
   - Follow DNS configuration instructions

## Deployment Workflow

### Automatic Deployment (Recommended)
1. Make changes on `dev` branch
2. Create PR to `main` branch
3. GitHub Actions runs checks
4. Merge PR after approval
5. Vercel automatically deploys

### Manual Deployment
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy to production
cd frontend
vercel --prod
```

## GitHub Actions Secrets

Add these secrets to your GitHub repository:
- `VERCEL_TOKEN`: Get from https://vercel.com/account/tokens
- `VERCEL_ORG_ID`: Found in Vercel project settings
- `VERCEL_PROJECT_ID`: Found in Vercel project settings
- `NEXT_PUBLIC_SUPABASE_URL`: Production Supabase URL
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY`: Production key

## Monitoring & Maintenance

### Health Checks
- Monitor at: https://vercel.com/[your-org]/[project]/analytics
- Set up uptime monitoring for nicode.co
- Check Supabase dashboard for API usage

### Performance
- Use Vercel Analytics for performance metrics
- Monitor Core Web Vitals
- Check bundle size with `npm run analyze`

### Troubleshooting

#### Build Failures
1. Check GitHub Actions logs
2. Verify environment variables
3. Test build locally: `npm run build`

#### 404 Errors
1. Check route configuration
2. Verify middleware.ts is working
3. Check Vercel function logs

#### Authentication Issues
1. Verify Supabase keys match environment
2. Check Supabase project status
3. Review middleware authentication logic

## Rollback Procedure

If issues occur after deployment:

1. **Immediate Rollback**
   - Go to Vercel dashboard
   - Click on deployment history
   - Select previous working deployment
   - Click "Promote to Production"

2. **Git Rollback**
   ```bash
   git revert HEAD
   git push origin main
   ```

## Security Checklist

- [ ] Environment variables set correctly
- [ ] Production keys not in code
- [ ] HTTPS enforced
- [ ] Security headers configured
- [ ] Rate limiting enabled on Supabase
- [ ] RLS policies active on all tables

## Next Steps After Deployment

1. **Verify Deployment**
   - Visit https://nicode.co
   - Test login/registration
   - Check all pages load

2. **Configure Monitoring**
   - Set up Vercel Analytics
   - Configure error tracking
   - Set up uptime monitoring

3. **Update DNS**
   - Ensure A/CNAME records point to Vercel
   - Enable SSL certificate
   - Test www redirect

## Support

- Vercel Docs: https://vercel.com/docs
- Next.js Docs: https://nextjs.org/docs
- Supabase Docs: https://supabase.com/docs