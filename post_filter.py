import pandas as pd

import CONST

df = pd.read_csv('./patents.csv')

df['cpcs'] = df['cpcs'].str.replace(' ', '', regex=False)

df['cpcs_list'] = df['cpcs'].str.split(",")
df['invention_title'] = df['invention_title'].str.lower()

exclusion_CPCs = [
    "A",        # Human necessityies
    "G16H",     # Healthcare informatics
    "B60W",     # Control system for raod vehicles
    "G05D",     # autonomous navigation
    "B25J",     # robots
    "G06F3",    # human-computer interaction
    "H04N21",   # selective content distribution
    "G10L",     # speach analysis
    "H04N5",    # cameras
    "H04N23",   # cameras
    "G06T",     # image data processing
    "G06Q"      # marketing AI
]

for cpc in exclusion_CPCs:
    # Exclude patents that have any CPC starting with exclusion cpc
    df = df[~df['cpcs_list'].apply(lambda x: any(code.strip().startswith(cpc) for code in x))]


# Define your medical terms
medical_terms = [
    "medical",
    "parkinson's",
    "parkinsons",
    "disease",
    "therapy",
    "clinical",
    "alzheimer's",
    "alzheimers",
    "biotech",
]

vehicular_terms = [
    "autonomous veh",
]




# Filter OUT patents that contain any of these terms (case-insensitive)
df_filtered = df[
    ~df['invention_title'].str.contains('|'.join(medical_terms), case=False, na=False)
]
df_filtered = df_filtered[
    ~df_filtered['invention_title'].str.contains('|'.join(vehicular_terms), case=False, na=False)
]


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

df_filtered = df_filtered[
    ~df_filtered['status_desc'].isin(abandoned_and_rejected)
]

df_filtered.to_csv('./filtered_patents.csv')
