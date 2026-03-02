import pandas as pd
import json
import re

filenames= [
    './data/outputs/gemini-2.5/output_batch_0_50000.jsonl',
    './data/outputs/gemini-2.5/output_batch_50000_100000.jsonl',
    './data/outputs/gemini-2.5/output_batch_150000_200000.jsonl',
    './data/outputs/gemini-2.5/output_batch_100000_150000.jsonl',
    './data/outputs/gemini-2.5/output_batch_200000_250000.jsonl',
    './data/outputs/gemini-2.5/output_batch_250000_300000.jsonl',
    './data/outputs/gemini-2.5/output_batch_300000_350000.jsonl',
    './data/outputs/gemini-2.5/output_batch_400000_450000.jsonl',
    './data/outputs/gemini-2.5/output_batch_450000_500000.jsonl',
]


def get_rows(filename):
    raw_jsons = []
    with open(filename) as f:
        for line in f:
            raw_jsons.append(json.loads(line))

    return raw_jsons


raw_jsons = []
for filename in filenames:
    raw_jsons += get_rows(filename)

print("Empty contents:")
empty = [row['key'] for row in raw_jsons if row['response']['candidates'][0]['content']['parts'][0]['text'] == ""]
print(empty)

no_response = [row['key'] for row in raw_jsons if not row.get("response")]
# print(len(no_response))
# print(raw_jsons)
raw_jsons = [row for row in raw_jsons if len(row['response']['candidates'][0]['content']['parts'][0]['text']) > 0]

for row in raw_jsons:
    try:
        row['response']['candidates'][0]['content']['parts'][0]['text'] = json.loads(row['response']['candidates'][0]['content']['parts'][0]['text'])
    except Exception:
        print(row['key'])

def extract_first_integer(text):
    # Pattern explanation:
    # r'[-+]?\d+'
    # [-+]? : an optional sign (+ or -)
    # \d+   : one or more digits
    match = re.search(r'[-+]?\d+', text)
    if match:
        return int(match.group(0))
    else:
        return None

data = [
    {
        "application_number": row['key'],
        "category": row['response']['candidates'][0]['content']['parts'][0]['text']["category"],
        "energy": extract_first_integer(row['response']['candidates'][0]['content']['parts'][0]['text']["energy"]),
        "compute": extract_first_integer(row['response']['candidates'][0]['content']['parts'][0]['text']["compute"]),
        "memory": extract_first_integer(row['response']['candidates'][0]['content']['parts'][0]['text']["memory"]),
        "algorithm": extract_first_integer(row['response']['candidates'][0]['content']['parts'][0]['text']["algorithm"]),
        "input_tokens": row['response']['usageMetadata']['promptTokenCount'],
        "output_tokens": row['response']['usageMetadata']["thoughtsTokenCount"] + row['response']['usageMetadata']["candidatesTokenCount"],
        "thinking_tokens":row['response']['usageMetadata']["thoughtsTokenCount"]
    }
    for row in raw_jsons
]


df = pd.DataFrame(data)
print(df)
print(f"Input Tokens: {df['input_tokens'].sum()}")

print(f"Output Tokens: {df['output_tokens'].sum()}")

df.to_csv("./data/all_llm_outputs.csv")

df = df[~df['category'].isin(["Unrelated", "Insufficient Data"])]


print(df.groupby('category')['application_number'].count())


df.to_csv("./data/outputs/processed_03_03_2026.csv")


df['application_number'] = (
    df['application_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
    .astype(int)
)


extended_df = pd.read_csv('./data/patents_with_details/full_sample.csv')
extended_df = extended_df.astype({"filing_date": "datetime64[ns]"})
extended_df = extended_df.drop(columns=['Unnamed: 0'], errors='ignore')

extended_df['application_number'] = (
    extended_df['application_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
    .astype(int)
)

df = df.merge(extended_df, on="application_number", how="left")
df = df.sort_values('filing_date')

df.to_csv('./data/full_post_data.csv')
