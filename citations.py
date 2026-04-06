import pandas as pd
import requests

# citations = pd.read_csv('./data/patents_cited.csv')
citations = pd.read_csv('./data/citations_count.csv')
# applications = pd.read_csv('./data/applications_cited.csv')
patents = pd.read_csv('./data/full_post_data.csv')
crosswalk = pd.read_csv('./data/patent_application_citation_crosswalk.csv')



patents['patent_number'] = (
    patents['patent_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
)
patents['application_number'] = (
    patents['application_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
)

citations['patent_number'] = (
    citations['patent_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
)
crosswalk['application_number'] = (
    crosswalk['application_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
)

# applications['application_number'] = (
#     applications['application_number']
#     .astype(str)                    # Convert to string
#     .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
#     .replace('nan', None)           # Replace 'nan' strings with None
# )

crosswalk['citation_document_number'] = (
    crosswalk['citation_document_number']
    .astype(str)                    # Convert to string
    .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
    .replace('nan', None)           # Replace 'nan' strings with None
)

count_application_citation = crosswalk.groupby('application_number')['citation_document_number'].count().reset_index()
count_application_citation = count_application_citation.rename(columns={'citation_document_number': 'application_citations_count'})

# count_citations = citations.groupby('citation_patent_id')['patent_id'].count().reset_index()
citations = citations.rename(columns={'citations_count': 'citations'})

patents = patents.merge(citations, on='patent_number', how='left')
patents = patents.merge(count_application_citation, on='application_number', how='left')

patents['citations'] = patents['citations'].fillna(0)
patents['application_citations_count'] = patents['application_citations_count'].fillna(0)

patents['total_citations'] = patents['citations'] + patents['application_citations_count']

print(patents['citations'])
print(patents['total_citations'])
print(patents['application_citations_count'])

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
patents = patents[~patents['status_desc'].isin(abandoned_and_rejected)]

patents = patents.sort_values('filing_date')

grouped = patents.groupby('citations')['patent_number'].count()
grouped.sort_values()
print(grouped)

grouped = patents.groupby('application_citations_count')['patent_number'].count()
grouped.sort_values()
print(grouped)

patents['first_applicant'] = patents['first_applicant'].str.lower()
patents['first_applicant'] = patents['first_applicant'].str.replace(r'[^\w\s]', '', regex=True)
patents['first_applicant'] = patents['first_applicant'].str.replace(r'\s+', ' ', regex=True).str.strip()

# patents = pd.read_csv('./data/full_patents_with_citations.csv').reset_index(drop=True)
# new_patents = pd.read_csv('./data/full_post_data.csv').reset_index(drop=True)

# patents = patents.drop(columns=['Unnamed: 0.1'])
# missing_columns = [col for col in patents.columns if col not in new_patents]

# new_patents['citations'] = 0
# new_patents['application_citations_count'] = 0
# new_patents['total_citations'] = 0

# patents['application_number'] = (
#     patents['application_number']
#     .astype(str)                    # Convert to string
#     .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
#     .replace('nan', None)           # Replace 'nan' strings with None
# )
# new_patents['application_number'] = (
#     new_patents['application_number']
#     .astype(str)                    # Convert to string
#     .str.replace(r'\.0$', '', regex=True)  # Remove .0 at the end
#     .replace('nan', None)           # Replace 'nan' strings with None
# )

# print(new_patents[['application_number', 'patent_number', 'filing_date']])
# new_patents = new_patents[~new_patents['application_number'].isin(patents['application_number'])]

# print(new_patents[['application_number', 'patent_number', 'filing_date']])
# temp = new_patents[new_patents['filing_date'] >= '2025-06-01']
# print(temp.groupby('filing_date')['application_number'].count()[:50])

# patents = pd.concat([patents, new_patents])

patents.to_csv('./data/full_patents_with_citations__temp.csv')
