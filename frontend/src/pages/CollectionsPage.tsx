import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchCollections } from '../api/client'

export default function CollectionsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['collections'],
    queryFn: () => fetchCollections(),
  })

  return (
    <div>
      <h2 className="page-heading">{t('collections.heading')}</h2>

      {isLoading && (
        <div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton skeleton-row" style={{ width: `${90 - i * 5}%` }} />
          ))}
        </div>
      )}
      {error && <p className="error-text">{t('common.error', { message: (error as Error).message })}</p>}

      {data && (
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('common.colNameArabic')}</th>
              <th>{t('common.colNameEnglish')}</th>
              <th>{t('collections.colCompiler')}</th>
              <th>{t('collections.colSect')}</th>
              <th style={{ textAlign: 'right' }}>{t('collections.colHadiths')}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/collections/${c.id}`)}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/collections/${c.id}`) }}
                tabIndex={0}
                role="link"
                className="clickable-row"
              >
                <td className="text-rtl">{c.name_ar}</td>
                <td>{c.name_en}</td>
                <td>{c.compiler_name ?? '-'}</td>
                <td>
                  <span className={`badge ${c.sect.toLowerCase() === 'sunni' ? 'badge-sunni' : 'badge-shia'}`}>
                    {c.sect}
                  </span>
                </td>
                <td style={{ textAlign: 'right' }}>
                  {c.total_hadiths != null ? c.total_hadiths.toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
