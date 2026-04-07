import { useAuth } from '../hooks/useAuth'

export default function WelcomeBanner() {
  const { user, isNewUser, dismissOnboarding } = useAuth()

  if (!isNewUser || !user) return null

  return (
    <div
      role="status"
      className="rounded-lg border border-primary/30 bg-primary/5 px-6 py-4 mb-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            Welcome to Isnad Graph, {user.name.split(' ')[0]}!
          </h3>
          <p className="text-sm text-muted-foreground">
            Start exploring hadith chains and narrator networks. Use the search bar to find
            narrators or hadiths, or browse the collections to get started.
          </p>
        </div>
        <button
          onClick={dismissOnboarding}
          aria-label="Dismiss welcome message"
          className="shrink-0 rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  )
}
