import os
import requests
import concurrent.futures
from zipfile import ZipFile
import shutil  # For directory operations

# Base URL for downloading OSV data
base_url = "https://osv-vulnerabilities.storage.googleapis.com/"

# Directory for storing ecosystem data
download_dir = "Senior-Project-REPO/src/[old]backend/ecosystem_data"
os.makedirs(download_dir, exist_ok=True)

# List of ecosystems
ecosystems = [
    "AlmaLinux", "Alpine", "Android", "Bitnami", "CRAN", "Chainguard", "Debian",
    "GIT", "GSD", "GitHub Actions", "Go", "Hackage", "Hex", "Linux", "Mageia",
    "Maven", "NuGet", "OSS-Fuzz", "Packagist", "Pub", "PyPI", "Red Hat",
    "Rocky Linux", "RubyGems", "SUSE", "SwiftURL", "UVI", "Ubuntu", "Wolfi",
    "crates.io", "npm", "openSUSE"
]

# Function to download and extract new ecosystem data
def download_and_extract(ecosystem):
    try:
        print(f"Starting synchronization for {ecosystem}...")

        # URL for downloading the ecosystem data
        url = f"{base_url}{ecosystem}/all.zip"
        
        # Create a temporary directory for this update
        temp_dir = os.path.join(download_dir, f"{ecosystem}_temp")
        os.makedirs(temp_dir, exist_ok=True)

        # Path for the downloaded ZIP file
        zip_file_path = os.path.join(temp_dir, f"{ecosystem}_vulnerabilities.zip")
        response = requests.get(url)

        if response.status_code == 200:
            # Save the ZIP file to the temporary directory
            with open(zip_file_path, 'wb') as f:
                f.write(response.content)
            print(f"Download complete for {ecosystem}. Extracting...")

            # Extract the ZIP file to the temporary directory
            with ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Define the final ecosystem directory
            final_dir = os.path.join(download_dir, ecosystem)

            # If the final directory exists, remove it
            if os.path.exists(final_dir):
                shutil.rmtree(final_dir)

            # Rename the temporary directory to the final ecosystem directory
            os.rename(temp_dir, final_dir)
            print(f"Synchronization complete for {ecosystem}.")
        else:
            print(f"Failed to download {ecosystem}, status code {response.status_code}.")
            # Clean up the temporary directory if download failed
            shutil.rmtree(temp_dir)

    except Exception as e:
        print(f"Error synchronizing {ecosystem}: {e}")
        # Clean up the temporary directory in case of error
        temp_dir = os.path.join(download_dir, f"{ecosystem}_temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# Function to download and extract all ecosystems in parallel
def download_and_extract_all_ecosystems():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_and_extract, ecosystems)

# Run the script
if __name__ == "__main__":
    print("Starting synchronization process for all ecosystems...")
    download_and_extract_all_ecosystems()
    print("Synchronization process completed.")
