import pandas as pd
# import matplotlib.pyplot as plt
import re
import numpy as np
# import statsmodels.formula.api as smf
import datetime as dt

import statsmodels.api as sm
# import statsmodels.formula.api as smf
# import patsy
import ast

def get_vis_df():
    df = pd.read_csv('./data/full_patents_with_citations.csv')
    df = df.drop_duplicates('application_number')
    df = df.set_index('application_number')
    # Drop rows with invalid data
    df = df.dropna(subset=['energy', 'compute', 'filing_date'])

    df = df.astype({"filing_date": "datetime64[ns]", "total_citations": "int64", 'energy': 'int64', 'compute': 'int64'})
    df_clean = df[df['memory']<=10]


    # Convert to month period
    df_clean['filing_month'] = df_clean['filing_date'].dt.to_period('M').dt.to_timestamp()
    df_clean['filing_week'] = df_clean['filing_date'].dt.to_period('W').dt.to_timestamp()

    # Create binary flags for >= 7
    df_clean['energy_high'] = (df_clean['energy'] >= 8).astype(int)
    df_clean['compute_high'] = (df_clean['compute'] >= 8).astype(int)

    # Group by month and aggregate
    weekly_stats = df_clean.groupby('filing_week').agg({
        'energy_high': 'sum',
        'compute_high': 'sum',
        'energy': 'sum',
        'compute': 'sum'
    }).reset_index()


    # Rename for clarity
    weekly_stats.columns = ['filing_date', 'energy_count', 'compute_count', 'energy_sum', 'compute_sum']

    weekly_stats['energy_to_compute_high'] = weekly_stats['energy_count'] / (weekly_stats['compute_count'] + weekly_stats['energy_count'])
    return df_clean, weekly_stats


