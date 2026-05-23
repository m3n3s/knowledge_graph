from fastapi import FastAPI, Query
from neo4j import GraphDatabase

app = FastAPI()
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neoneoneo"))

@app.get("/api/recommendations")
def get_recommendations(city: str, cuisine: str):
    cypher_query = """
    MATCH (targetCuisine:Cuisine {name: "Vietnamese"})-[:ORIGINATES_FROM]->(region:WorldRegion)
    MATCH (siblingCuisine:Cuisine)-[:ORIGINATES_FROM]->(region)
    MATCH (r:Restaurant)-[:SERVES]->(siblingCuisine)
    MATCH (r)-[:LOCATED_IN]->(:Location {name: "Munich"})
    RETURN r.name AS name, r.address AS address, r.rating AS rating, siblingCuisine.name AS cuisine_type
    ORDER BY r.rating DESC
    LIMIT 10
    """
    
    with driver.session() as session:
        result = session.run(cypher_query, city=city, cuisine=cuisine)
        r = [dict(record) for record in result]
        print(f"Response:\n{r}")
        return 