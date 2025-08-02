// app/(dashboard)/layout.tsx
// Dashboard layout with sidebar navigation
// Protected route that requires authentication
// RELEVANT FILES: ../../components/dashboard/sidebar.tsx, ../../middleware.ts

import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { 
  LayoutDashboard, 
  Users, 
  Mail, 
  Settings,
  LogOut,
  Target
} from 'lucide-react'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Check authentication server-side
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Campaigns', href: '/dashboard/campaigns', icon: Target },
    { name: 'Leads', href: '/dashboard/leads', icon: Users },
    { name: 'Messages', href: '/dashboard/messages', icon: Mail },
    { name: 'Settings', href: '/dashboard/settings', icon: Settings },
  ]

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <div className="w-64 bg-card border-r">
        <div className="h-full flex flex-col">
          {/* Logo */}
          <div className="p-6 border-b">
            <Link href="/dashboard" className="text-xl font-bold">
              Agentic Outreach
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {navigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            ))}
          </nav>

          {/* User section */}
          <div className="p-4 border-t">
            <div className="flex items-center gap-3 px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {user.email}
                </p>
                <p className="text-xs text-muted-foreground">
                  {user.id.slice(0, 8)}...
                </p>
              </div>
              <button className="text-muted-foreground hover:text-foreground">
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b bg-background">
          <div className="h-full px-6 flex items-center justify-between">
            <h1 className="text-2xl font-semibold">Dashboard</h1>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 bg-muted/40">
          {children}
        </main>
      </div>
    </div>
  )
}