def get_merged_df():
    df_clean, weekly_stats = get_vis_df()
    # df_cats = df_clean.reset_index().groupby(['category'])['application_number'].count().reset_index()


    # 1. Load Data
    fred_df = pd.read_csv('./data/fredgraph.csv')
    patents_df = pd.read_csv('./data/full_patents_with_citations.csv')

    # 2. Process FRED
    # Convert to numeric, handle errors
    fred_df['semi_conductor_chips'] = pd.to_numeric(fred_df['semi_conductor_chips'], errors='coerce')
    fred_df['gas_turbines'] = pd.to_numeric(fred_df['gas_turbines'], errors='coerce')
    fred_df['observation_date'] = pd.to_datetime(fred_df['observation_date'])
    fred_df = fred_df.dropna()

    # Calculate Ratio
    fred_df['chip_gas_ratio'] = fred_df['semi_conductor_chips'] / fred_df['gas_turbines']
    fred_df['log_gas_turbine_price'] = np.log(fred_df['gas_turbines'])
    fred_df['log_chip_price'] = np.log(fred_df['semi_conductor_chips'])
    fred_df['log_chip_gas_ratio'] = np.log(fred_df['chip_gas_ratio'])
    fred_df['Month'] = fred_df['observation_date'].dt.to_period('M')


    # claude_pricing_indexes = pd.read_csv('./data/comprehensive_price_indices.csv')
    # claude_pricing_indexes['date'] = pd.to_datetime(claude_pricing_indexes['date'])
    # claude_pricing_indexes['Month'] = claude_pricing_indexes['date'].dt.to_period('M')

    # 3. Process Patents
    patents_df['filing_date'] = pd.to_datetime(patents_df['filing_date'], errors='coerce')
    patents_df = patents_df.dropna(subset=['filing_date', 'energy', 'compute', 'category'])
    patents_df['Month'] = patents_df['filing_date'].dt.to_period('M')
    patents_df['filing_week'] = patents_df['filing_date'].dt.to_period('W')


    patents_df['cpcs_actual_list'] = patents_df['cpcs_list'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
    patents_df['first_cpc'] = patents_df['cpcs_actual_list'].str[0]
    patents_df['cpc_subclass'] = patents_df['first_cpc'].str[:4]
    patents_df['cpc_class'] = patents_df['first_cpc'].str[:3]
    patents_df['cpc_section'] = patents_df['first_cpc'].str[:1]

    # 4. Define Target
    patents_clean = patents_df.copy()
    patents_clean['is_energy_biased'] = (patents_clean['energy'] - patents_clean['compute'] >0).astype(int)
    patents_clean['is_compute_biased'] = (patents_clean['energy'] - patents_clean['compute']< 0).astype(int)

    # 5. Merge

    # Create lagged version of fred_df
    fred_lagged = fred_df[['Month', 'chip_gas_ratio', 'log_chip_price', 'log_gas_turbine_price']].copy()
    fred_lagged['Month'] = fred_lagged['Month'] + 3  # Shift forward by 3 months
    fred_lagged = fred_lagged.rename(
        columns={
            'chip_gas_ratio': 'chip_gas_ratio_lag3',
            'log_chip_price': 'log_chip_price_lag3',
            'log_gas_turbine_price': 'log_gas_turbine_price_lag3',
        })

    # Merge with both current and lagged
    merged_df = patents_clean.merge(fred_df, on='Month', how='inner')
    merged_df = merged_df.merge(fred_lagged[['Month', 'chip_gas_ratio_lag3', 'log_gas_turbine_price_lag3', 'log_chip_price_lag3']], on='Month', how='left')
    merged_df['log_chip_gas_ratio_lag3'] = np.log(merged_df['chip_gas_ratio_lag3'])

    fred_ng = pd.read_csv('./data/fred_natural_gas.csv')
    fred_ng  = fred_ng.astype({"observation_date": "datetime64[ns]"})
    fred_ng['Month'] = fred_ng['observation_date'].dt.to_period('M')
    fred_ng['log_ng_price'] = np.log(fred_ng['ng_price'])
    merged_df = merged_df.merge(fred_ng, on='Month', how='left')
    # merged_df = merged_df.merge(claude_pricing_indexes, on='Month', how='left')

    fred_ng_lagged = fred_ng[['Month', 'ng_price', 'log_ng_price']].copy()
    fred_ng_lagged['Month'] = fred_ng_lagged['Month'] + 3  # Shift forward by 3 months
    fred_ng_lagged = fred_ng_lagged.rename(columns={'ng_price': 'ng_price_lag3', 'log_ng_price': 'log_ng_price_lag3'})
    merged_df = merged_df.merge(fred_ng_lagged, on='Month', how='left')
    merged_df['energy_high'] = (merged_df['energy'] >= 8).astype(int)
    merged_df['compute_high'] = (merged_df['compute'] >= 8).astype(int)

    merged_df['filing_month'] = merged_df['filing_date'].dt.to_period('M').dt.to_timestamp()
    merged_df['filing_year'] = merged_df['filing_date'].dt.to_period('Y').dt.to_timestamp()
    merged_df['filing_week'] = merged_df['filing_date'].dt.to_period('W').dt.to_timestamp()


    prices = pd.read_csv('./data/comprehensive_price_indices.csv')
    prices['date'] = pd.to_datetime(prices['date'])
    prices['Month'] = prices['date'].dt.to_period('M')
    prices['log_gpu_energy_ratio'] = np.log(prices['gpu_energy_ratio'])
    # Create multiple lags
    for lag in [0, 3, 6, 9, 12, 18]:
        prices_lagged = prices.copy()
        prices_lagged['Month'] = prices_lagged['Month'] + lag

        prices_lagged = prices_lagged[['Month', 'log_gpu_price_index', 'log_energy_cost_index',
                                       'log_gpu_energy_ratio', 'log_ng_price_index', 'log_turbine_price_index',
                                       'gpu_energy_ratio', 'log_gpu_turbine_ratio']]
        columns = [
            'Month', f'log_gpu_price_index_{lag}', f'log_energy_cost_index_{lag}',
            f'log_gpu_energy_ratio_{lag}', f'log_ng_price_index_{lag}', f'log_turbine_price_index_{lag}',
            f'gpu_energy_ratio_{lag}', f'log_gpu_turbine_ratio_{lag}'
        ]
        prices_lagged.columns = columns

        merged_df = merged_df.merge(
            prices_lagged,
            on='Month',
            how='left'
        )
    merged_df = merged_df.merge(prices[['Month','energy_cost_index', 'turbine_price_index', 'gpu_price_index', 'gpu_energy_ratio']], on="Month", how="left")


    abandoned_and_rejected = [
        'Final Rejection Counted, Not Yet Mailed',
        'Final Rejection Mailed',
        'Expressly Abandoned  --  During Examination',
        'Abandoned  --  Failure to Respond to an Office Action',
        'Notice of Appeal Filed',
        'Proceedings Terminated',
        'Abandonment for Failure to Correct Drawings/Oath/NonPub Request',
        'Expressly Abandoned  --  During Publication Process',
        "Abandoned  --  After Examiner's Answer or Board of Appeals Decision",
        'Patent Expired Due to NonPayment of Maintenance Fees Under 37 CFR 1.362',
    ]

    merged_df = merged_df[
        ~merged_df['status_desc'].isin(abandoned_and_rejected)
    ]
    return merged_df

def by_top_X_companies(df, x):

    companies = pd.read_csv('./data/companies_manually_cleaned.csv')
    companies['company_name'] = companies['company_name'].replace('', np.nan)
    companies['company_name'] = companies['company_name'].fillna(companies['first_applicant'])
    companies['num_company_patents'] = companies['num_company_patents'].astype(int)
    companies['num_company_citations'] = companies['num_company_citations'].astype(int)

    companies['num_company_patents'] = companies.groupby('company_name')['num_company_patents'].transform('sum')
    companies['num_company_citations'] = companies.groupby('company_name')['num_company_citations'].transform('sum')
    grouped = companies.groupby('company_name')['num_company_patents'].max().reset_index()

    df['first_applicant'] = df['first_applicant'].str.lower()
    df['first_applicant'] = df['first_applicant'].str.replace(r'[^\w\s]', '', regex=True)
    df['first_applicant'] = df['first_applicant'].str.replace(r'\s+', ' ', regex=True).str.strip()

    df = df.merge(companies, on='first_applicant', how='left')

    n_largest = grouped.nlargest(x, 'num_company_patents')['company_name'].to_list()
    df = df[df['company_name'].isin(n_largest)]

    return df


def by_companies_with_X_patents(df, x):
    companies = pd.read_csv('./data/companies_manually_cleaned.csv')
    companies['company_name'] = companies['company_name'].replace('', np.nan)
    companies['company_name'] = companies['company_name'].fillna(companies['first_applicant'])
    companies['num_company_patents'] = companies['num_company_patents'].astype(int)
    companies['num_company_citations'] = companies['num_company_citations'].astype(int)

    companies['num_company_patents'] = companies.groupby('company_name')['num_company_patents'].transform('sum')
    companies['num_company_citations'] = companies.groupby('company_name')['num_company_citations'].transform('sum')
    grouped = companies.groupby('company_name')['num_company_patents'].max().reset_index()

    df['first_applicant'] = df['first_applicant'].str.lower()
    df['first_applicant'] = df['first_applicant'].str.replace(r'[^\w\s]', '', regex=True)
    df['first_applicant'] = df['first_applicant'].str.replace(r'\s+', ' ', regex=True).str.strip()

    df = df.merge(companies, on='first_applicant', how='left')
    companies_w_x = grouped[grouped['num_company_patents'] >= x]['company_name'].to_list()
    df = df[df['company_name'].isin(companies_w_x)]

    return df
