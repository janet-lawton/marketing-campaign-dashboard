import os
import pandas as pd
import requests
import tempfile
import zipfile

def clean_currency(value):
    """Convert currency string like '$16,174.00' to float 16174.00"""
    if isinstance(value, str):
        return float(value.replace('$', '').replace(',', ''))
    return value

def download_dataset_from_kaggle():
    """Download dataset directly from Kaggle API using requests"""
    print("Downloading dataset from Kaggle...")

    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")

    if not username or not key:
        raise Exception("KAGGLE_USERNAME and KAGGLE_KEY environment variables are required")

    url = "https://www.kaggle.com/api/v1/datasets/download/manishabhatt22/marketing-campaign-performance-dataset"

    with tempfile.TemporaryDirectory() as tmpdir:
        response = requests.get(url, auth=(username, key), stream=True)

        if response.status_code != 200:
            raise Exception(f"Kaggle API request failed with status {response.status_code}: {response.text}")

        zip_path = os.path.join(tmpdir, "dataset.zip")
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        csv_files = [f for f in os.listdir(tmpdir) if f.endswith('.csv')]
        if not csv_files:
            raise Exception("No CSV file found in downloaded dataset")

        df = pd.read_csv(os.path.join(tmpdir, csv_files[0]))
        df['Acquisition_Cost'] = df['Acquisition_Cost'].apply(clean_currency)

    return df

def load_data() -> pd.DataFrame:
    """Load data from Kaggle API"""
    try:
        df = download_dataset_from_kaggle()
        print(f"Successfully loaded {len(df)} records from Kaggle API")
        print(f"Acquisition_Cost type: {df['Acquisition_Cost'].dtype}")
        return df
    except Exception as e:
        print(f"Error downloading from Kaggle: {e}")
        raise

def get_filter_options(df: pd.DataFrame) -> dict:
    """Return unique values for categorical columns only (exclude numeric)"""
    categorical_cols = df.select_dtypes(include=['object']).columns
    options = {}
    for col in categorical_cols:
        options[col] = sorted(df[col].dropna().unique().tolist())
    return options
