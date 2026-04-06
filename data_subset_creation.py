import pandas as pd
import re

"""The point of this file is to aggregate information from the data and create
small data sets which capture specific types of information.
"""

def companies(max_date=None):
    """Returns a df of inventors with thier names ans number of patents and citations

    max_date (opt:str): "YYYY-MM-DD". selects companies based on the max date.
        This might be used if you want to elimiate endogenous effect of new companies
        innovating and skewing the results for within-company over the timeseries.
    """
    df = pd.read_csv('./data/full_patents_with_citations.csv')

    if max_date:
        df['filing_date'] = pd.to_datetime(df['filing_date'])
        df = df[df['filing_date'] <= max_date]

    df['first_applicant'] = df['first_applicant'].str.lower()
    df['first_applicant'] = df['first_applicant'].str.replace(r'[^\w\s]', '', regex=True)
    df['first_applicant'] = df['first_applicant'].str.replace(r'\s+', ' ', regex=True).str.strip()

    df['decile'] = pd.qcut(df['total_citations'], q=10, labels=False, duplicates='drop') + 1

    inventors = df.groupby('first_applicant')['application_number'].count().reset_index()
    citations = df.groupby('first_applicant')['citations'].sum().reset_index()

    inventors = inventors.merge(citations, on='first_applicant', how='left')

    inventors = inventors.rename(
        columns={
            'application_number': 'num_company_patents',
            'citations': 'num_company_citations'
        }
    )
    inventors = inventors.sort_values(by='num_company_patents')
    if max_date:
        inventors.to_csv(f'./data/companies__{max_date}.csv', index=False)
    else:
        inventors.to_csv('./data/companies.csv', index=False)
    return inventors


if __name__ == '__main__':
    inventors = companies('2020-01-01')
