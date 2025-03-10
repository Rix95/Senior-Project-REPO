import os
import json
import time
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = "ecosystem_data"
OUTPUT_FILE = "src/[old]backend/all_vulnerability_ids.json"

vulnerability_ids = []
file_count = 0
total_files = 0

# Count the total number of files first for progress tracking
for ecosystem in os.listdir(BASE_DIR):
    ecosystem_path = os.path.join(BASE_DIR, ecosystem)
    if os.path.isdir(ecosystem_path):
        for filename in os.listdir(ecosystem_path):
            if filename.endswith(".json"):
                total_files += 1

# Function to process each file
def process_file(file_path):
    global file_count
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            vuln_id = data.get("id")
            if vuln_id:
                vulnerability_ids.append(vuln_id)
                file_count += 1
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

start_time = time.time()  # Start timing

# Create a ThreadPoolExecutor for parallel processing
with ThreadPoolExecutor() as executor:
    # Gather all file paths first
    file_paths = []
    for ecosystem in os.listdir(BASE_DIR):
        ecosystem_path = os.path.join(BASE_DIR, ecosystem)
        if os.path.isdir(ecosystem_path):
            for filename in os.listdir(ecosystem_path):
                if filename.endswith(".json"):
                    file_paths.append(os.path.join(ecosystem_path, filename))

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
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(vulnerability_ids, f, indent=4)

# Final results
print(f"\n✅ Processed {file_count} JSON files in {elapsed_time:.2f} seconds.")
print(f"⏳ Estimated time per file: {elapsed_time/file_count:.4f} sec")