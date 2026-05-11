import os
import urllib.request
import zipfile
import shutil

def download_and_extract(url, extract_to):
    os.makedirs(extract_to, exist_ok=True)
    zip_path = os.path.join(extract_to, "dataset.zip")
    
    print(f"Downloading {url}...")
    # Add User-Agent header to avoid 403 Forbidden errors
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
            
        print(f"Done extracting to {extract_to}.")
    except Exception as e:
        print(f"Error processing {url}: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

if __name__ == "__main__":
    base_dir = "./datasets"
    os.makedirs(base_dir, exist_ok=True)
    
    # SQuAD
    squad_dir = os.path.join(base_dir, "squad")
    os.makedirs(squad_dir, exist_ok=True)
    with open(os.path.join(squad_dir, ".gitignore"), "w") as f:
        f.write("# Automatically generated\n*")
    squad_url = "https://www.kaggle.com/api/v1/datasets/download/stanfordu/stanford-question-answering-dataset"
    download_and_extract(squad_url, squad_dir)
    
    # HotpotQA
    hotpotqa_dir = os.path.join(base_dir, "hotpotqa")
    os.makedirs(hotpotqa_dir, exist_ok=True)
    with open(os.path.join(hotpotqa_dir, ".gitignore"), "w") as f:
        f.write("# Automatically generated\n*")
    hotpotqa_url = "https://www.kaggle.com/api/v1/datasets/download/jeromeblanchet/hotpotqa-question-answering-dataset"
    download_and_extract(hotpotqa_url, hotpotqa_dir)
    
    print("All datasets prepared.")
