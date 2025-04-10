from osv.vulnerability_repo_mapper import find_minimum_hitting_set
import json

def test_ubuntu_cve_minimum_hitting_set():
    """
    Test function that uses the Ubuntu CVE-2022-40281 data to verify the 
    minimum hitting set algorithm works correctly with real-world data.
    """
    # Create the dataset based on the image you shared
    ubuntu_cve_data = {
        "UBUNTU-CVE-2022-40281": [
            ["0.0.19-1", "0.0.20-1", "0.0.18-2"],
            ["0.0.22-3.1", "0.0.21-2", "0.0.22-1", "0.0.22-4", "0.0.22-2", "0.0.22-3build1", "0.0.22-3"],
            ["0.0.23.1-4build1", "0.0.23.1-4ubuntu1", "0.0.23.1-4ubuntu2", "0.0.23.1-4ubuntu3"],
            ["0.0.25b-1.1ubuntu1", "0.0.25b-2", "0.0.25b-1", "0.0.25b-1.1"],
            ["0.0.26-6ubuntu0.24.10.1"]
        ]
    }
    
    # Flatten the version lists for processing
    cve_version_lists = ubuntu_cve_data["UBUNTU-CVE-2022-40281"]
    
    # Create recency scores based on version strings
    all_versions = set()
    for version_list in cve_version_lists:
        all_versions.update(version_list)
    
    # Simple recency scores
    sorted_versions = sorted(list(all_versions))
    version_recency = {v: 100 + i for i, v in enumerate(sorted_versions)}
    
    try:
        # Run the algorithm
        result = find_minimum_hitting_set(cve_version_lists, version_recency)
        
        # Validate the result
        validation = {
            "covers_all_cves": True,
            "is_minimal": True,
            "details": []
        }
        
        # Check if the result covers all CVE entries
        for i, cve_list in enumerate(cve_version_lists):
            covered = any(version in result for version in cve_list)
            if not covered:
                validation["covers_all_cves"] = False
                validation["details"].append(f"Version list {i+1} not covered by the solution")
        
        # Check if it's minimal (can't remove any version)
        for version in result:
            # Try removing this version
            test_set = [v for v in result if v != version]
            
            # Check if this reduced set still covers all CVEs
            all_covered = True
            for cve_list in cve_version_lists:
                if not any(v in test_set for v in cve_list):
                    all_covered = False
                    break
            
            if all_covered:
                validation["is_minimal"] = False
                validation["details"].append(f"Version {version} could be removed")
                
        # Coverage details
        coverage_details = []
        for i, version_list in enumerate(cve_version_lists):
            covered_by = [v for v in result if v in version_list]
            coverage_details.append({
                "version_list_index": i,
                "versions": version_list,
                "covered_by": covered_by
            })
            
        output = {
            "input_data": {
                "cve_data": ubuntu_cve_data,
                "version_recency": version_recency
            },
            "result": {
                "minimal_hitting_set": result,
                "set_size": len(result),
                "recency_score": sum(version_recency.get(v, 0) for v in result)
            },
            "validation": validation,
            "coverage_details": coverage_details
        }
        
        return output
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    result = test_ubuntu_cve_minimum_hitting_set()
    print(json.dumps(result, indent=2))