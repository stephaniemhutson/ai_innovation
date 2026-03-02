import pandas as pd


# patents_df = pd.read_csv('./patents_02_05_2026_filtered.csv')
dfs = []
dfs = [pd.read_csv('./data/patents_with_details/group_1/patents_with_details.csv')]
for i in range(500):
    try:
        """Used for:
        ./data/inputs/batches_model2.5_0_50000.jsonl
        ./data/inputs/batches_model2.5_50000_100000.jsonl
        ./data/inputs/batches_model2.5_100000_150000.jsonl
        ./data/inputs/batches_model2.5_150000_200000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_1/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        """Used for:
        ./data/inputs/batches_model2.5_0_50000.jsonl
        ./data/inputs/batches_model2.5_50000_100000.jsonl
        ./data/inputs/batches_model2.5_100000_150000.jsonl
        ./data/inputs/batches_model2.5_150000_200000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_2/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        """Used for:
        ./data/inputs/batches_model2.5_0_50000.jsonl
        ./data/inputs/batches_model2.5_50000_100000.jsonl
        ./data/inputs/batches_model2.5_100000_150000.jsonl
        ./data/inputs/batches_model2.5_150000_200000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_3/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        """Used for:
        ./data/inputs/batches_model2.5_200000_250000.jsonl
        ./data/inputs/batches_model2.5_250000_300000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_4/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        """Used for:
        ./data/inputs/batches_model2.5_300000_350000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_5/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        """Used for:
        ./data/inputs/batches_model2.5_400000_450000.jsonl
        ./data/inputs/batches_model2.5_450000_500000.jsonl
        """
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_6/patents_with_details__{i}.csv'))
    except Exception:
        pass

df = pd.concat(dfs, ignore_index=True)
df = df.drop_duplicates(subset="application_number", keep="first", ignore_index=True)
df.to_csv('./data/patents_with_details/full_sample.csv')


# Drop rows where the total information we have is very limited.
df['abstract'] = df['abstract'].fillna("")
df['summary'] = df['summary'].fillna("")
df['background'] = df['background'].fillna("")
df['sum_len'] = df['abstract'].str.len() + df['summary'].str.len() + df['background'].str.len()
df = df[df["sum_len"] >= 400]

df = df[["application_number","patent_number","cpcs","filing_date","invention_title","grant_date","status_code","status_desc","cpcs_list","abstract","summary","background"]]

df.to_csv('./data/patent_data_03_01_2026.csv')


# # df_filtered = patents_df[~patents_df['application_number'].isin(df['application_number'])]

# # df_filtered.to_csv('./patents_left_to_capture.csv')

