# Agentic Outreach System - Frontend

Modern Next.js 15 frontend for the Agentic Outreach System, featuring AI-powered outreach automation with email and LinkedIn integration.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **Authentication**: Supabase Auth with SSR
- **State Management**: React hooks + Context API
- **API Client**: Custom fetch wrapper with token management

## Prerequisites

- Node.js 18+ and npm
- Backend API running on http://localhost:8000
- Supabase project configured

## Setup Instructions

1. **Install dependencies**:
```bash
npm install
```

2. **Configure environment variables**:
Create a `.env.local` file (already created) with:
```env
NEXT_PUBLIC_SUPABASE_URL=https://tqjyyedrazaimtujdjrw.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_X80tZQGzoRlM6oIsqGLvhg_ZRKE1fMi
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. **Start development server**:
```bash
npm run dev
```

The application will be available at http://localhost:3000 (or next available port).

## Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── (auth)/            # Auth routes (login, register)
│   ├── (dashboard)/       # Protected dashboard routes
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Landing page
├── components/            # React components
│   └── ui/                # shadcn/ui components
├── lib/                   # Utilities and clients
│   ├── api/               # API client modules
│   └── supabase/          # Supabase clients
├── types/                 # TypeScript type definitions
└── public/                # Static assets
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Check TypeScript types

## Features Implemented

### Authentication
- Email/password login with JWT tokens
- User registration with email verification
- Protected routes with middleware
- Automatic token refresh

### Dashboard
- Overview metrics and statistics
- Campaign management (list, create, edit)
- Lead management
- Message tracking
- Responsive sidebar navigation

### API Integration
- Type-safe API client
- Automatic token management
- Error handling and retries
- Request/response interceptors

## Development Guidelines

### Code Style
- Use TypeScript strict mode
- Follow React best practices
- Keep components small and focused
- Use proper error boundaries

### State Management
- Use React hooks for local state
- Context API for global state
- Server state with API client

### Performance
- Use React Server Components where possible
- Implement proper loading states
- Optimize images with Next.js Image
- Code split with dynamic imports

## Deployment

### Vercel (Recommended)
1. Push to GitHub
2. Import project to Vercel
3. Configure environment variables
4. Deploy

### Self-hosted
1. Build the application:
```bash
npm run build
```

2. Start production server:
```bash
npm start
```

## Contributing

1. Create feature branch from `dev`
2. Make changes following code style
3. Test thoroughly
4. Create pull request

## Troubleshooting

### Port already in use
The dev server will automatically use the next available port if 3000 is taken.

### Authentication issues
- Verify Supabase keys are correct
- Check backend API is running
- Clear browser localStorage

### Build errors
- Run `npm run type-check` to find TypeScript issues
- Check all environment variables are set
- Ensure Node.js version is 18+# Deploy to production
