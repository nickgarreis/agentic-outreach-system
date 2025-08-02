# Pre-Deployment Checklist

## Before Merging to Main

### Code Quality
- [ ] All TypeScript errors resolved (`npm run type-check`)
- [ ] Build succeeds locally (`npm run build`)
- [ ] No console errors in browser
- [ ] All features tested on localhost:3002

### Supabase Configuration
- [ ] Production database has all required tables
- [ ] Migrations synced between dev and production
- [ ] RLS policies configured on production tables
- [ ] Production keys are different from development

### Environment Setup
- [ ] `.env.production` file created (not committed)
- [ ] Vercel has production environment variables
- [ ] GitHub secrets configured for Actions

### Testing
- [ ] Authentication flow works (register/login/logout)
- [ ] Protected routes redirect properly
- [ ] Database queries return expected data
- [ ] No hardcoded development URLs

### Security
- [ ] No secrets in code
- [ ] API keys use environment variables
- [ ] CORS configured properly
- [ ] Security headers in next.config.js

## Deployment Steps

1. **Final Local Test**
   ```bash
   npm run build
   npm run start
   # Test on http://localhost:3000
   ```

2. **Create Pull Request**
   - From: `dev` branch
   - To: `main` branch
   - Wait for GitHub Actions checks

3. **Merge & Deploy**
   - Merge PR after approval
   - Monitor Vercel deployment
   - Check deployment logs

4. **Post-Deployment Verification**
   - [ ] Site loads at nicode.co
   - [ ] SSL certificate active
   - [ ] Login with test account works
   - [ ] Check browser console for errors
   - [ ] Verify data loads from production Supabase

## Emergency Contacts

- Vercel Status: https://www.vercel-status.com/
- Supabase Status: https://status.supabase.com/
- Domain Registrar: [Your registrar support]

## Rollback Commands

```bash
# If deployment fails
vercel rollback

# If code has issues
git revert HEAD
git push origin main
```

Remember: Always test thoroughly before deploying!