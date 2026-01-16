from configparser import ConfigParser
import requests
import pandas as pd
import json
from xml.etree import ElementTree as ET
import re
import os
import traceback
import time

import CONST

config = ConfigParser()
config.read('config.ini')


class NotFoundError(Exception):
    pass



def get_patents(config, page=0, limit=100, cpcs=None):
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']
    url = config['ODP']['URL']

    # query = '("data center*" OR datacenter*) OR (A?I OR AI OR "artificial intelligence" OR "machine learning") OR (?PU AND comput*) OR abstract:(cooling)'

    cpcs = cpcs if cpcs else CONST.CPC_lui_2022

    r = requests.post(
        url = 'https://api.uspto.gov/api/v1/patent/applications/search',
        headers={api_base: api_key, 'content-type': 'application/json'},
        json={
            "filters": [
              {
                  "name": "applicationMetaData.cpcClassificationBag",
                  # Using values which end in 00 seems to broadly
                  "value": cpcs
              }
            ],
            "rangeFilters": [
                {
                    "field": "applicationMetaData.filingDate",
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
                "applicationMetaData.inventionTitle",
                "applicationMetaData.grantDate",
                "applicationMetaData.applicationStatusCode",
                "applicationMetaData.applicationStatusDescriptionText",
            ],
            "pagination": {
                "offset": page * limit,
                "limit": limit
            },
            "facets": [
                "applicationMetaData.applicationTypeLabelName",
                "applicationMetaData.applicationStatusCode"
            ]
        }
    )

    data = r.json()['patentFileWrapperDataBag']



    def raw_to_row(raw):

        meta_data = raw['applicationMetaData']

        raw.update(meta_data)
        parsing_dict = {
            "applicationNumberText": 'application_number',
            "patentNumber": 'patent_number',
            "cpcClassificationBag": "cpcs",
            "filingDate": 'filing_date',
            "inventionTitle": "invention_title",
            "grantDate": "grant_date",
            "applicationStatusCode": "status_code",
            "applicationStatusDescriptionText": "status_desc",
        }

        row = {}
        for k, v in parsing_dict.items():
            row[v] = raw.get(k, None)

        if row.get('cpcs'):
            row['cpcs'] = ",".join(row['cpcs'])
        return row

    rows = [raw_to_row(raw) for raw in data]



    df = pd.DataFrame(rows)

    csv_file = 'patents.csv'

    # First batch - write with headers
    if not os.path.exists(csv_file):
        df.to_csv(csv_file, index=False)
    else:
        # Subsequent batches - append without headers
        df.to_csv(csv_file, mode='a', header=False, index=False)

    return df


# # Possible documents to grab: ['ABST', 'SPEC', ]
def get_docs(application_number, config, doc_types):
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']

    r = requests.get(
        f'https://api.uspto.gov/api/v1/patent/applications/{application_number}/documents',
        headers={api_base: api_key},
        params={
            "documentCodes": doc_types
        }
    )
    try:
        docs_bag = r.json()['documentBag']
    except KeyError:
        if r.json().get('message'):
            if r.json()['message'] == "Too Many Requests":
                print("Too many requests, wait for 2 minutes and try to continue")
                # pause for 2 minutes to let the API chill for a sec.
                time.sleep(120)
                docs_bag = get_docs(application_number, config, doc_types)
        else:
            print(r.json())
            raise
    return docs_bag


def extract_abstract(xml_string):
    """Extract abstract text from USPTO XML document."""
    try:
        root = ET.fromstring(xml_string)

        # Find the ABSTRACT heading
        headings = root.findall('.//uscom:Heading', CONST.NAMESPACES)
        abstract_heading_id = None

        for heading in headings:
            heading_text = ''.join(heading.itertext()).strip().upper()
            if 'ABSTRACT' in heading_text:
                abstract_heading_id = heading.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')
                break

        # Find all paragraph elements
        paragraphs = root.findall('.//uscom:P', CONST.NAMESPACES)

        # If we found an ABSTRACT heading, find the first substantial paragraph after it
        if abstract_heading_id:
            # Extract the heading number (e.g., "h-1" -> 1)
            heading_num = int(abstract_heading_id.split('-')[1]) if '-' in abstract_heading_id else 0

            # Find the first paragraph after the heading with substantial content
            for p in root:
                p_id = p.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')
                if p_id:
                    # Extract paragraph number (e.g., "p-3" -> 3)
                    p_num = int(p_id.split('-')[1]) if '-' in p_id else 0

                    # Only consider paragraphs that come after the heading
                    if p_num > heading_num:
                        # Get only the direct text, not nested elements
                        text_parts = []
                        if p.text:
                            text_parts.append(p.text)
                        for child in p:
                            if child.tail:
                                text_parts.append(child.tail)
                        abstract_text = ''.join(text_parts).strip()

                        # Skip short paragraphs (likely page numbers or docket numbers)
                        # and return the first substantial paragraph
                        if len(abstract_text) > 100:
                            return abstract_text

        # Fallback: if no ABSTRACT heading found, try the old method
        # Look for first paragraph with substantial content
        for p in paragraphs:
            text_parts = []
            if p.text:
                text_parts.append(p.text)
            for child in p:
                if child.tail:
                    text_parts.append(child.tail)
            abstract_text = ''.join(text_parts).strip()

            # Return first paragraph with substantial content (>50 chars)
            if len(abstract_text) > 50:
                return abstract_text

        return None
    except Exception as e:
        print(f"Error parsing abstract: {e}")
        print(traceback.format_exc())
        return None


def extract_spec(xml_string, debug=False):
    try:
        root = ET.fromstring(xml_string)

        # Find the SUMMARY heading
        headings = root.findall('.//uscom:Heading', CONST.NAMESPACES)
        summary_heading_id = None
        background_heading_id = None

        for heading in headings:
            heading_text = ''.join(heading.itertext()).strip().upper()
            print(heading_text)
            if 'SUMMARY' in heading_text:
                summary_heading_id = heading.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')
            elif 'BACKGROUND' in heading_text:
                background_heading_id = heading.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')


        if summary_heading_id:
            summary_heading_num = int(summary_heading_id.split('-')[1]) if '-' in summary_heading_id else None
        else:
            summary_heading_num = None
        if background_heading_id:
            background_heading_num = int(background_heading_id.split('-')[1]) if '-' in background_heading_id else None
        else:
            background_heading_num = None

        if background_heading_num and summary_heading_num and background_heading_num > summary_heading_num:
            look_background_first = 1
        else:
            look_background_first = 0

        check_for_summary = summary_heading_num is not None and not look_background_first
        check_for_background = not check_for_summary and background_heading_num is not None

        text_parts = {
            'summary': [],
            'background': []
        }

        for child in root:
            p_id = child.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')
            if not p_id:
                continue

            # Extract paragraph number (e.g., "p-3" -> 3)
            p_num = int(p_id.split('-')[1]) if '-' in p_id else 0

            text = child.text
            if check_for_summary and p_num > summary_heading_num:
                if child.text:
                    # check for headings
                    if (len(text) > 0 and
                        not text.startswith('[') and
                        len(text) < 50 and  # Headings should be short
                        not text.replace('.', '').replace('-', '').isdigit()
                    ):
                        check_for_summary = False
                        check_for_background = background_heading_num is not None
                        continue
                    text_parts['summary'].append(child.text)

            elif check_for_background and p_num > background_heading_num:
                if child.text:
                    if (len(text) > 0 and
                        not text.startswith('[') and
                        len(text) < 50 and  # Headings should be short
                        not text.replace('.', '').replace('-', '').isdigit()
                    ):
                        if look_background_first:
                            check_for_summary = True
                            check_for_background = False
                        break
                    text_parts['background'].append(child.text)

        results = {
            'summary': "\n".join(text_parts['summary']),
            'background': "\n".join(text_parts['background'])
        }
        return results
    except Exception as e:
        print(f"Error parsing specification: {e}")
        print(traceback.format_exc())
        raise


def get_document_code(xml_string):
    """Extract document code (e.g., ABST, SPEC, DRWD) from XML."""
    try:
        root = ET.fromstring(xml_string)
        doc_code = root.find('.//uscom:DocumentCode', CONST.NAMESPACES)
        return doc_code.text if doc_code is not None else None
    except Exception as e:
        print(f"Error getting document code: {e}")
        return None

def parse_xml(docs, config):
    """Parse USPTO XML documents and extract information."""
    xml_url = None
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']

    # Find XML document URL
    for doc in docs:
        if doc['mimeTypeIdentifier'] == "XML":
            xml_url = doc['downloadUrl']
            break

    if not xml_url:
        raise NotFoundError(f'XML not found. Available docs: {[doc['mimeTypeIdentifier'] for doc in docs]}')

    # Download XML content
    r = requests.get(
        xml_url,
        headers={api_base: api_key}
    )

    # Try multiple encoding strategies
    content = None
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']

    for encoding in encodings:
        try:
            content = r.content.decode(encoding)
            # print(f"Successfully decoded with {encoding}")
            break
        except UnicodeDecodeError:
            continue

    # If all encodings fail, use utf-8 with error handling
    if content is None:
        content = r.content.decode('utf-8', errors='replace')
        print("Decoded with utf-8 using 'replace' error handling")

    # Alternative: use 'ignore' to skip invalid characters
    # content = r.content.decode('utf-8', errors='ignore')

    # Split into individual XML documents
    elements = content.split('<?xml version="1.0" encoding="utf-8"?>')[1:]
    elements = [
        '<?xml version="1.0" encoding="utf-8"?>' + e.split('</uspat:SpecificationDocument>')[0] + '</uspat:SpecificationDocument>'
        for e in elements
    ]

    # Process each document
    results = []
    for i, xml_doc in enumerate(elements):
        doc_code = get_document_code(xml_doc)

        # Extract information based on document type
        result = {
            'index': i,
            'document_code': doc_code,
        }

        # If it's an abstract document, extract the abstract text
        if doc_code == 'ABST':
            abstract = extract_abstract(xml_doc)
            result['abstract'] = abstract
            # print(f"\nDocument {i} - {doc_code}")
            # print(f"Abstract: {abstract}")

        if doc_code == 'SPEC':
            spec = extract_spec(xml_doc)
            result['background'] = spec.get('background', "")
            result['summary'] = spec.get('summary', "")
            # print(f"\nDocument {i} - {doc_code}")
            # print(f"Spec: {spec}")
        # else:
        #     print(f"\nDocument {i} - {doc_code}")

        results.append(result)

    # pick best results
    best_result = {
        'abstract': "",
        'background': "",
        'summary': "",
    }
    sections = ['abstract', 'background', 'summary']
    for result in results:
        for section in sections:
            if result.get(section) and len(result[section]) > len(best_result[section]):
                best_result[section] = result[section]

    return best_result

def get_all_patents(config):
    length = 10000
    page = 0
    error_count = 0
    limit = 100
    while length >= limit:
        try:
            df = get_patents(config, page=page, limit=limit)
            error_count = 0
        except KeyError as e:
            error_count += 1
            if error_count <= 3:
                print(f"Failed to get patents for page {page}. Trying again")
                continue
            else:
                print(f"Errored 3 times on page {page}. Returning.")
                break

        length = len(df)
        print(f"Selected {length} new patents from page {page} and added to the csv.")
        page +=1
    return


def get_bulk_docs(df, page, config, limit=2):

    patents = df[page*limit:(page +1)*limit]

    for i, row in patents.iterrows():
        specs = get_docs(row['application_number'], config, ['SPEC'])
        abstracts = get_docs(row['application_number'], config, ['ABST'])

        details = {
            'abstract': None,
            'summary': None,
            'background': None,
        }
        bags = [opt for bag in specs for opt in bag['downloadOptionBag']] + [opt for bag in abstracts for opt in bag['downloadOptionBag']]

        try:
            res = parse_xml(bags, config)
        except NotFoundError:
            print(f"No XML found for {row['application_number']}")
        print(res)

df = pd.read_csv('./filtered_patents.csv')
get_bulk_docs(df, 4, config)
