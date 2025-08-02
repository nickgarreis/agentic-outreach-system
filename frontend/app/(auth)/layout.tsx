// app/(auth)/layout.tsx
// Layout for authentication pages
// Provides centered card layout for auth forms
// RELEVANT FILES: login/page.tsx, register/page.tsx

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/50">
      <div className="w-full max-w-md p-4">
        {children}
      </div>
    </div>
  )
}