import os
import json
import time
from concurrent.futures import ThreadPoolExecutor

def extract_vulnerability_ids(base_dir="osv/ecosystem_data", output_file="osv/all_vulnerability_ids.json"):
    print("testy testy test")
    vulnerability_ids = []
    file_paths = []
    total_files = 0

    # Count the total number of files first for progress tracking
    print(os.listdir(base_dir))
    for ecosystem in os.listdir(base_dir):
        ecosystem_path = os.path.join(base_dir, ecosystem)
        
        if os.path.isdir(ecosystem_path):
            for filename in os.listdir(ecosystem_path):
                if filename.endswith(".json"):
                    total_files += 1
    print("totalfiles: ", total_files)
    def process_file(file_path):
        print("process file . - _ . -")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                vuln_id = data.get("id")
                if vuln_id:
                    vulnerability_ids.append(vuln_id)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    start_time = time.time()  # Start timing

    # Create a ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor() as executor:
        # Gather all file paths first
        file_paths = []
        for ecosystem in os.listdir(base_dir):
            ecosystem_path = os.path.join(base_dir, ecosystem)
            if os.path.isdir(ecosystem_path):
                for filename in os.listdir(ecosystem_path):
                    if filename.endswith(".json"):
                        file_paths.append(os.path.join(ecosystem_path, filename))
        print("line 45", file_paths)
        # Submit the file processing tasks to the executor
        futures = [executor.submit(process_file, file_path) for file_path in file_paths]

        # Progress tracking
        processed_count = 0
        for future in futures:
            future.result()
            processed_count += 1
            percent_complete = (processed_count / total_files) * 100
            elapsed_time = time.time() - start_time
            print(f"\rProgress: [{processed_count}/{total_files}] {percent_complete:.2f}% | Elapsed: {elapsed_time:.2f} sec", end="")

    end_time = time.time()  # End timing
    elapsed_time = end_time - start_time

    # Save extracted IDs into a separate JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(vulnerability_ids, f, indent=4)

    # Final results
    print(f"\n✅ Processed {total_files} JSON files in {elapsed_time:.2f} seconds.")
    print(f"⏳ Estimated time per file: {elapsed_time/total_files:.4f} sec")



    