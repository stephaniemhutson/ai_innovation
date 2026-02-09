import pandas as pd

# first_full_sample = pd.read_csv('./data/full_sample.csv')

# patents_df = pd.read_csv('./patents_02_05_2026_filtered.csv')

dfs = [pd.read_csv('./data/patents_with_details/group_1/patents_with_details.csv')]
for i in range(90):
    try:
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_1/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_2/patents_with_details__{i}.csv'))
    except Exception:
        pass

    try:
        dfs.append(pd.read_csv(f'./data/patents_with_details/group_3/patents_with_details__{i}.csv'))
    except Exception:
        pass

df = pd.concat(dfs, ignore_index=True)
df = df.drop_duplicates(subset="application_number", keep="first", ignore_index=True)
df.to_csv('./data/patents_with_details/full_sample.csv')

# df_filtered = pd.read_csv('./filtered_patents.csv')
# print(df_filtered)

# # df = pd.concat(dfs, ignore_index=True)

df = df[~(df['summary'].isnull() & df['background'].isnull() & df['abstract'].isnull())]
# df = df[df['filing_date'] >= '2018-01-01']


# Drop rows where the total information we have is very limited.
df['abstract'] = df['abstract'].fillna("")
df['summary'] = df['summary'].fillna("")
df['background'] = df['background'].fillna("")
df['sum_len'] = df['abstract'].str.len() + df['summary'].str.len() + df['background'].str.len()
df = df[df["sum_len"] >= 300]



df = df[["application_number","patent_number","cpcs","filing_date","invention_title","grant_date","status_code","status_desc","cpcs_list","abstract","summary","background"]]


df.to_csv('./data/patents_with_details/dropped_empty_details.csv')


# df_filtered = patents_df[~patents_df['application_number'].isin(df['application_number'])]

# # # print(df)
# print(df_filtered)

# df_filtered.to_csv('./patents_left_to_capture.csv')

