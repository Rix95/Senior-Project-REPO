#!/usr/bin/env python3
"""
Script to connect to Neo4j, query vulnerability data, and generate minimal version sets
that cover all CVEs for each package.
"""
import argparse
from neo4j import GraphDatabase
import json
import time
from datetime import datetime
from collections import defaultdict
from ..osv.neo4j_connection import get_neo4j_driver

class VulnerabilityProcessor:
    def __init__(self, batch_size=5000):
        self._driver = None
        self.batch_size = batch_size  # Number of records to process in each batch
        
    def connect(self):
        self._driver = get_neo4j_driver()
        return self._driver is not None
        
    def close(self):
        """Close the Neo4j connection if open"""
        if self._driver:
            self._driver.close()
            print("Neo4j connection closed.")
    
    def get_vulnerability_count(self, repo_name="OSV"):
        """Get the total count of vulnerabilities in the database for a specific repo"""
        if not self._driver:
            print("Error: Not connected to Neo4j. Call connect() first.")
            return 0
            
        with self._driver.session() as session:
            query = """
            MATCH (v:Vulnerability)-[:BELONGS_TO]->(vr:VULN_REPO)
            MATCH (v)-[:AFFECTS]->(p:Package)
            WHERE vr.name = $repo_name
            RETURN COUNT(*) AS count
            """
            result = session.run(query, {"repo_name": repo_name})
            record = result.single()
            return record["count"] if record else 0
    
    def get_package_vulnerability_data(self, repo_name="OSV", progress_interval=10000):
        """
        Query Neo4j to get package vulnerability data by repository
        """
        if not self._driver:
            print("Error: Not connected to Neo4j. Call connect() first.")
            return {}
            
        package_cve_data = {}
        processed_count = 0
        start_time = time.time()
        
        total_count = self.get_vulnerability_count(repo_name)
        print(f"Processing {total_count} vulnerability relationships for repo '{repo_name}'...")
        
        with self._driver.session() as session:
            query = """
                MATCH (v:Vulnerability)-[:BELONGS_TO]->(vr:VULN_REPO)
                MATCH (v)-[:AFFECTS]->(p:Package)
                WHERE vr.name = $repo_name
                RETURN p.name AS package_name, p.ecosystem AS ecosystem, p.purl AS purl, 
                       v.id AS vuln_id, p.versions AS affected_versions
                ORDER BY p.name, v.id
            """
            
            result = session.run(query, {"repo_name": repo_name})
            
            for record in result:
                package_name = record['package_name']
                ecosystem = record['ecosystem']
                purl = record.get('purl', None)
                vuln_id = record['vuln_id']
                affected_versions = record['affected_versions']
                
                # Create package entry if it doesn't exist
                if package_name not in package_cve_data:
                    package_cve_data[package_name] = {
                        'ecosystem': ecosystem,
                        'purl': purl or ''
                    }
                
                # Process affected versions
                if isinstance(affected_versions, list):
                    versions = affected_versions
                else:
                    versions = [affected_versions]
                
                # Add vulnerability and its versions
                if vuln_id not in package_cve_data[package_name]:
                    package_cve_data[package_name][vuln_id] = list(set(versions))
                else:
                    # Merge versions if vulnerability already exists
                    existing_versions = set(package_cve_data[package_name][vuln_id])
                    existing_versions.update(versions)
                    package_cve_data[package_name][vuln_id] = list(existing_versions)
                
                processed_count += 1
                
                if processed_count % progress_interval == 0:
                    elapsed = time.time() - start_time
                    percent = (processed_count / total_count) * 100 if total_count > 0 else 0
                    records_per_second = processed_count / elapsed if elapsed > 0 else 0
                    eta_seconds = (total_count - processed_count) / records_per_second if records_per_second > 0 else 0
                    
                    print(f"Progress: {processed_count}/{total_count} ({percent:.1f}%) - "
                          f"Speed: {records_per_second:.1f} records/sec - "
                          f"ETA: {datetime.fromtimestamp(time.time() + eta_seconds).strftime('%H:%M:%S')}")
        
        print(f"Completed processing {processed_count} records in {time.time() - start_time:.1f} seconds")
        
        return package_cve_data
    
    def generate_minimal_version_sets(self, package_cve_data):
        """
        Generate a minimal set of versions that covers all CVEs for each package
        """
        minimal_version_sets = {}
        
        for package_name, package_data in package_cve_data.items():
            # Extract all vulnerability IDs and their affected versions
            ecosystem = package_data.get('ecosystem', '')
            purl = package_data.get('purl', '')
            
            # Create a clean mapping of vulnerability ID to affected versions
            vuln_to_versions = defaultdict(set)
            
            for key, value in package_data.items():
                if key not in ['ecosystem', 'purl']:
                    vuln_id = key
                    # Convert to set to eliminate duplicates
                    versions = set(value)
                    vuln_to_versions[vuln_id].update(versions)
            
            if not vuln_to_versions:
                # No vulnerabilities for this package
                minimal_version_sets[package_name] = {
                    "ecosystem": ecosystem,
                    "purl": purl,
                    "minimal_versions": [],
                    "total_vulnerabilities": 0,
                    "covered_by_minimal_set": 0
                }
                continue
                
            # Create a version-to-vulnerabilities mapping
            version_vuln_map = defaultdict(set)
            for vuln_id, versions in vuln_to_versions.items():
                for version in versions:
                    version_vuln_map[version].add(vuln_id)
            
            # Greedy algorithm to find minimal version sets
            all_vulns = set(vuln_to_versions.keys())
            remaining_vulns = set(all_vulns)
            selected_versions = []
            
            while remaining_vulns:
                # Find the version that covers the most remaining vulnerabilities
                best_version = None
                most_covered = 0
                
                for version, vulns in version_vuln_map.items():
                    covered = len(vulns.intersection(remaining_vulns))
                    if covered > most_covered:
                        most_covered = covered
                        best_version = version
                
                if best_version is None or most_covered == 0:
                    # No more versions can cover remaining vulnerabilities
                    break
                    
                # Add the best version
                selected_versions.append(best_version)
                remaining_vulns -= version_vuln_map[best_version]
            
            # Calculate the total vulnerabilities covered by the minimal set
            covered_vulns = set()
            for version in selected_versions:
                covered_vulns.update(version_vuln_map[version])
            
            # Add the package and its minimal version set to the result
            minimal_version_sets[package_name] = {
                "ecosystem": ecosystem,
                "purl": purl,
                "minimal_versions": selected_versions,
                "total_vulnerabilities": len(all_vulns),
                "covered_by_minimal_set": len(covered_vulns)
            }
        
        return minimal_version_sets
    
    def save_minimal_version_sets(self, minimal_version_sets, output_file):
        """Save the minimal version sets to a JSON file"""
        try:
            with open(output_file, 'w') as f:
                json.dump(minimal_version_sets, f, indent=2)
            print(f"Minimal version sets saved to {output_file}")
            return True
        except Exception as e:
            print(f"Error saving JSON file: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Generate minimal version sets from Neo4j vulnerability data')
    parser.add_argument('--output', '-o', help='Output JSON file name', default='minimal_version_sets.json')
    parser.add_argument('--repo', help='Repository name to query (e.g., OSV)', default='OSV')
    parser.add_argument('--batch-size', type=int, help='Batch size for processing', default=5000)
    parser.add_argument('--progress-interval', type=int, help='Progress update interval', default=10000)
    
    args = parser.parse_args()
    
    processor = VulnerabilityProcessor(batch_size=args.batch_size)
    
    try:
        if processor.connect():
            print("Successfully connected to Neo4j database.")
            
            # Get vulnerability data from Neo4j
            print(f"Querying vulnerability data for repository '{args.repo}'...")
            package_cve_data = processor.get_package_vulnerability_data(
                repo_name=args.repo,
                progress_interval=args.progress_interval
            )
            
            if not package_cve_data:
                print("No data retrieved from Neo4j. Exiting.")
                return
            
            # Generate minimal version sets
            print(f"Generating minimal version sets for {len(package_cve_data)} packages...")
            minimal_version_sets = processor.generate_minimal_version_sets(package_cve_data)
            
            # Save to file
            processor.save_minimal_version_sets(minimal_version_sets, args.output)
            
            # Print statistics
            total_versions_count = 0
            total_vulns_count = 0
            
            for package_name, package_data in package_cve_data.items():
                unique_versions = set()
                for key, versions in package_data.items():
                    if key not in ['ecosystem', 'purl'] and versions:
                        unique_versions.update(versions)
                total_versions_count += len(unique_versions)
            
            minimal_versions_count = sum(len(data["minimal_versions"]) for data in minimal_version_sets.values())
            total_vulns_count = sum(data["total_vulnerabilities"] for data in minimal_version_sets.values())
            
            print(f"Total vulnerabilities found: {total_vulns_count}")
            print(f"Total unique versions in original data: {total_versions_count}")
            print(f"Total versions in minimal sets: {minimal_versions_count}")
            if total_versions_count > 0:
                print(f"Reduction: {(1 - minimal_versions_count/total_versions_count)*100:.1f}%")
        else:
            print("Failed to connect to Neo4j database.")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        processor.close()

if __name__ == "__main__":
    main()