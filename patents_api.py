from configparser import ConfigParser
import requests
import pandas as pd
import json

config = ConfigParser()
config.read('config.ini')

url = config['ODP']['URL']
api_key = config['ODP']['KEY']
api_base = config['ODP']['API_BASE']


uspto_url = config['USPTO']['URL']
uspto_api_key = config['USPTO']['KEY']
us_pto_api_base = config['USPTO']['API_BASE']


r = requests.post(
  'https://api.uspto.gov/api/v1/patent/applications/search',
  headers={api_base: api_key, 'content-type': 'application/json'},
  json={
    "q": "applicationMetaData.applicationTypeLabelName:Utility",
    "filters": [
      {
        "name": "applicationMetaData.cpcClassificationBag",
        "value": [" G06F1/0307"]
      }
    ],
    "rangeFilters": [
      {
        "field": "applicationMetaData.grantDate",
        "valueFrom": "2010-08-04",
        "valueTo": "2022-08-04"
      }
    ],
    "sort": [
      {
        "field": "applicationMetaData.filingDate",
        "order": "desc"
      }
    ],
    "fields": [
      "applicationMetaData.patentNumber",
      "applicationMetaData.cpcClassificationBag",
      "applicationMetaData.filingDate"
    ],
    "pagination": {
      "offset": 0,
      "limit": 25
    },
    "facets": [
      "applicationMetaData.applicationTypeLabelName",
      "applicationMetaData.applicationStatusCode"
    ]
  }
)

data = r.json()['patentFileWrapperDataBag']
patent_numbers = [row['applicationMetaData']['patentNumber'] for row in data]
print(patent_numbers)


r = requests.get(
  url=config['USPTO']['URL'],
  headers={config['USPTO']['API_BASE']: config['USPTO']['KEY']},
  params={
    'q': json.dumps({'patent_id': patent_numbers}),
    "f": json.dumps([
      "patent_id",
      "patent_title",
      "patent_date",
      "patent_abstract",
    ])
  }
)

print(r.json())
