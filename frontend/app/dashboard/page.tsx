// app/dashboard/page.tsx
// Dashboard home page with overview metrics from Supabase
// Shows campaign statistics and recent activity
// RELEVANT FILES: layout.tsx, campaigns/page.tsx, ../../lib/supabase/server.ts

import { createClient } from '@/lib/supabase/server'

export default async function DashboardPage() {
  // Fetch data from Supabase
  const supabase = await createClient()
  
  // Get campaigns count
  const { count: campaignsCount } = await supabase
    .from('campaigns')
    .select('*', { count: 'exact', head: true })
  
  // Get leads count
  const { count: leadsCount } = await supabase
    .from('leads')
    .select('*', { count: 'exact', head: true })
  
  // Get messages count
  const { count: messagesCount } = await supabase
    .from('messages')
    .select('*', { count: 'exact', head: true })
  
  // Get recent campaigns
  const { data: recentCampaigns } = await supabase
    .from('campaigns')
    .select('id, name, status, created_at')
    .order('created_at', { ascending: false })
    .limit(5)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Welcome back</h2>
        <p className="text-muted-foreground">
          Here's an overview of your outreach campaigns
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Active Campaigns
            </p>
            <p className="text-2xl font-bold">{campaignsCount || 0}</p>
            <p className="text-xs text-muted-foreground">
              Total campaigns in system
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Leads
            </p>
            <p className="text-2xl font-bold">{leadsCount || 0}</p>
            <p className="text-xs text-muted-foreground">
              Across all campaigns
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Messages Sent
            </p>
            <p className="text-2xl font-bold">{messagesCount || 0}</p>
            <p className="text-xs text-muted-foreground">
              Total outreach messages
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Response Rate
            </p>
            <p className="text-2xl font-bold">
              {messagesCount ? '0%' : 'N/A'}
            </p>
            <p className="text-xs text-muted-foreground">
              Average across campaigns
            </p>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border bg-card">
        <div className="p-6">
          <h3 className="text-lg font-medium">Recent Campaigns</h3>
          <p className="text-sm text-muted-foreground">
            Your latest campaign activity
          </p>
        </div>
        <div className="border-t">
          {recentCampaigns && recentCampaigns.length > 0 ? (
            <div className="divide-y">
              {recentCampaigns.map((campaign) => (
                <div key={campaign.id} className="p-4 hover:bg-muted/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{campaign.name}</p>
                      <p className="text-sm text-muted-foreground">
                        Status: {campaign.status}
                      </p>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {new Date(campaign.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-muted-foreground">
              No campaigns yet. Create your first campaign to get started!
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="mb-2 text-lg font-medium">Start a New Campaign</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Launch your next outreach campaign with AI-powered messaging
          </p>
          <a
            href="/dashboard/campaigns/new"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Create Campaign
          </a>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="mb-2 text-lg font-medium">Import Leads</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Add new prospects to your existing campaigns
          </p>
          <a
            href="/dashboard/leads/import"
            className="inline-flex items-center justify-center rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
          >
            Import Leads
          </a>
        </div>
      </div>
    </div>
  )
}