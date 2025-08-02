// app/page.tsx
// Landing page for the application
// Public facing page with product information
// RELEVANT FILES: layout.tsx, (auth)/login/page.tsx

import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Navigation */}
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center px-4">
          <Link href="/" className="flex items-center space-x-2">
            <span className="text-xl font-bold">Agentic Outreach</span>
          </Link>
          <nav className="ml-auto flex gap-4">
            <Link
              href="/login"
              className="text-sm font-medium hover:text-primary"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="container mx-auto px-4 py-24">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-6xl">
              AI-Powered Outreach Automation
            </h1>
            <p className="mb-8 text-xl text-muted-foreground">
              Scale your outreach efforts with intelligent automation.
              Connect with prospects across email and LinkedIn using
              personalized, AI-generated messages.
            </p>
            <div className="flex flex-col gap-4 sm:flex-row sm:justify-center">
              <Link
                href="/register"
                className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90"
              >
                Start Free Trial
              </Link>
              <Link
                href="#features"
                className="inline-flex items-center justify-center rounded-md border border-input px-8 py-3 text-base font-medium hover:bg-accent hover:text-accent-foreground"
              >
                Learn More
              </Link>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="border-t bg-muted/50 py-24">
          <div className="container mx-auto px-4">
            <h2 className="mb-12 text-center text-3xl font-bold">
              Everything you need for successful outreach
            </h2>
            <div className="grid gap-8 md:grid-cols-3">
              <div className="rounded-lg border bg-card p-6">
                <h3 className="mb-3 text-xl font-semibold">
                  AI-Powered Messages
                </h3>
                <p className="text-muted-foreground">
                  Generate personalized outreach messages using advanced AI
                  that understands your prospects and your value proposition.
                </p>
              </div>
              <div className="rounded-lg border bg-card p-6">
                <h3 className="mb-3 text-xl font-semibold">
                  Multi-Channel Campaigns
                </h3>
                <p className="text-muted-foreground">
                  Reach prospects where they are with integrated email and
                  LinkedIn outreach campaigns managed from one platform.
                </p>
              </div>
              <div className="rounded-lg border bg-card p-6">
                <h3 className="mb-3 text-xl font-semibold">
                  Smart Lead Enrichment
                </h3>
                <p className="text-muted-foreground">
                  Automatically enrich leads with detailed information to
                  ensure your messages are relevant and timely.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          © 2025 Agentic Outreach System. All rights reserved.
        </div>
      </footer>
    </div>
  )
}