from fastapi import FastAPI, Query
from neo4j import GraphDatabase

app = FastAPI()
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neoneoneo"))

@app.get("/api/recommendations")
def get_recommendations(city: str, cuisine: str):
    cypher_query = """
    MATCH (r:Restaurant)-[:SERVES]->(c:Cuisine {name: $cuisine}),
          (r)-[:LOCATED_IN]->(l:Locality)-[:PART_OF]->(cit:City {name: $city})
    RETURN r.name AS name, r.rating AS rating, r.average_cost AS cost, l.name AS locality
    ORDER BY r.rating DESC
    LIMIT 10
    """
    
    with driver.session() as session:
        result = session.run(cypher_query, city=city, cuisine=cuisine)
        r = [dict(record) for record in result]
        print(f"Response:\n{r}")
        return 