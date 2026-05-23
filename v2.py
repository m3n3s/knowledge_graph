import pandas as pd
from neo4j import GraphDatabase
from cuisines import *

# --- Configuration ---
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neoneoneo"
CSV_PATH = "munich_df.csv"

def create_constraints(tx):
    """Create unique constraints to prevent duplicate nodes and accelerate lookups."""
    print("Creating database constraints...")
    tx.run("CREATE CONSTRAINT FOR (r:Restaurant) REQUIRE r.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (c:Cuisine) REQUIRE c.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (loc:Location) REQUIRE loc.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (d:Diet) REQUIRE d.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (p:PriceCategory) REQUIRE p.tier IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (t:Tag) REQUIRE t.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (w:WorldRegion) REQUIRE w.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (e:EstablishmentType) REQUIRE e.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT FOR (g:FormatGroup) REQUIRE g.name IS UNIQUE")

def insert_restaurant_row(tx, row):
    """Cypher query block to inject a single row's relationships into Neo4j."""
    
    # 1. Base Restaurant Node Query (Handles Address and Coordinates natively)
    # Using float() for lat/lon allows Neo4j to use distance functions later.
    base_cypher = """
    MERGE (r:Restaurant {id: $res_id})
    SET r.name = $res_name,
        r.address = $address,
        r.rating = toFloat($rating),
        r.location = point({latitude: toFloat($lat), longitude: toFloat($lon)})
    """
    
    tx.run(base_cypher, 
           res_id=str(row['restaurant_link']),
           res_name=str(row['restaurant_name']),
           address=str(row['address']) if pd.notna(row['address']) else None,
           rating=float(row['avg_rating']) if pd.notna(row['avg_rating']) else None,
           lat=float(row['latitude']) if pd.notna(row['latitude']) else None,
           lon=float(row['longitude']) if pd.notna(row['longitude']) else None)

    # 2. Location Hierarchy (City -> Region -> Country)
    if pd.notna(row['city']):
        loc_cypher = """
        MATCH (r:Restaurant {id: $res_id})
        MERGE (city:Location {name: $city, type: 'City'})
        MERGE (r)-[:LOCATED_IN]->(city)
        """
        tx.run(loc_cypher, res_id=str(row['restaurant_link']), city=str(row['city']).strip())
        
        if pd.notna(row['region']):
            reg_cypher = """
            MERGE (city:Location {name: $city, type: 'City'})
            MERGE (reg:Location {name: $region, type: 'Region'})
            MERGE (city)-[:IS_PART_OF]->(reg)
            """
            tx.run(reg_cypher, city=str(row['city']).strip(), region=str(row['region']).strip())
            
            if pd.notna(row['country']):
                coun_cypher = """
                MERGE (reg:Location {name: $region, type: 'Region'})
                MERGE (coun:Location {name: $country, type: 'Country'})
                MERGE (reg)-[:IS_PART_OF]->(coun)
                """
                tx.run(coun_cypher, region=str(row['region']).strip(), country=str(row['country']).strip())

    # 3. Cuisines & Macro-Region Origins
    if pd.notna(row['cuisines']):
        items = [c.strip() for c in str(row['cuisines']).split(',')]
        for item in items:
            
            # Path 1: It's a true geographical Cuisine
            if item in CUISINE_TO_REGION:
                cuisine_cypher = """
                MATCH (r:Restaurant {id: $res_id})
                MERGE (c:Cuisine {name: $cuisine})
                MERGE (r)-[:SERVES]->(c)
                """
                tx.run(cuisine_cypher, res_id=str(row['restaurant_link']), cuisine=item)
                
                world_reg = CUISINE_TO_REGION[item]
                origin_cypher = """
                MERGE (c:Cuisine {name: $cuisine})
                MERGE (w:WorldRegion {name: $world_reg})
                MERGE (c)-[:ORIGINATES_FROM]->(w)
                """
                tx.run(origin_cypher, cuisine=item, world_reg=world_reg)
                
            # Path 2: It's an Establishment Type or Vibe category
            elif item in ESTABLISHMENT_FORMATS:
                format_cypher = """
                MATCH (r:Restaurant {id: $res_id})
                MERGE (e:EstablishmentType {name: $item})
                MERGE (r)-[:HAS_TYPE]->(e)
                """
                tx.run(format_cypher, res_id=str(row['restaurant_link']), item=item)
                
                group_name = ESTABLISHMENT_FORMATS[item]
                group_cypher = """
                MERGE (e:EstablishmentType {name: $item})
                MERGE (g:FormatGroup {name: $group_name})
                MERGE (e)-[:BELONGS_TO_GROUP]->(g)
                """
                tx.run(group_cypher, item=item, group_name=group_name)
                
            # Fallback path if an item isn't in either dictionary yet
            else:
                fallback_cypher = """
                MATCH (r:Restaurant {id: $res_id})
                MERGE (c:Cuisine {name: $item})
                MERGE (r)-[:SERVES]->(c)
                """
                tx.run(fallback_cypher, res_id=str(row['restaurant_link']), item=item)

    # 4. Dietary Restraints
    if pd.notna(row['special_diets']):
        diets = [d.strip() for d in str(row['special_diets']).split(',')]
        for diet in diets:
            diet_cypher = """
            MATCH (r:Restaurant {id: $res_id})
            MERGE (d:Diet {name: $diet})
            MERGE (r)-[:SUITABLE_FOR]->(d)
            """
            tx.run(diet_cypher, res_id=str(row['restaurant_link']), diet=diet)

    # 5. Price Level
    if pd.notna(row['price_level']):
        price_cypher = """
        MATCH (r:Restaurant {id: $res_id})
        MERGE (p:PriceCategory {tier: $price_tier})
        MERGE (r)-[:HAS_PRICE]->(p)
        """
        tx.run(price_cypher, res_id=str(row['restaurant_link']), price_tier=str(row['price_level']).strip())

    # 6. Keywords / Descriptive Tags
    if pd.notna(row['keywords']):
        keywords = [k.strip() for k in str(row['keywords']).split(',')]
        for kw in keywords:
            kw_cypher = """
            MATCH (r:Restaurant {id: $res_id})
            MERGE (t:Tag {name: $kw})
            MERGE (r)-[:HAS_TAG]->(t)
            """
            tx.run(kw_cypher, res_id=str(row['restaurant_link']), kw=kw)


def main():
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Could not find CSV file at {CSV_PATH}")
        return

    print(f"Connecting to Neo4j instance at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Run constraints first
        try:
            session.execute_write(create_constraints)
        except Exception as e:
            print(f"Exception while running constraints: {e}.")
            
        print(f"Populating graph with {len(df)} entries.")
        for idx, row in df.iterrows():
            session.execute_write(insert_restaurant_row, row)
            if (idx + 1) % 100 == 0:
                print(f"Progress: Completed {idx + 1} restaurants...")
                
    driver.close()
    print("Neo4j Knowledge Graph population successful!")

if __name__ == "__main__":
    main()