import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchNarrator, fetchNarratorChains } from '../api/client'

export default function NarratorDetailPage() {
  const { id } = useParams<{ id: string }>()

  const {
    data: narrator,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['narrator', id],
    queryFn: () => fetchNarrator(id!),
    enabled: !!id,
  })

  const { data: chainsData } = useQuery({
    queryKey: ['narrator-chains', id],
    queryFn: () => fetchNarratorChains(id!),
    enabled: !!id,
  })

  if (isLoading) return <p>Loading...</p>
  if (error) return <p className="error-text">Error: {(error as Error).message}</p>
  if (!narrator) return <p>Narrator not found.</p>

  return (
    <div>
      <Link to="/narrators" className="link-primary">
        &larr; Back to Narrators
      </Link>

      <h2 className="text-rtl" style={{ marginTop: '1rem' }}>
        {narrator.name_ar}
      </h2>
      {narrator.name_en && (
        <h3 style={{ color: '#555', fontWeight: 400 }}>{narrator.name_en}</h3>
      )}

      <section className="section">
        <h3>Biography</h3>
        <table className="bio-table">
          <tbody>
            {[
              ['Kunya', narrator.kunya],
              ['Nisba', narrator.nisba],
              ['Laqab', narrator.laqab],
              ['Birth Year', narrator.birth_year_ah != null ? `${narrator.birth_year_ah} AH` : null],
              ['Death Year', narrator.death_year_ah != null ? `${narrator.death_year_ah} AH` : null],
              ['Generation', narrator.generation],
              ['Gender', narrator.gender],
              ['Sect Affiliation', narrator.sect_affiliation],
              ['Trustworthiness', narrator.trustworthiness_consensus],
            ].map(
              ([label, value]) =>
                value && (
                  <tr key={label as string}>
                    <td>{label}</td>
                    <td>{value}</td>
                  </tr>
                ),
            )}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h3>Network Statistics</h3>
        <div className="flex-row-wrap" style={{ gap: '2rem' }}>
          {[
            ['In-Degree', narrator.in_degree],
            ['Out-Degree', narrator.out_degree],
            ['Betweenness', narrator.betweenness_centrality?.toFixed(4)],
            ['PageRank', narrator.pagerank?.toFixed(4)],
            ['Community', narrator.community_id != null ? `#${narrator.community_id}` : null],
          ].map(
            ([label, value]) =>
              value != null && (
                <div key={label as string} className="network-stat">
                  <div className="network-stat-label">{label}</div>
                  <div className="network-stat-value">{value}</div>
                </div>
              ),
          )}
        </div>
      </section>

      {chainsData && chainsData.chains.length > 0 && (
        <section className="section">
          <h3>Chains ({chainsData.total})</h3>
          <ul style={{ paddingLeft: '1.25rem' }}>
            {chainsData.chains.map((chain) => (
              <li key={chain.chain_id} style={{ marginBottom: '0.5rem' }}>
                <Link to={`/hadiths/${chain.hadith_id}`} className="link-primary">
                  Hadith {chain.hadith_id}
                </Link>
                {chain.grade && (
                  <span style={{ color: '#999', marginLeft: '0.5rem' }}>({chain.grade})</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
