from configparser import ConfigParser
import requests
import pandas as pd
import json
from xml.etree import ElementTree

config = ConfigParser()
config.read('config.ini')

url = config['ODP']['URL']
api_key = config['ODP']['KEY']
api_base = config['ODP']['API_BASE']


uspto_url = config['USPTO']['URL']
uspto_api_key = config['USPTO']['KEY']
us_pto_api_base = config['USPTO']['API_BASE']


CPC_CATEGORIES = [
  # From ChatGPT
  "H05K7/*",
  "F28D*",
  "F28F*",
  "F28C*",
  "F24F5/*",
  "F24F11/*",
  "F24F3/*",
  "F25B*",
  "F25D*",
  "G06F1/*",
  "G06F1/32",
  "G06F1/26",
  "Y02B30/*",
  "Y02B7/*",
  "Y02B12/*",
  "C09K*",
  "C23C*",
  "H01L23/*",
  "H01L27/*",
]



r = requests.post(
  'https://api.uspto.gov/api/v1/patent/applications/search',
  headers={api_base: api_key, 'content-type': 'application/json'},
  json={
    # "q": "applicationMetaData.applicationTypeLabelName:Utility",
    "filters": [
      {
        "name": "applicationMetaData.cpcClassificationBag",
        # Using values which end in 00 seems to broadly
        "value": CPC_CATEGORIES
      }
    ],
    "rangeFilters": [
      {
        "field": "applicationMetaData.grantDate",
        "valueFrom": "2018-08-04",
        "valueTo": "2026-01-01"
      }
    ],
    "sort": [
      {
        "field": "applicationMetaData.filingDate",
        "order": "desc"
      }
    ],
    "fields": [
      # only patents that have been granted have a patent number. If you are using the filing
      # date you might select patents which don't have a patent number. Perhaps this
      # means we need to get an application number so that when we pull from patents view
      # we are able to find them.
      'applicationNumberText',
      "applicationMetaData.patentNumber",
      "applicationMetaData.cpcClassificationBag",
      "applicationMetaData.filingDate",
      # "applicationMetaData.applicationStatusDescriptionText",
    ],
    "pagination": {
      "offset": 0,
      "limit": 2
    },
    "facets": [
      "applicationMetaData.applicationTypeLabelName",
      "applicationMetaData.applicationStatusCode"
    ]
  }
)
print(r)
data = r.json()['patentFileWrapperDataBag']

# data = r.json()['applicationTypeLabelName']
print(data[0])
patent_numbers = [row['applicationMetaData'].get('patentNumber') for row in data]
application_numbers = [row['applicationNumberText'] for row in data]

print(application_numbers)

# # Possible documents to grab: ['ABST', 'SPEC', ]

r = requests.get(
  f'https://api.uspto.gov/api/v1/patent/applications/{application_numbers[0]}/documents',
  headers={api_base: api_key},
  params={
    "documentCodes": ["SPEC", "ABST"]
  }
)

docs = r.json()['documentBag'][0]['downloadOptionBag']
xml_url = None
for doc in docs:
  if doc['mimeTypeIdentifier'] == "XML":
    xml_url = doc['downloadUrl']
    break

if xml_url:
  r = requests.get(
    xml_url,
    headers={api_base: api_key}
    )
  print(r.headers['Content-Type'])

  content = r.content.decode('utf-8')

  elements = content.split('<?xml version="1.0" encoding="utf-8"?>')[1:]
  elements = ['<?xml version="1.0" encoding="utf-8"?>' + e.split('</uspat:SpecificationDocument>')[0] + '</uspat:SpecificationDocument>' for e in elements]

  for element in elements:
    tree = ElementTree.fromstring(element)
    # tree = xmltodict.parse(r.content)
    print(tree)
else:
  print("Did not find xml")




# print(patent_numbers)


# r = requests.get(
#   url=config['USPTO']['URL'],
#   headers={config['USPTO']['API_BASE']: config['USPTO']['KEY']},
#   params={
#     'q': patent_numbers,
#     "f": json.dumps([
#       "patent_id",
#       "patent_title",
#       "patent_date",
#       "patent_abstract",
#       # "patent_summary"
#     ]),
#     "o": json.dumps({"size": 5})
#   }
# )
# print(r)
# print(r.json())
