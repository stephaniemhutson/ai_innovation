import pandas as pd
import re
import numpy as np
import datetime as dt

import statsmodels.api as sm
import ast
import data_subset_creation as dsc

def get_vis_df(x_firms = None):
    df = pd.read_csv('./data/full_patents_with_citations__temp.csv')
    if x_firms:
        df = by_top_X_companies(df, x_firms)
    df = df.drop_duplicates('application_number')
    df = df[(~df['patent_number'].duplicated()) | df['patent_number'].isna()]
    # df = df.set_index('application_number')
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
    weekly_stats = df_clean.groupby('filing_month').agg({
        'energy_high': 'sum',
        'compute_high': 'sum',
        'energy': 'sum',
        'compute': 'sum',
        'application_number': 'count'
    }).reset_index()


    # Rename for clarity
    weekly_stats.columns = ['filing_date', 'energy_count', 'compute_count', 'energy_sum', 'compute_sum', 'count_patents']

    weekly_stats['energy_to_compute_high'] = weekly_stats['energy_count'] / (weekly_stats['compute_count'] + weekly_stats['energy_count'])
    return df_clean, weekly_stats


def get_merged_df():
    patents_df, weekly_stats = get_vis_df()
    # df_cats = df_clean.reset_index().groupby(['category'])['application_number'].count().reset_index()


    # 1. Load Data
    fred_df = pd.read_csv('./data/fredgraph.csv')
    # patents_df = pd.read_csv('./data/full_patents_with_citations__temp.csv')

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
    prices['log_gpu_electricity_ratio'] = np.log(prices['gpu_electricity_ratio'])
    # Create multiple lags
    for lag in [0, 3, 6, 9, 12, 18]:
        prices_lagged = prices.copy()
        prices_lagged['Month'] = prices_lagged['Month'] + lag

        prices_lagged = prices_lagged[['Month', 'log_gpu_price_index', 'log_energy_cost_index',
                                       'log_gpu_electricity_ratio', 'log_electricity_price_index', 'log_turbine_price_index',
                                       'gpu_electricity_ratio', 'log_gpu_turbine_ratio', 'log_gpu_price_index_combined']]
        columns = [
            'Month', f'log_gpu_price_index_{lag}', f'log_energy_cost_index_{lag}',
            f'log_gpu_electricity_ratio_{lag}', f'log_electricity_price_index_{lag}', f'log_turbine_price_index_{lag}',
            f'gpu_electricity_ratio_{lag}', f'log_gpu_turbine_ratio_{lag}', f'log_gpu_price_index_combined_{lag}'
        ]
        prices_lagged.columns = columns

        merged_df = merged_df.merge(
            prices_lagged,
            on='Month',
            how='left'
        )
    merged_df = merged_df.merge(prices[['Month','energy_cost_index', 'turbine_price_index', 'gpu_price_index', 'gpu_electricity_ratio', 'electricity_price_index']], on="Month", how="left")

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

    merged_df['month_of_year'] = merged_df['filing_month'].dt.month
    merged_df['year'] = merged_df['filing_month'].dt.year

    return merged_df

def by_top_X_companies(df, x, max_date=None):

    companies = pd.read_csv('./data/companies_manually_cleaned.csv')

    if max_date:
        subset_companies = dsc.companies(max_date)
        companies = companies.drop(columns=['num_company_patents', 'num_company_citations'])
        companies = subset_companies.merge(companies, on='first_applicant', how='left')
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


def by_companies_with_X_patents(df, x, categories=None):
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

    if categories is not None:
        df = df[df['category'].isin(categories)]
    companies_w_x = grouped[grouped['num_company_patents'] >= x]['company_name'].to_list()
    df = df[df['company_name'].isin(companies_w_x)]
    return df

