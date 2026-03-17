import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchHadith, fetchHadithParallels } from '../api/client'

export default function HadithDetailPage() {
  const { id } = useParams<{ id: string }>()

  const {
    data: hadith,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['hadith', id],
    queryFn: () => fetchHadith(id!),
    enabled: !!id,
  })

  const { data: parallelsData } = useQuery({
    queryKey: ['hadith-parallels', id],
    queryFn: () => fetchHadithParallels(id!),
    enabled: !!id,
  })

  if (isLoading) return <p>Loading...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!hadith) return <p>Hadith not found.</p>

  return (
    <div>
      <Link to="/hadiths" className="link-primary">
        &larr; Back to Hadiths
      </Link>

      <h2 style={{ marginTop: '1rem' }}>
        {hadith.source_corpus} &mdash; {hadith.id}
      </h2>

      {hadith.grade_composite && (
        <span
          className={`badge ${hadith.grade_composite.toLowerCase() === 'sahih' ? 'badge-sahih' : 'badge-other-grade'}`}
          style={{ display: 'inline-block', padding: '0.2rem 0.6rem', fontSize: '0.9rem', marginBottom: '1rem' }}
        >
          {hadith.grade_composite}
        </span>
      )}

      <section className="section">
        <h3>Matn (Arabic)</h3>
        <div className="text-arabic-block">{hadith.matn_ar}</div>
      </section>

      {hadith.matn_en && (
        <section className="section">
          <h3>English Translation</h3>
          <div className="text-english-block">{hadith.matn_en}</div>
        </section>
      )}

      {hadith.topic_tags && hadith.topic_tags.length > 0 && (
        <section className="section">
          <h3>Topics</h3>
          <div className="flex-row-wrap" style={{ gap: '0.5rem' }}>
            {hadith.topic_tags.map((tag) => (
              <span key={tag} className="badge-topic-lg">
                {tag}
              </span>
            ))}
          </div>
        </section>
      )}

      {parallelsData && parallelsData.parallels.length > 0 && (
        <section className="section">
          <h3>Parallel Hadiths ({parallelsData.total})</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Source Corpus</th>
                <th>Grade</th>
                <th>Similarity</th>
                <th>Cross-sect</th>
              </tr>
            </thead>
            <tbody>
              {parallelsData.parallels.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/hadiths/${p.id}`} className="link-primary">
                      {p.source_corpus}
                    </Link>
                  </td>
                  <td>{p.grade ?? '-'}</td>
                  <td>
                    {p.similarity_score != null ? `${(p.similarity_score * 100).toFixed(0)}%` : '-'}
                  </td>
                  <td>{p.cross_sect ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
