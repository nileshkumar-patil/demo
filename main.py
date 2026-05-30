import pandas as pd
import requests
from io import StringIO

url = "https://jsonplaceholder.typicode.com/posts"
response = requests.get(url)
response.raise_for_status()

data = response.json()
df = pd.DataFrame(data)

csv_path = "posts.csv"
df.to_csv(csv_path, index=False)

print(f"Saved {csv_path}")