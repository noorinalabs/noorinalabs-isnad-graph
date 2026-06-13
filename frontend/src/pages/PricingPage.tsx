import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useSubscription } from '../hooks/useSubscription'

type BillingInterval = 'monthly' | 'annual'

interface Tier {
  id: string
  name: string
  monthlyPrice: number | null
  description: string
  features: string[]
  cta: string
  popular?: boolean
}

const tiers: Tier[] = [
  {
    id: 'trial',
    name: 'Trial',
    monthlyPrice: 0,
    description: 'Free for 7 days',
    features: [
      '100 searches per day',
      'Basic hadith browsing',
      'Single user',
    ],
    cta: 'Current plan',
  },
  {
    id: 'individual',
    name: 'Individual',
    monthlyPrice: 14.95,
    description: 'For independent researchers',
    features: [
      'Unlimited searches',
      'Graph visualization',
      'Export data (CSV, JSON)',
      'Saved searches',
      'Narrator network analysis',
      'Cross-collection parallels',
    ],
    cta: 'Get started',
    popular: true,
  },
  {
    id: 'team',
    name: 'Team',
    monthlyPrice: 19.95,
    description: 'Per user/month',
    features: [
      'Everything in Individual',
      'Shared workspace',
      'Collaborative annotations',
      'Team analytics dashboard',
      'Priority support',
    ],
    cta: 'Get started',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    monthlyPrice: null,
    description: 'Custom pricing',
    features: [
      'Everything in Team',
      'SSO / SAML integration',
      'Dedicated support engineer',
      'Custom SLA',
      'Custom integrations',
      'On-premise deployment option',
    ],
    cta: 'Contact us',
  },
]

function formatPrice(price: number, interval: BillingInterval): string {
  if (price === 0) return 'Free'
  if (interval === 'annual') {
    const annual = price * 10 // 2 months free
    return `$${(annual / 12).toFixed(2)}`
  }
  return `$${price.toFixed(2)}`
}

function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--color-primary)"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0 mt-0.5"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

