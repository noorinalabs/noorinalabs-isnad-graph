// Find narrator nodes with no relationships
// Expected: 0 orphans in a healthy graph
MATCH (n:Narrator)
WHERE NOT (n)--()
RETURN n.id AS narrator_id, n.name_en AS name
ORDER BY n.id
