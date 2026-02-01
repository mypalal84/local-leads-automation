import pandas as pd
import requests

# ==================================================
# Generate a CLEAN towns_1000.csv with real U.S. data
# ==================================================

def generate_towns_csv(output_path="../data/towns_1000.csv", num_rows=1000):
    """
    Downloads and filters a list of real U.S. cities and states,
    then saves the top `num_rows` into towns_1000.csv.
    """
    print("🌎 Fetching U.S. city data from authoritative source...")
    url = "https://simplemaps.com/static/data/us-cities/uscities.csv"

    resp = requests.get(url)
    resp.raise_for_status()

    # Load to DataFrame
    from io import StringIO
    df = pd.read_csv(StringIO(resp.text))

    # Select relevant columns
    towns = df.loc[:, ["city", "state_id", "population"]]
    towns = towns.sort_values("population", ascending=False).head(num_rows)

    # Rename columns to match your existing format
    towns = towns.rename(columns={"city": "Town", "state_id": "State", "population": "Population"})

    towns.to_csv(output_path, index=False)
    print(f"✅ Saved {len(towns)} valid towns to {output_path}")

if __name__ == "__main__":
    generate_towns_csv()