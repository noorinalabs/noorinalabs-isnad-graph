// Verify TRANSMITTED_TO paths form valid chains (no cycles, connected)
// Bounded cycle detection — check paths up to length 20
MATCH path = (n:Narrator)-[:TRANSMITTED_TO*1..20]->(m:Narrator)
WHERE n = m
RETURN n.id AS narrator_id, length(path) AS cycle_length
LIMIT 100
