import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchNarrators } from '../api/client'

export default function NarratorsPage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [inputValue, setInputValue] = useState('')
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['narrators', page, search],
    queryFn: () => fetchNarrators(page, 20, search || undefined),
  })

  const handleSearch = () => {
    setSearch(inputValue)
    setPage(1)
  }

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0

  return (
    <div>
      <h2 className="page-heading">{t('narrators.heading')}</h2>

      <div className="flex-row" style={{ marginBottom: 'var(--spacing-4)' }}>
        <input
          type="text"
          placeholder={t('narrators.searchPlaceholder')}
          aria-label={t('narrators.searchLabel')}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="form-input"
          style={{ flex: 1, maxWidth: 400 }}
        />
        <button onClick={handleSearch} className="btn-primary">
          {t('common.search')}
        </button>
      </div>

      {isLoading && (
        <div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton skeleton-row" style={{ width: `${90 - i * 5}%` }} />
          ))}
        </div>
      )}
      {error && <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>}

      {data && data.items.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </div>
          <div className="empty-state-heading">{t('narrators.emptyHeading')}</div>
          <div className="empty-state-body">
            {t('narrators.emptyBody')}
          </div>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('common.colNameArabic')}</th>
                <th>{t('common.colNameEnglish')}</th>
                <th>{t('narrators.colGeneration')}</th>
                <th>{t('narrators.colTrustworthiness')}</th>
                <th>{t('narrators.colCommunity')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr
                  key={n.id}
                  onClick={() => navigate(`/narrators/${n.id}`)}
                  onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/narrators/${n.id}`) }}
                  tabIndex={0}
                  role="link"
                  className="clickable-row"
                >
                  <td className="text-rtl">{n.name_ar}</td>
                  <td>{n.name_en ?? '-'}</td>
                  <td>{n.generation ?? '-'}</td>
                  <td>{n.trustworthiness_consensus ?? '-'}</td>
                  <td>{n.community_id != null ? `#${n.community_id}` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              {t('common.previous')}
            </button>
            <span>
              {t('common.pageOf', { current: data.page, total: totalPages })}
            </span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              {t('common.next')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