export default function PricingPage() {
  const [interval, setInterval] = useState<BillingInterval>('monthly')
  const { subscription } = useSubscription()

  return (
    <div
      className="min-h-screen bg-background px-6 py-10"
    >
      <div className="mx-auto max-w-[1200px]">
        {/* Header */}
        <div className="mb-10 text-center">
          <Link
            to="/"
            className="mb-6 inline-block text-primary no-underline"
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--text-sm)',
            }}
          >
            &larr; Back to Isnad Graph
          </Link>
          <h1
            className="mb-3 font-bold text-foreground"
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--text-3xl)',
            }}
          >
            Choose your plan
          </h1>
          <p
            className="mx-auto mb-8 max-w-[600px] text-muted-foreground"
            style={{
              fontSize: 'var(--text-lg)',
              lineHeight: 1.6,
            }}
          >
            Access the most comprehensive computational hadith analysis platform.
            Start free, upgrade when you need more.
          </p>

          {/* Billing toggle */}
          <div className="inline-flex items-center gap-3 rounded-full bg-accent p-1">
            <button
              onClick={() => setInterval('monthly')}
              className="cursor-pointer rounded-full border-none px-5 py-2 font-semibold"
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                background:
                  interval === 'monthly' ? 'var(--color-card)' : 'transparent',
                color:
                  interval === 'monthly'
                    ? 'var(--color-foreground)'
                    : 'var(--color-muted-foreground)',
                boxShadow:
                  interval === 'monthly' ? 'var(--shadow-sm)' : 'none',
                transition: 'all var(--duration-fast) var(--ease-default)',
              }}
            >
              Monthly
            </button>
            <button
              onClick={() => setInterval('annual')}
              className="cursor-pointer rounded-full border-none px-5 py-2 font-semibold"
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 'var(--text-sm)',
                background:
                  interval === 'annual' ? 'var(--color-card)' : 'transparent',
                color:
                  interval === 'annual'
                    ? 'var(--color-foreground)'
                    : 'var(--color-muted-foreground)',
                boxShadow:
                  interval === 'annual' ? 'var(--shadow-sm)' : 'none',
                transition: 'all var(--duration-fast) var(--ease-default)',
              }}
            >
              Annual
              <span
                className="ml-2 rounded-full bg-primary px-2 py-0.5 font-bold text-primary-foreground"
                style={{
                  fontSize: 'var(--text-xs)',
                }}
              >
                Save 17%
              </span>
            </button>
          </div>
        </div>

        {/* Tier cards */}
        <div
          className="mx-auto grid gap-6 max-w-[1100px]"
          style={{
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          }}
        >
          {tiers.map((tier) => {
            const isCurrent = subscription?.tier === tier.id
            const isEnterprise = tier.monthlyPrice === null

            return (
              <div
                key={tier.id}
                className="relative flex flex-col rounded-xl bg-card p-8"
                style={{
                  border: tier.popular
                    ? '2px solid var(--color-primary)'
                    : 'var(--border-width-thin) solid var(--color-border)',
                  boxShadow: tier.popular ? 'var(--shadow-lg)' : 'var(--shadow-sm)',
                }}
              >
                {tier.popular && (
                  <div
                    className="absolute rounded-full bg-primary px-4 py-1 font-bold text-primary-foreground uppercase whitespace-nowrap"
                    style={{
                      top: -12,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      fontSize: 'var(--text-xs)',
                      fontFamily: 'var(--font-heading)',
                      letterSpacing: '0.05em',
                    }}
                  >
                    Most popular
                  </div>
                )}

                <h2
                  className="mb-1 font-bold text-foreground"
                  style={{
                    fontFamily: 'var(--font-heading)',
                    fontSize: 'var(--text-xl)',
                  }}
                >
                  {tier.name}
                </h2>

                <p
                  className="mb-6 text-muted-foreground"
                  style={{
                    fontSize: 'var(--text-sm)',
                  }}
                >
                  {tier.description}
                </p>

                <div className="mb-6">
                  {isEnterprise ? (
                    <span
                      className="font-bold text-foreground"
                      style={{
                        fontFamily: 'var(--font-heading)',
                        fontSize: 'var(--text-3xl)',
                      }}
                    >
                      Custom
                    </span>
                  ) : (
                    <>
                      <span
                        className="font-bold text-foreground"
                        style={{
                          fontFamily: 'var(--font-heading)',
                          fontSize: 'var(--text-3xl)',
                        }}
                      >
                        {formatPrice(tier.monthlyPrice!, interval)}
                      </span>
                      {tier.monthlyPrice! > 0 && (
                        <span
                          className="ml-1 text-muted-foreground"
                          style={{
                            fontSize: 'var(--text-sm)',
                          }}
                        >
                          /mo{tier.id === 'team' ? '/user' : ''}
                        </span>
                      )}
                      {tier.monthlyPrice! > 0 && interval === 'annual' && (
                        <div
                          className="mt-1 text-muted-foreground"
                          style={{
                            fontSize: 'var(--text-xs)',
                          }}
                        >
                          Billed annually (${(tier.monthlyPrice! * 10).toFixed(2)}/year)
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* CTA */}
                {isCurrent ? (
                  <div
                    className="mb-6 rounded-md border-2 border-primary p-3 text-center font-semibold text-primary"
                    style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 'var(--text-sm)',
                    }}
                  >
                    Current plan
                  </div>
                ) : isEnterprise ? (
                  <a
                    href="mailto:contact@noorinalabs.com?subject=Enterprise%20inquiry"
                    className="mb-6 block rounded-md bg-accent p-3 text-center font-semibold text-foreground no-underline"
                    style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 'var(--text-sm)',
                      transition: 'opacity var(--duration-fast) var(--ease-default)',
                    }}
                  >
                    {tier.cta}
                  </a>
                ) : (
                  <Link
                    to="/billing/checkout"
                    state={{ tier: tier.id, interval }}
                    className="mb-6 block rounded-md p-3 text-center font-semibold no-underline"
                    style={{
                      background: tier.popular
                        ? 'var(--color-primary)'
                        : 'var(--color-accent)',
                      fontFamily: 'var(--font-body)',
                      fontSize: 'var(--text-sm)',
                      color: tier.popular
                        ? 'var(--color-primary-foreground)'
                        : 'var(--color-foreground)',
                      transition: 'opacity var(--duration-fast) var(--ease-default)',
                    }}
                  >
                    {tier.cta}
                  </Link>
                )}

                {/* Features */}
                <ul className="m-0 flex flex-1 list-none flex-col gap-3 p-0">
                  {tier.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-2 text-foreground"
                      style={{
                        fontSize: 'var(--text-sm)',
                      }}
                    >
                      <CheckIcon />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
