import pandas as pd

# List of Excel files to merge
file_names = [f'emails{i}.xlsx' for i in range(1, 11)]

# List to hold individual DataFrames
dfs = []

# Read each Excel file into a DataFrame
for file in file_names:
    df = pd.read_excel(file)  # Assumes the email column is the only column
    dfs.append(df)

# Concatenate all DataFrames into one
merged_df = pd.concat(dfs)

# Remove duplicate email addresses
unique_emails = merged_df.drop_duplicates(subset=['Email'])

# Save the result to a new Excel file
unique_emails.to_excel('merged_emails.xlsx', index=False)

print("All email files have been merged into 'merged_emails.xlsx' with unique email addresses.")
