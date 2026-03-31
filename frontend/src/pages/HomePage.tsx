import { Link } from 'react-router-dom'
import {
  GraphExplorerIcon,
  SearchIcon,
  CompareIcon,
  TimelineIcon,
  CollectionsIcon,
  NarratorsIcon,
  HadithsIcon,
} from '../components/icons'
import { GeometricBorder } from '../components/icons/decorative'

const features = [
  {
    to: '/graph',
    Icon: GraphExplorerIcon,
    title: 'Graph Explorer',
    description: 'Visualize narrator networks and isnad chains as interactive graphs.',
  },
  {
    to: '/search',
    Icon: SearchIcon,
    title: 'Search',
    description: 'Full-text and semantic search across hadith texts and narrators.',
  },
  {
    to: '/compare',
    Icon: CompareIcon,
    title: 'Comparative Analysis',
    description: 'Detect parallel hadiths across Sunni and Shia collections.',
  },
  {
    to: '/timeline',
    Icon: TimelineIcon,
    title: 'Timeline',
    description: 'Explore narrators and transmission events across historical periods.',
  },
  {
    to: '/collections',
    Icon: CollectionsIcon,
    title: 'Collections',
    description: 'Browse major hadith compilations and their contents.',
  },
]

const quickLinks = [
  { to: '/narrators', Icon: NarratorsIcon, label: 'Browse Narrators' },
  { to: '/hadiths', Icon: HadithsIcon, label: 'Browse Hadiths' },
  { to: '/graph', Icon: GraphExplorerIcon, label: 'Open Graph Explorer' },
  { to: '/search', Icon: SearchIcon, label: 'Search' },
]

export default function HomePage() {
  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Hero */}
      <section style={{ marginBottom: 'var(--spacing-8)' }}>
        <h1
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            color: 'var(--color-foreground)',
            marginBottom: 'var(--spacing-3)',
            letterSpacing: 'var(--tracking-tight)',
          }}
        >
          Isnad Graph &mdash; Hadith Analysis Platform
        </h1>
        <p
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-base)',
            color: 'var(--color-muted-foreground)',
            lineHeight: 1.6,
            maxWidth: 680,
          }}
        >
          A computational platform for analyzing hadith chains of narration (isnad).
          Explore narrator networks, detect cross-collection parallels, and study
          transmission topology across Sunni and Shia hadith literature using graph
          analysis and semantic search.
        </p>
      </section>

      <GeometricBorder style={{ marginBottom: 'var(--spacing-8)' }} />

      {/* Feature cards */}
      <section style={{ marginBottom: 'var(--spacing-8)' }}>
        <h2
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-lg)',
            fontWeight: 600,
            color: 'var(--color-foreground)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          Key Features
        </h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 'var(--spacing-4)',
          }}
        >
          {features.map((f) => (
            <Link
              key={f.to}
              to={f.to}
              style={{
                textDecoration: 'none',
                color: 'inherit',
                padding: 'var(--spacing-5)',
                borderRadius: 'var(--radius-lg)',
                border: 'var(--border-width-thin) solid var(--color-border)',
                background: 'var(--color-card)',
                transition: 'border-color var(--duration-fast) var(--ease-default), box-shadow var(--duration-fast) var(--ease-default)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-primary)'
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                <f.Icon size={20} style={{ color: 'var(--color-primary)', opacity: 0.8 }} />
                <h3
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-heading)',
                    fontSize: 'var(--text-base)',
                    fontWeight: 600,
                    color: 'var(--color-foreground)',
                  }}
                >
                  {f.title}
                </h3>
              </div>
              <p
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-body)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--color-muted-foreground)',
                  lineHeight: 1.5,
                }}
              >
                {f.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <GeometricBorder style={{ marginBottom: 'var(--spacing-8)' }} />

      {/* Getting started */}
      <section>
        <h2
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--text-lg)',
            fontWeight: 600,
            color: 'var(--color-foreground)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          Getting Started
        </h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-3)' }}>
          {quickLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--spacing-2)',
                padding: 'var(--spacing-2) var(--spacing-4)',
                borderRadius: 'var(--radius-md)',
                border: 'var(--border-width-thin) solid var(--color-border)',
                background: 'var(--color-card)',
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                fontWeight: 500,
                color: 'var(--color-foreground)',
                textDecoration: 'none',
                transition: 'background var(--duration-fast) var(--ease-default)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-accent)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--color-card)'
              }}
            >
              <link.Icon size={16} style={{ opacity: 0.7 }} />
              {link.label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
