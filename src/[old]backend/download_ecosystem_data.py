import os  # For creating directories and file paths
import requests  # For sending HTTP requests to download the data
import concurrent.futures  # For parallel execution of tasks
from zipfile import ZipFile  # For extracting ZIP files

# List of ecosystems that we want to download data for
ecosystems = [
    "AlmaLinux", "Alpine", "Android", "Bitnami", "CRAN", "Chainguard", "Debian",
    "GIT", "GSD", "GitHub Actions", "Go", "Hackage", "Hex", "Linux", "Mageia",
    "Maven", "NuGet", "OSS-Fuzz", "Packagist", "Pub", "PyPI", "Red Hat",
    "Rocky Linux", "RubyGems", "SUSE", "SwiftURL", "UVI", "Ubuntu", "Wolfi",
    "crates.io", "npm", "openSUSE"
]

# Base URL for downloading the files
base_url = "https://osv-vulnerabilities.storage.googleapis.com/"

# Directory where the ecosystem data will be saved
download_dir = "ecosystem_data"
os.makedirs(download_dir, exist_ok=True)  # Create the main directory if it doesn't exist

# Function to download and extract the ZIP file for a given ecosystem
def download_and_extract(ecosystem):
    try:
        print(f"Starting download for {ecosystem}...")

        # URL for the ecosystem data
        url = f"{base_url}{ecosystem}/all.zip"
        
        # Create a directory for the ecosystem if it doesn't exist
        ecosystem_path = os.path.join(download_dir, ecosystem)
        os.makedirs(ecosystem_path, exist_ok=True)  # Create ecosystem-specific directory

        # Send HTTP request to download the ZIP file
        response = requests.get(url)
        
        # Check if the download was successful
        if response.status_code == 200:
            # Define the path to save the ZIP file
            zip_file_path = os.path.join(ecosystem_path, f"{ecosystem}_vulnerabilities.zip")
            
            # Write the content of the downloaded file to the disk
            with open(zip_file_path, 'wb') as f:
                f.write(response.content)
            print(f"Download complete for {ecosystem}. Extracting...")

            # Extract the ZIP file
            with ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(ecosystem_path)  # Extract to ecosystem folder
            print(f"Extraction complete for {ecosystem}.")
        else:
            print(f"Failed to download {ecosystem}, status code {response.status_code}.")
    
    except Exception as e:
        print(f"Error downloading and extracting {ecosystem}: {e}")

# Function to download and extract data for all ecosystems using parallel processing
def download_all_ecosystems():
    # Using ThreadPoolExecutor for parallel downloading and extracting
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_and_extract, ecosystems)

# Main entry point of the script
if __name__ == "__main__":
    print("Starting download and extraction process for all ecosystems...")
    
    # Start the download and extraction process
    download_all_ecosystems()

    print("Download and extraction process completed.")