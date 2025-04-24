'''
Before running this file, follow these steps:
1. Run `download_ecosystem_data.py` to download / update vulnerability information. 
2. Run fetch_osv_ids. Wait for `all_vulnerability_ids.json` to be created / updated.

This file will populate neo4j for the first time. It can be ran again to update the database with
the new information. 
'''
import json
import aiohttp
import asyncio
import time
import random
from osv.neo4j_connection import get_neo4j_driver
from concurrent.futures import ThreadPoolExecutor

async def fetch_vulnerability_data(vuln_id, session, semaphore):
    # Fetch vulnerability data from OSV API with retry logic and rate limit handling
    async with semaphore:
        url = f"https://api.osv.dev/v1/vulns/{vuln_id}"
        retries = 3
        for attempt in range(retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Verify the ID is correct
                        if data.get('id') != vuln_id:
                            print(f"Warning: API returned ID '{data.get('id')}' but expected '{vuln_id}'. Fixing.")
                            data['id'] = vuln_id
                        return data
                    elif response.status == 429:  # Rate limited
                        wait_time = random.uniform(2, 5)
                        print(f"Rate limited for {vuln_id}, waiting {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Failed to fetch data for {vuln_id}, status code: {response.status}")
                        return None
            except Exception as e:
                print(f"Error fetching data for {vuln_id}, attempt {attempt + 1}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(random.uniform(1, 3))  # Wait a random time before retrying
                else:
                    return None

def check_if_vulnerabilities_exist(driver, vuln_ids):
    # Check which vulnerability IDs already exist in the database
    with driver.session() as session:
        result = session.run("""
        UNWIND $ids AS id
        OPTIONAL MATCH (v:Vulnerability {id: id})
        RETURN id, v IS NOT NULL AS exists
        """, ids=vuln_ids)
        
        exists_map = {record["id"]: record["exists"] for record in result}
        return exists_map

def insert_batch_vulnerabilities_to_neo4j(batch_vuln_data, driver):
    #Insert a batch of vulnerability data into Neo4j with proper handling for updates vs new inserts
    try:
        # Extract the IDs
        vuln_ids = [vuln.get('id') for vuln in batch_vuln_data if vuln.get('id')]
        
        # Check which vulnerabilities already exist
        exists_map = check_if_vulnerabilities_exist(driver, vuln_ids)
        
        # Split the batch into updates and inserts
        updates = [vuln for vuln in batch_vuln_data if vuln.get('id') and exists_map.get(vuln.get('id'), False)]
        inserts = [vuln for vuln in batch_vuln_data if vuln.get('id') and not exists_map.get(vuln.get('id'), False)]
        
        # Print what we're doing
        if updates and inserts:
            print(f"Processing {len(updates)} updates and {len(inserts)} new inserts")
        elif updates:
            print(f"Updating {len(updates)} existing vulnerabilities")
        elif inserts:
            print(f"Inserting {len(inserts)} new vulnerabilities")
        
        # Process updates
        if updates:
            with driver.session() as session:
                # Clean up existing relationships for these nodes
                session.run("""
                UNWIND $ids AS id
                MATCH (v:Vulnerability {id: id})
                OPTIONAL MATCH (v)-[r]-()
                DELETE r
                """, ids=[vuln.get('id') for vuln in updates])
                
                # Then process the updates
                session.write_transaction(insert_batch_vulnerabilities, updates)
        
        # Process inserts
        if inserts:
            with driver.session() as session:
                session.write_transaction(insert_batch_vulnerabilities, inserts)
        
        print(f"Successfully processed {len(batch_vuln_data)} vulnerabilities in Neo4j.")
        return len(batch_vuln_data)
    except Exception as e:
        print(f"Error processing batch in Neo4j: {e}")
        return 0

def insert_batch_vulnerabilities(tx, batch_vuln_data):
    # Function to insert vulnerability data using the OSV schema
    query = """
    UNWIND $batch AS vuln

    MERGE (v:Vulnerability {id: vuln.id})
    SET v.summary = coalesce(vuln.summary, "unknown_summary"),
        v.details = coalesce(vuln.details, "unknown_details"),
        v.modified = coalesce(vuln.modified, "unknown_modified"),
        v.published = coalesce(vuln.published, "unknown_published"),
        v.schema_version = coalesce(vuln.schema_version, "unknown_schema_version"),
        v.withdrawn = coalesce(vuln.withdrawn, null),
        v.aliases = coalesce(vuln.aliases, []),
        v.related = coalesce(vuln.related, [])

    WITH v, vuln, vuln.severity as severityItems

    UNWIND CASE WHEN severityItems IS NULL THEN [null] ELSE severityItems END AS severityItem
    WITH v, vuln, severityItem
    WHERE severityItem IS NOT NULL
    MERGE (sev:Severity {
        type: coalesce(severityItem.type, "unknown_severity_type"),
        score: coalesce(severityItem.score, "unknown_score")
    })
    MERGE (v)-[:HAS_SEVERITY]->(sev)

    WITH v, vuln

    MERGE (repo:VULN_REPO {name: "OSV"})
    SET repo.last_updated = timestamp(), repo.minimal_versions = coalesce(repo.minimal_versions, [])

    MERGE (v)-[:BELONGS_TO]->(repo)

    WITH v, vuln.references AS references, vuln.affected AS affectedItems, vuln.credits AS credits, vuln.database_specific AS database_specific

    SET v.database_specific = CASE
        WHEN database_specific IS NULL THEN null
        ELSE apoc.convert.toJson(database_specific)
    END

    WITH v, references, affectedItems, credits

    UNWIND references AS reference
    MERGE (r:Reference {url: coalesce(reference.url, "unknown_url"), type: coalesce(reference.type, "unknown_reference_type")})
    MERGE (v)-[:HAS_REFERENCE]->(r)

    WITH v, affectedItems, credits

    UNWIND affectedItems AS affectedItem
    MERGE (p:Package {name: coalesce(affectedItem.package.name, "unknown_package_name"),
                                    ecosystem: coalesce(affectedItem.package.ecosystem, "unknown_ecosystem"),
                                    purl: coalesce(affectedItem.package.purl, "unknown_purl")})

    MERGE (v)-[:AFFECTS]->(p)
    SET p.versions = coalesce(affectedItem.versions, [])

    SET p.ecosystem_specific = CASE
        WHEN affectedItem.ecosystem_specific IS NULL THEN null
        ELSE apoc.convert.toJson(affectedItem.ecosystem_specific)
    END,
    p.database_specific = CASE
        WHEN affectedItem.database_specific IS NULL THEN null
        ELSE apoc.convert.toJson(affectedItem.database_specific)
    END

    WITH v, affectedItem, p, credits
    UNWIND CASE WHEN affectedItem.severity IS NULL THEN [null] ELSE affectedItem.severity END AS severityItem
    WITH v, affectedItem, p, credits, severityItem
    WHERE severityItem IS NOT NULL

    MERGE (sev:PackageSeverity {
        type: coalesce(severityItem.type, "unknown_severity_type"),
        score: coalesce(severityItem.score, "unknown_score")
    })
    MERGE (p)-[:HAS_SEVERITY]->(sev)

    WITH v, affectedItem, p, credits

    UNWIND affectedItem.ranges AS range
    WITH v, p, range, credits // Carry p into the range UNWIND
    MERGE (ra:Range {type: coalesce(range.type, "unknown_range_type")})
    MERGE (p)-[:HAS_RANGE]->(ra)

    SET ra.database_specific = CASE
        WHEN range.database_specific IS NULL THEN null
        ELSE apoc.convert.toJson(range.database_specific)
    END

    WITH v, p, ra, range, credits

    UNWIND range.events AS event
    MERGE (e:Event {introduced: coalesce(event.introduced, "unknown_introduced"),
                                    fixed: coalesce(event.fixed, "unknown_fixed"),
                                    last_affected: coalesce(event.last_affected, "unknown_last_affected"),
                                    limit: coalesce(event.limit, "unknown_limit")})
    MERGE (ra)-[:HAS_EVENT]->(e)

    WITH v, credits

    UNWIND credits AS credit
    MERGE (c:Credit {name: coalesce(credit.name, "unknown_name"),
                                    type: coalesce(credit.type, "unknown_credit_type")})
    MERGE (v)-[:HAS_CREDIT]->(c)

    WITH c, credit.contact AS contacts

    UNWIND contacts as contact
    MERGE (co:Contact {contact: coalesce(contact, "unknown_contact")})
    MERGE (c)-[:HAS_CONTACT]->(co)
    """
    tx.run(query, batch=batch_vuln_data)

def load_vulnerability_ids(file_path):
    """Load vulnerability IDs from a JSON file."""
    with open(file_path, 'r') as file:
        vuln_ids = json.load(file)
    return vuln_ids

def create_indexes(driver):
    """Create database indexes to optimize Neo4j performance."""
    with driver.session() as session:
        # Create indexes for all node types to optimize MERGE operations
        session.run("CREATE INDEX vulnerability_id_index IF NOT EXISTS FOR (v:Vulnerability) ON (v.id)")
        session.run("CREATE INDEX reference_url_index IF NOT EXISTS FOR (r:Reference) ON (r.url)")
        session.run("CREATE INDEX package_composite_index IF NOT EXISTS FOR (p:Package) ON (p.name, p.ecosystem, p.purl)")
        session.run("CREATE INDEX range_composite_index IF NOT EXISTS FOR (r:Range) ON (r.type, r.repo)")
        session.run("CREATE INDEX event_composite_index IF NOT EXISTS FOR (e:Event) ON (e.introduced, e.fixed)")
        session.run("CREATE INDEX credit_name_index IF NOT EXISTS FOR (c:Credit) ON (c.name)")
        session.run("CREATE INDEX contact_index IF NOT EXISTS FOR (c:Contact) ON (c.contact)")
        session.run("CREATE INDEX severity_composite_index IF NOT EXISTS FOR (s:Severity) ON (s.type, s.score)")
        session.run("CREATE INDEX package_severity_composite_index IF NOT EXISTS FOR (s:PackageSeverity) ON (s.type, s.score)")
        print("Created Neo4j indexes for all node types")

def cleanup_duplicates(driver):
    # Find and merge duplicated vulnerability nodes
    with driver.session() as session:
        print("Checking for duplicate vulnerability nodes...")
        result = session.run("""
        MATCH (v:Vulnerability)
        WITH v.id AS id, collect(v) AS nodes
        WHERE size(nodes) > 1
        RETURN id, size(nodes) AS count
        """)
        
        duplicates = {record["id"]: record["count"] for record in result}
        
        if duplicates:
            print(f"Found {len(duplicates)} vulnerability IDs with duplicate nodes")
            
            # Use APOC to merge duplicate nodes
            for dup_id, count in duplicates.items():
                try:
                    print(f"Merging {count} duplicates for ID: {dup_id}")
                    session.run("""
                    MATCH (v:Vulnerability {id: $id})
                    WITH collect(v) AS duplicates
                    CALL apoc.refactor.mergeNodes(duplicates, {properties: 'combine'})
                    YIELD node
                    RETURN count(node) AS merged
                    """, id=dup_id)
                except Exception as e:
                    print(f"Error merging duplicates for {dup_id}: {e}")
            
            print(f"Merged {len(duplicates)} sets of duplicate nodes")
        else:
            print("No duplicate vulnerability nodes found.")

def remove_obsolete_vulnerabilities(driver, current_vuln_ids):
    """Remove vulnerabilities from Neo4j that no longer exist in the current ID list."""
    current_ids_set = set(current_vuln_ids)
    
    with driver.session() as session:
        # Get all vulnerability IDs from Neo4j
        result = session.run("MATCH (v:Vulnerability) RETURN v.id as id")
        neo4j_ids = [record["id"] for record in result]
        
        # Find IDs that exist in Neo4j but not in the current ID list
        to_remove = [vid for vid in neo4j_ids if vid not in current_ids_set]
        
        if to_remove:
            print(f"Found {len(to_remove)} obsolete vulnerabilities to remove from Neo4j")
            
            # Delete in smaller batches to avoid transaction timeouts
            batch_size = 500
            for i in range(0, len(to_remove), batch_size):
                batch = to_remove[i:i+batch_size]
                # Delete these vulnerabilities and their relationships
                session.run("""
                UNWIND $ids AS id
                MATCH (v:Vulnerability {id: id})
                OPTIONAL MATCH (v)-[r]-()
                DELETE r, v
                """, ids=batch)
                print(f"Removed batch of {len(batch)} obsolete vulnerabilities")
            
            print(f"Successfully removed {len(to_remove)} obsolete vulnerabilities")
        else:
            print("No obsolete vulnerabilities found")
            
    return len(to_remove) if to_remove else 0

def neo4j_worker(batch_data, driver):
    # Handle Neo4j insertion in a separate thread
    return insert_batch_vulnerabilities_to_neo4j(batch_data, driver)

async def process_in_batches(vuln_ids, batch_size, driver, max_concurrent_batches):
    # Process vulnerability data in batches with concurrency
    semaphore = asyncio.Semaphore(100)
    total_vulnerabilities = len(vuln_ids)
    processed_count = 0
    start_total = time.time()

    # Create a thread pool for Neo4j operations
    thread_pool = ThreadPoolExecutor(max_workers=max_concurrent_batches)
    neo4j_futures = []

    # Check for duplicates periodically
    duplicate_check_interval = 1000

    # Split into chunks for progress reporting
    chunk_size = 1000
    for chunk_start in range(0, total_vulnerabilities, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_vulnerabilities)
        chunk_ids = vuln_ids[chunk_start:chunk_end]

        # Process the chunk in batches
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as session:
            for i in range(0, len(chunk_ids), batch_size):
                batch_ids = chunk_ids[i:i + batch_size]
                batch_start_time = time.time()

                # Fetch all vulnerability data concurrently
                tasks = [fetch_vulnerability_data(vuln_id, session, semaphore) for vuln_id in batch_ids]
                results = await asyncio.gather(*tasks)
                batch_vuln_data = [vuln_data for vuln_data in results if vuln_data]

                if batch_vuln_data:
                    # Submit Neo4j processing to thread pool
                    future = thread_pool.submit(neo4j_worker, batch_vuln_data, driver)
                    neo4j_futures.append(future)

                    # Limit number of concurrent Neo4j operations
                    while len([f for f in neo4j_futures if not f.done()]) >= max_concurrent_batches:
                        await asyncio.sleep(0.1)

                    # Check for completed futures
                    for future in [f for f in neo4j_futures if f.done()]:
                        try:
                            processed_count += future.result()
                            neo4j_futures.remove(future)
                        except Exception as e:
                            print(f"Error in Neo4j worker: {e}")

                batch_time = time.time() - batch_start_time
                print(f"Batch of {len(batch_vuln_data)} processed in {batch_time:.2f}s. " +
                      f"Progress: {processed_count}/{total_vulnerabilities} " +
                      f"({(processed_count/total_vulnerabilities*100):.2f}%)")
                
                # Check for duplicates periodically
                if processed_count % duplicate_check_interval == 0 and processed_count > 0:
                    print(f"Periodic duplicate check at {processed_count} vulnerabilities...")
                    cleanup_duplicates(driver)

        # After each chunk, report overall progress
        elapsed = time.time() - start_total
        if chunk_end > 0:  # Prevent division by zero
            remaining = (elapsed / chunk_end) * (total_vulnerabilities - chunk_end)
            print(f"Completed chunk {chunk_start//chunk_size + 1}/{(total_vulnerabilities + chunk_size - 1)//chunk_size}. " +
                  f"Elapsed: {elapsed/60:.1f}m, Estimated remaining: {remaining/60:.1f}m")

    # Wait for remaining Neo4j operations to complete
    for future in neo4j_futures:
        try:
            processed_count += future.result()
        except Exception as e:
            print(f"Error in Neo4j worker: {e}")

    thread_pool.shutdown()

    # Final duplicate check
    print("Performing final duplicate check...")
    cleanup_duplicates(driver)

    total_time = time.time() - start_total
    print(f"Total processing time: {total_time/60:.2f} minutes")
    print(f"Average processing speed: {total_vulnerabilities/total_time:.2f} vulnerabilities/second")

async def main():
    # Main function to coordinate the entire ETL process
    # Configuration parameters
    batch_size = 50
    max_concurrent_neo4j_batches = 2  # Control number of concurrent Neo4j transactions

    # Process in chunks with progress tracking
    driver = get_neo4j_driver()
    print("first flag")
    if driver:
        print("second flag")
        # Check if APOC is installed using a query that works across versions
        with driver.session() as session:
            try:
                result = session.run("CALL apoc.help('apoc.convert.toJson')")  # check if a apoc function exists.
                if not result.peek():
                    print("ERROR: APOC extension is not installed in Neo4j. Please install APOC before running this script.")
                    print("Installation instructions: https://neo4j.com/labs/apoc/4.4/installation/")
                    return
            except Exception as e:
                print(f"Error checking for APOC: {e}")
                print("ERROR: APOC extension is not installed in Neo4j. Please install APOC before running this script.")
                print("Installation instructions: https://neo4j.com/labs/apoc/4.4/installation/")
                return

        # Clean up existing vulnerabilities with '1.6.0' as ID
        with driver.session() as session:
            try:
                result = session.run("MATCH (v:Vulnerability {id: '1.6.0'}) DETACH DELETE v RETURN count(*) as count")
                deleted_count = result.single()["count"]
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} vulnerabilities with incorrect ID '1.6.0'")
            except Exception as e:
                print(f"Error cleaning up incorrect vulnerabilities: {e}")

        # Clean up any duplicate vulnerability nodes
        print("Running initial duplicate cleanup...")
        cleanup_duplicates(driver)

        # Create indexes to optimize database performance
        create_indexes(driver)

        vuln_ids = load_vulnerability_ids("osv/all_vulnerability_ids.json")
        print(f"Loaded {len(vuln_ids)} vulnerability IDs for processing")

        # Remove obsolete vulnerabilities
        removed_count = remove_obsolete_vulnerabilities(driver, current_vuln_ids=vuln_ids)
        print(f"Removed {removed_count} obsolete vulnerabilities from Neo4j")

        checkpoint_file = "checkpoint.json"
        start_index = 0
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                start_index = checkpoint.get("last_processed_index", 0)
                if start_index > 0:
                    print(f"Resuming from index {start_index} ({start_index/len(vuln_ids)*100:.2f}% complete)")
                    vuln_ids = vuln_ids[start_index:]
        except FileNotFoundError:
            print("No checkpoint found, starting from the beginning")

        try:
            await process_in_batches(vuln_ids, batch_size, driver, max_concurrent_neo4j_batches)
            # Save final checkpoint upon successful completion
            with open(checkpoint_file, 'w') as f:
                json.dump({"last_processed_index": len(vuln_ids) + start_index, "completed": True}, f)
            print("Processing completed successfully")
        except KeyboardInterrupt:
            # Save checkpoint on interrupt
            with open(checkpoint_file, 'w') as f:
                checkpoint_index = start_index + (len(load_vulnerability_ids("all_vulnerability_ids.json")) - len(vuln_ids))
                json.dump({"last_processed_index": checkpoint_index, "completed": False}, f)
            print(f"Process interrupted, checkpoint saved at index {checkpoint_index}.")
        except Exception as e:
            print(f"Unexpected error: {e}")
            # Save checkpoint on error
            with open(checkpoint_file, 'w') as f:
                checkpoint_index = start_index + (len(load_vulnerability_ids("all_vulnerability_ids.json")) - len(vuln_ids))
                json.dump({"last_processed_index": checkpoint_index, "completed": False, "error": str(e)}, f)
            print(f"Error occurred, checkpoint saved at index {checkpoint_index}.")
        finally:
            driver.close()
    else:
        print("Failed to connect to Neo4j database")

async def load_osv():
    main()
    
if __name__ == "__main__":
    asyncio.run(main())