import pandas as pd
from neo4j import GraphDatabase

# 1. Connect to Neo4j
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neoneoneo")

CUISINE_TO_REGION = {
    "French": "Western European",
    "Japanese": "East Asian",
    "Desserts": "Bakery & Sweets",
    "Korean": "East Asian",
    "Italian": "Mediterranean",
    "Spanish": "Mediterranean"
}

def run_import():
    # Load your CSV data
    df = pd.read_csv("dataset.csv")

    driver = GraphDatabase.driver(URI, auth=AUTH)

    print("Connected..")
    
    with driver.session() as session:
        # Assuming you are looping through your dataframe rows...
        for _, row in df.iterrows():
            if pd.isna(row['Cuisines']) or not isinstance(row['Cuisines'], str):
                print(f"cuisine filed is null. Row: {row}")
                continue
    
            query = """
            MERGE (city:City {name: $city_name})
            MERGE (loc:Locality {name: $locality_name})
            MERGE (loc)-[:PART_OF]->(city)

            MERGE (r:Restaurant {id: $r_id})
            SET r.name = $r_name, r.rating = $rating
                
            MERGE (r)-[:LOCATED_IN]->(loc)

            // Unwind the payload list
            WITH r, $cuisines AS cuisines_list
            UNWIND cuisines_list AS cuisine_data
            MERGE (c:Cuisine {name: cuisine_data.name})
            MERGE (r)-[:SERVES]->(c)

            // FIX: Pass BOTH 'c' and 'cuisine_data' forward through the WITH clause
            WITH c, cuisine_data
            WHERE cuisine_data.region IS NOT NULL
            MERGE (reg:CuisineRegion {name: cuisine_data.region})
            MERGE (c)-[:BELONGS_TO]->(reg)
            """
            
            # Clean cuisines and attach their regions from the mapping dictionary
            raw_cuisines = [c.strip() for c in row['Cuisines'].split(',')]
            cuisine_payload = []
            for c in raw_cuisines:
                cuisine_payload.append({
                    "name": c,
                    "region": CUISINE_TO_REGION.get(c, "Other") # Fallback to 'Other' if not mapped
                })
        
            session.run(
                query,
                city_name=row['City'],
                locality_name=row['Locality'],
                r_id=int(row['Restaurant ID']),
                r_name=row['Restaurant Name'],
                rating=float(row['Aggregate rating']),
                cuisines=cuisine_payload
            )
            
    driver.close()
    print("Knowledge Graph constructed successfully!")

if __name__ == "__main__":
    run_import()