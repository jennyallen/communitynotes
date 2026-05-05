import os
import requests
import zipfile
from datetime import datetime

def create_directories():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/ratings', exist_ok=True)

def download_and_unzip(url, folder):
    filename = url.split('/')[-1]
    filepath = os.path.join(folder, filename)

    print(f"Downloading {filename}...")
    response = requests.get(url)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"Unzipping {filename}...")
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(folder)

        os.remove(filepath)  # Remove zip after extraction
        print(f"✓ {filename} completed")
        return True
    else:
        print(f"✗ Failed to download {filename}")
        return False

def main():
    create_directories()

    # Use today's date
    date = datetime.now()
    date_path = f"{date.year}/{date.month:02d}/{date.day:02d}"
    base_url = f"https://ton.twimg.com/birdwatch-public-data/{date_path}"

    print(f"Downloading Community Notes data for {date.strftime('%Y-%m-%d')}")

    # Download main files
    download_and_unzip(f"{base_url}/notes/notes-00000.zip", 'data')
    download_and_unzip(f"{base_url}/noteStatusHistory/noteStatusHistory-00000.zip", 'data')
    download_and_unzip(f"{base_url}/userEnrollment/userEnrollment-00000.zip", 'data')

    # Download ratings files (00000 to 00019)
    for i in range(20):
        filename = f"ratings-{i:05d}.zip"
        url = f"{base_url}/noteRatings/{filename}"
        download_and_unzip(url, 'data/ratings')

    print("Download complete!")

if __name__ == "__main__":
    main()
