#!/usr/bin/env python3
from src.backend.api.osv.vulnerability_repo_mapper import run_complete_pipeline

if __name__ == "__main__":
    print("Starting minimum hitting sets pipeline...")
    final_report = run_complete_pipeline()
    print("Pipeline completed!")

