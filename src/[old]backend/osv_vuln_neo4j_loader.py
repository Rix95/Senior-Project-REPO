'''
Before running this file, follow these steps:
1. Run `download_ecosystem_data.py` to download / update vulnerability information. 
2. Run fetch_osv_ids. Wait for `all_vulnerability_ids.json` to be created / updated.

This file will populate neo4j for the first time. It can be ran again to update the database with
the new information. 
```