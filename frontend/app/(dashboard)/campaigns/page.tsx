// app/(dashboard)/campaigns/page.tsx
// Campaigns list page with CRUD operations
// Shows all campaigns with status and metrics
// RELEVANT FILES: ../../../lib/api/campaigns.ts, new/page.tsx

'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Plus, MoreVertical, Search } from 'lucide-react'
import { campaignsApi } from '@/lib/api/campaigns'
import { Campaign, CampaignStatus } from '@/types'

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadCampaigns()
  }, [])

  const loadCampaigns = async () => {
    try {
      setIsLoading(true)
      const response = await campaignsApi.list()
      setCampaigns(response.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load campaigns')
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case CampaignStatus.ACTIVE:
        return 'bg-green-100 text-green-800'
      case CampaignStatus.PAUSED:
        return 'bg-yellow-100 text-yellow-800'
      case CampaignStatus.COMPLETED:
        return 'bg-blue-100 text-blue-800'
      case CampaignStatus.ARCHIVED:
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Campaigns</h2>
          <p className="text-muted-foreground">
            Manage your outreach campaigns
          </p>
        </div>
        <Link href="/dashboard/campaigns/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Campaign
          </Button>
        </Link>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search campaigns..."
            className="w-full pl-9 pr-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>

      {/* Campaigns List */}
      {isLoading ? (
        <div className="text-center py-12">Loading campaigns...</div>
      ) : error ? (
        <div className="text-center py-12 text-destructive">{error}</div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground mb-4">
            No campaigns found. Create your first campaign to get started.
          </p>
          <Link href="/dashboard/campaigns/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Campaign
            </Button>
          </Link>
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Leads
                </th>
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Messages
                </th>
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-sm font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={campaign.id} className="border-b hover:bg-muted/50">
                  <td className="px-6 py-4">
                    <Link
                      href={`/dashboard/campaigns/${campaign.id}`}
                      className="font-medium hover:text-primary"
                    >
                      {campaign.name}
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeClass(
                        campaign.status
                      )}`}
                    >
                      {campaign.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {campaign.total_leads_discovered || 0}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {campaign.email_metrics?.sent || 0}
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <button className="text-muted-foreground hover:text-foreground">
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}