import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './hooks/useAuth'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import NarratorsPage from './pages/NarratorsPage'
import NarratorDetailPage from './pages/NarratorDetailPage'
import HadithsPage from './pages/HadithsPage'
import HadithDetailPage from './pages/HadithDetailPage'
import CollectionsPage from './pages/CollectionsPage'
import CollectionDetailPage from './pages/CollectionDetailPage'
import SearchPage from './pages/SearchPage'
import TimelinePage from './pages/TimelinePage'
import ComparativePage from './pages/ComparativePage'
import GraphExplorerPage from './pages/GraphExplorerPage'
import UserManagementPage from './pages/admin/UserManagementPage'
import SystemHealthPage from './pages/admin/SystemHealthPage'
import ContentStatsPage from './pages/admin/ContentStatsPage'
import UsageAnalyticsPage from './pages/admin/UsageAnalyticsPage'
import ModerationPage from './pages/admin/ModerationPage'
import ReportsPage from './pages/admin/ReportsPage'
import ConfigPage from './pages/admin/ConfigPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/narrators" replace />} />
              <Route path="narrators" element={<NarratorsPage />} />
              <Route path="narrators/:id" element={<NarratorDetailPage />} />
              <Route path="hadiths" element={<HadithsPage />} />
              <Route path="hadiths/:id" element={<HadithDetailPage />} />
              <Route path="collections" element={<CollectionsPage />} />
              <Route path="collections/:id" element={<CollectionDetailPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="timeline" element={<TimelinePage />} />
              <Route path="compare" element={<ComparativePage />} />
              <Route path="graph" element={<GraphExplorerPage />} />
            </Route>
            <Route path="admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/users" replace />} />
              <Route path="users" element={<UserManagementPage />} />
              <Route path="health" element={<SystemHealthPage />} />
              <Route path="stats" element={<ContentStatsPage />} />
              <Route path="analytics" element={<UsageAnalyticsPage />} />
              <Route path="moderation" element={<ModerationPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="config" element={<ConfigPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
