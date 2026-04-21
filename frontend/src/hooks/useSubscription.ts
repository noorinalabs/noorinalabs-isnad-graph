import { useQuery } from '@tanstack/react-query'
import { fetchSubscriptionOrNull } from '../api/client'
import type { SubscriptionResponse } from '../types/api'
import { useAuth } from './useAuth'

export function useSubscription() {
  const { user, isAdmin } = useAuth()

  // Admins have no subscription concept — skip the call entirely. A 404 from
  // /subscriptions/me is a terminal "no subscription" data state, so we treat
  // it as `null` instead of an error and disable retry (see #830).
  const { data, isLoading, error } = useQuery<SubscriptionResponse | null>({
    queryKey: ['subscription'],
    queryFn: fetchSubscriptionOrNull,
    enabled: !!user && !isAdmin,
    retry: false,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })

  return {
    subscription: data ?? null,
    isLoading,
    error,
    isExpired: data?.status === 'expired',
    isTrial: data?.status === 'trial',
    isActive: data?.status === 'active',
    daysRemaining: data?.days_remaining ?? 0,
  }
}
