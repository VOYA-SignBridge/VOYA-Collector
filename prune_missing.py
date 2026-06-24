import pandas as pd
import os

df = pd.read_csv('dataset/samples/samples.csv')
initial_len = len(df)

# Check existence of each file path
df_cleaned = df[df['file_path'].apply(lambda p: os.path.exists(str(p)))]

final_len = len(df_cleaned)
missing_count = initial_len - final_len

if missing_count > 0:
    df_cleaned.to_csv('dataset/samples/samples.csv', index=False)
    df_cleaned.to_csv('dataset/samples.csv', index=False)
    print(f"Successfully removed {missing_count} missing rows. Remaining valid files: {final_len}")
else:
    print("No missing files found. Nothing was removed.")
