// Compare expected vs actual hadith counts per collection
MATCH (c:Collection)
OPTIONAL MATCH (h:Hadith)-[:APPEARS_IN]->(c)
WITH c, count(h) AS actual_count
RETURN c.id AS collection_id, c.name_en AS name,
       c.expected_count AS expected, actual_count AS actual,
       CASE WHEN c.expected_count IS NOT NULL
            THEN abs(actual_count - c.expected_count) * 100.0 / c.expected_count
            ELSE null END AS deviation_pct
ORDER BY c.id
