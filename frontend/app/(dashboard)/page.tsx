// app/(dashboard)/page.tsx
// Dashboard home page with overview metrics
// Shows campaign statistics and recent activity
// RELEVANT FILES: layout.tsx, campaigns/page.tsx

export default function DashboardPage() {
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
            <p className="text-2xl font-bold">0</p>
            <p className="text-xs text-muted-foreground">
              +0% from last month
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Leads
            </p>
            <p className="text-2xl font-bold">0</p>
            <p className="text-xs text-muted-foreground">
              +0% from last month
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Messages Sent
            </p>
            <p className="text-2xl font-bold">0</p>
            <p className="text-xs text-muted-foreground">
              +0% from last month
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Response Rate
            </p>
            <p className="text-2xl font-bold">0%</p>
            <p className="text-xs text-muted-foreground">
              +0% from last month
            </p>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border bg-card">
        <div className="p-6">
          <h3 className="text-lg font-medium">Recent Activity</h3>
          <p className="text-sm text-muted-foreground">
            Your latest campaign updates and lead interactions
          </p>
        </div>
        <div className="border-t">
          <div className="p-6 text-center text-muted-foreground">
            No recent activity to display
          </div>
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