def innovation_rate(num_firms, categories=None, weights=None, max_date=None):
    df = get_merged_df()
    if categories is not None:
        df = df[df['category'].isin(categories)]
    df = by_top_X_companies(df, num_firms, max_date)

    df['citation_percentile'] = df.groupby(['filing_year'])['total_citations'].rank(pct=True)

    indices = [
        'semi_conductor_chips', 'gas_turbines', 'chip_gas_ratio', 'log_gas_turbine_price',
        'log_chip_price', 'log_chip_gas_ratio', 'chip_gas_ratio_lag3',
        'log_gas_turbine_price_lag3', 'log_chip_price_lag3', 'log_chip_gas_ratio_lag3',
        'ng_price', 'log_ng_price', 'ng_price_lag3', 'log_ng_price_lag3', 'filing_year',
        'log_gpu_price_index_0', 'log_energy_cost_index_0', 'log_gpu_electricity_ratio_0',
        'log_electricity_price_index_0', 'log_turbine_price_index_0', 'gpu_electricity_ratio_0',
        'log_gpu_turbine_ratio_0', 'log_gpu_price_index_3', 'log_energy_cost_index_3',
        'log_gpu_electricity_ratio_3', 'log_electricity_price_index_3', 'log_turbine_price_index_3',
        'gpu_electricity_ratio_3', 'log_gpu_turbine_ratio_3', 'log_gpu_price_index_6',
        'log_energy_cost_index_6', 'log_gpu_electricity_ratio_6', 'log_electricity_price_index_6',
        'log_turbine_price_index_6', 'gpu_electricity_ratio_6', 'log_gpu_turbine_ratio_6',
        'log_gpu_price_index_9', 'log_energy_cost_index_9', 'log_gpu_electricity_ratio_9',
        'log_electricity_price_index_9', 'log_turbine_price_index_9', 'gpu_electricity_ratio_9',
        'log_gpu_turbine_ratio_9', 'log_gpu_price_index_12', 'log_energy_cost_index_12',
        'log_gpu_electricity_ratio_12', 'log_electricity_price_index_12', 'log_turbine_price_index_12',
        'gpu_electricity_ratio_12', 'log_gpu_turbine_ratio_12', 'log_gpu_price_index_18',
        'log_energy_cost_index_18', 'log_gpu_electricity_ratio_18', 'log_electricity_price_index_18',
        'log_turbine_price_index_18', 'gpu_electricity_ratio_18', 'log_gpu_turbine_ratio_18',
        'energy_cost_index', 'turbine_price_index', 'gpu_price_index', 'gpu_electricity_ratio',
        'log_gpu_price_index_combined_0', 'log_gpu_price_index_combined_3',
        'log_gpu_price_index_combined_6', 'log_gpu_price_index_combined_12',
        'log_gpu_price_index_combined_18',
    ]
    transform_indexes = {
        index: 'median'
        for index in indices
    }

    index_by_month = df.groupby('filing_month').agg(transform_indexes).reset_index()

    df['is_compute_biased'] = (df['compute'] - df['energy'] > 0).astype(int)
    df['is_energy_biased'] = (df['energy'] - df['compute'] > 0).astype(int)

    transform ={
        'application_number': 'count',
        'energy': 'mean',
        'compute': 'mean',
        'energy_high': 'sum',
        'compute_high': 'sum',
        'total_citations': 'sum',
        'is_compute_biased': 'sum',
        'is_energy_biased': 'sum',
        'citation_percentile': 'mean'
    }

    conditional_on_energy = df[df['energy'] >=3]
    conditional_on_compute = df[df['compute'] >=3]

    energy_by_month = conditional_on_energy.groupby(['company_name', 'filing_month']).agg({'energy': 'mean', 'application_number': 'count'}).reset_index()
    energy_by_month = energy_by_month.rename(columns={'energy': 'energy_conditional_on_ge_2', 'application_number': 'count_energy_patents'})
    compute_by_month = conditional_on_compute.groupby(['company_name', 'filing_month']).agg({'compute': 'mean', 'application_number': 'count'}).reset_index()
    compute_by_month = compute_by_month.rename(columns={'compute': 'compute_conditional_on_ge_2', 'application_number': 'count_compute_patents'})

    rate_by_month = df.groupby(['company_name', 'filing_month']).agg(transform)
    rate_by_month = rate_by_month.reset_index()
    rate_by_month = rate_by_month.rename(columns={'application_number': 'count_patents'})

    rate_by_month = rate_by_month.merge(energy_by_month, on=['company_name', 'filing_month'], how='left')
    rate_by_month = rate_by_month.merge(compute_by_month, on=['company_name', 'filing_month'], how='left')

    rate_by_month['monthly_energy_addition'] = (rate_by_month['count_patents']*rate_by_month['energy']).fillna(0)
    rate_by_month['monthly_compute_addition'] = (rate_by_month['count_patents']*rate_by_month['compute']).fillna(0)


    rate_by_month['monthly_energy_addition_conditional'] = (rate_by_month['count_energy_patents']*rate_by_month['energy_conditional_on_ge_2']).fillna(0)
    rate_by_month['monthly_compute_addition_conditional'] = (rate_by_month['count_compute_patents']*rate_by_month['compute_conditional_on_ge_2']).fillna(0)

    rate_by_month['energy_high_proportional'] = (rate_by_month['energy_high']/rate_by_month['count_patents']).fillna(0)
    rate_by_month['compute_high_proportional'] = (rate_by_month['compute_high']/rate_by_month['count_patents']).fillna(0)

    rate_by_month['energy_high_proportional_conditional'] = (rate_by_month['energy_high']*rate_by_month['energy_conditional_on_ge_2']).fillna(0)
    rate_by_month['compute_high_proportional_conditional'] = (rate_by_month['compute_high']*rate_by_month['compute_conditional_on_ge_2']).fillna(0)

    rate_by_month = (
        rate_by_month.set_index(['company_name', 'filing_month'])
        .groupby(level='company_name')
        .apply(lambda x: x.droplevel(0).reindex(
            pd.date_range(x.index.get_level_values('filing_month').min(),
                          x.index.get_level_values('filing_month').max(),
                          freq='MS')  # MS = Month Start
        ))
        .rename_axis(['company_name', 'filing_month']).reset_index()
    )
    for col in ['count_patents', 'energy', 'compute', 'energy_high', 'compute_high']:
        rate_by_month[col] = rate_by_month[col].fillna(0)

    rate_by_month = rate_by_month.merge(index_by_month, on='filing_month')

    # add dependent variables:

    rate_by_month['log_count_patents'] = np.log(rate_by_month['count_patents'] + .1)
    rate_by_month['log_energy_high'] = np.log(rate_by_month['energy_high'] + .1)
    rate_by_month['log_compute_high'] = np.log(rate_by_month['compute_high'] + .1)

    rate_by_month['log_is_compute_biased'] = np.log(rate_by_month['is_compute_biased'] + 0.1)
    rate_by_month['log_is_energy_biased'] = np.log(rate_by_month['is_energy_biased'] + 0.1)

    rate_by_month['log_monthly_energy_addition'] = np.log(rate_by_month['monthly_energy_addition'] + .1)
    rate_by_month['log_monthly_compute_addition'] = np.log(rate_by_month['monthly_compute_addition'] + .1)
    rate_by_month['log_monthly_energy_addition_conditional'] = np.log(rate_by_month['monthly_energy_addition_conditional'] + .1)
    rate_by_month['log_monthly_compute_addition_conditional'] = np.log(rate_by_month['monthly_compute_addition_conditional'] + .1)
    rate_by_month['log_energy_conditional'] = np.log(rate_by_month['energy_conditional_on_ge_2'] + .1)
    rate_by_month['log_compute_conditional'] = np.log(rate_by_month['compute_conditional_on_ge_2'] + .1)
    rate_by_month['total_citations__plus_1'] = rate_by_month['total_citations'] + 1

    rate_by_month['log_energy_high_proportional_conditional'] = np.log(rate_by_month['energy_high_proportional_conditional'] + 0.01)
    rate_by_month['log_compute_high_proportional_conditional'] = np.log(rate_by_month['compute_high_proportional_conditional'] + 0.01)

    rate_by_month['log_energy_high_proportional'] = np.log(rate_by_month['energy_high_proportional'] + 0.01)
    rate_by_month['log_compute_high_proportional'] = np.log(rate_by_month['compute_high_proportional'] + 0.01)

    deps = [
        'log_count_patents',
        'log_energy_high',
        'log_compute_high',
        'log_monthly_energy_addition',
        'log_monthly_compute_addition',

        'energy',
        'compute',
        'log_energy_high_proportional',
        'log_compute_high_proportional',
        'log_energy_high_proportional_conditional',
        'log_compute_high_proportional_conditional',
        'log_energy_conditional',
        'log_compute_conditional',
        'log_monthly_energy_addition_conditional',
        'log_monthly_compute_addition_conditional',

        'log_is_energy_biased',
        'log_is_compute_biased',
    ]

    lagged_cols = ['filing_month', 'company_name']
    lagged_cols += deps

    lagged = rate_by_month[lagged_cols].copy()
    lagged['filing_month'] = lagged['filing_month'] + pd.DateOffset(months=1)

    lagged = lagged.rename(
        columns = {
            dep: f'{dep}_l1'
            for dep in deps
        }
    )

    rate_by_month = rate_by_month.merge(lagged, on=['filing_month', 'company_name'], how='left')


    return rate_by_month
