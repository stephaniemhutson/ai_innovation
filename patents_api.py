from configparser import ConfigParser
import requests
import pandas as pd
import json
from xml.etree import ElementTree as ET
import re
import os
import traceback
import time
import argparse

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
                    "valueFrom": "2018-01-01",
                    "valueTo": "2026-02-05"
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
                "applicationMetaData.firstApplicantName",
                "applicationMetaData.firstInventorName",
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
            "firstInventorName": "first_inventor",
            "firstApplicantName": "first_applicant"
        }

        row = {}
        for k, v in parsing_dict.items():
            row[v] = raw.get(k, None)

        if row.get('cpcs'):
            row['cpcs'] = ",".join(row['cpcs'])
        return row

    rows = [raw_to_row(raw) for raw in data]



    df = pd.DataFrame(rows)

    csv_file = 'patents_02_23_2026.csv'

    # First batch - write with headers
    if not os.path.exists(csv_file):
        df.to_csv(csv_file, index=False)
    else:
        # Subsequent batches - append without headers
        df.to_csv(csv_file, mode='a', header=False, index=False)

    return df


# # Possible documents to grab: ['ABST', 'SPEC', ]
def get_docs(application_number, config, doc_types, attempts=1):
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']
    try:
        r = requests.get(
            f'https://api.uspto.gov/api/v1/patent/applications/{application_number}/documents',
            headers={api_base: api_key},
            params={
                "documentCodes": doc_types
            }
        )
        print(r)
    except requests.exceptions.ConnectionError:
        print("ConnectionError, wait 60s and try again")
        time.sleep(60)
        r = requests.get(
            f'https://api.uspto.gov/api/v1/patent/applications/{application_number}/documents',
            headers={api_base: api_key},
            params={
                "documentCodes": doc_types
            }
        )
        print(r)
    try:
        docs_bag = r.json()['documentBag']
        # print(r.json()['documentBag'])
    except KeyError:
        if r.json().get('message'):
            if r.json()['message'] == "Too Many Requests":
                print("Too many requests, wait for 10 seconds and try to continue")
                # pause for 1 minutes to let the API chill for a sec.
                time.sleep(10)
                docs_bag = get_docs(application_number, config, doc_types)
        else:
            print(r.json())
            if attempts < 3:
                attempts +=1
                docs_bag = get_docs(application_number, config, doc_types, attempts)
            else:
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
                        abstract_text = ' '.join(text_parts).strip()

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

        if background_heading_num and summary_heading_num and background_heading_num < summary_heading_num:
            look_background_first = 1
        else:
            look_background_first = 0

        check_for_summary = summary_heading_num is not None and not look_background_first
        check_for_background = not check_for_summary and background_heading_num is not None

        text_parts = {
            'summary': [],
            'background': []
        }

        # Some backgrounds and summaries are quite long. In the interest of efficiency, limit to
        # 5 paragraphs for each sections.
        max_paragraphs = 10
        count = 0
        for child in root:
            p_id = child.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')
            if not p_id:
                continue
            # Extract paragraph number (e.g., "p-3" -> 3)
            p_num = int(p_id.split('-')[1]) if '-' in p_id else 0
            text = child.text
            if check_for_summary and p_num > summary_heading_num:
                if text:
                    # check for headings
                    if (len(text) > 0 and
                        (not text.startswith('[') or not text.startswith('(')) and # indicates a paragraph
                        len(text) < 50   # Headings should be short
                        # not text.replace('.', '').replace('-', '').isdigit()
                    ):
                        check_for_summary = False
                        check_for_background = background_heading_num is not None and not look_background_first
                        count = 0
                        continue
                    if count >= max_paragraphs:
                        check_for_summary = False
                        check_for_background = background_heading_num is not None and not look_background_first
                        count = 0
                        continue
                    text_parts['summary'].append(child.text)
                    count +=1

            elif check_for_background and p_num > background_heading_num:
                if text:
                    if (len(text) > 0 and
                        (not text.startswith('[') or not text.startswith('(')) and
                        len(text) < 50   # Headings should be short
                        # not text.replace('.', '').replace('-', '').isdigit()
                    ):
                        if look_background_first:
                            check_for_summary = True
                            check_for_background = False
                            count = 0
                            continue
                        check_for_background = False
                        check_for_summary = summary_heading_num is not None and look_background_first
                        count = 0
                        continue
                    if count >= max_paragraphs:
                        check_for_background = False
                        check_for_summary = summary_heading_num is not None and look_background_first
                        count = 0
                        continue
                    text_parts['background'].append(child.text)
                    count += 1
        results = {
            'summary': " ".join(text_parts['summary']),
            'background': " ".join(text_parts['background'])
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

def parse_all_xml(docs, config):
    """Parse USPTO XML documents and extract information."""
    xml_urls = {}
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']

    # Find XML document URL
    for doc in docs:
        doc_code = doc['DOC_TYPE']
        if doc['mimeTypeIdentifier'] == "XML":
            xml_urls[doc['downloadUrl']] = doc_code

    if len(xml_urls) == 0:
        raise NotFoundError(f'XML not found. Available docs: {[doc['mimeTypeIdentifier'] for doc in docs]}')

    best_result = {
        'abstract': "",
        'background': "",
        'summary': "",
    }
    sections = ['abstract', 'background', 'summary']

    for xml_url, doc_code in xml_urls.items():

        # If we've already gotten what we need from the abstract and the spec, then don't look at extra documents.
        if doc_code == "ABST" and len(best_result['abstract']) >= 300:
            continue
        elif doc_code == "SPEC" and len(best_result['background']) >= 300 and len(best_result['summary']) >= 300:
            continue
        # Download XML content
        try:
            # print(xml_url)
            r = requests.get(
                xml_url,
                headers={'X-API-KEY': api_key},
                allow_redirects=True,
                # timeout=30
            )
            print(r)
        except requests.exceptions.Timeout:
            print("Timed out")
        except requests.exceptions.ConnectionError:
            print("Connection Error, wait 60s, try again")
            time.sleep(60)
            r = requests.get(
                xml_url,
                headers={'X-API-KEY': api_key},
                allow_redirects=True,
                # timeout=30
            )
            print(r)

        # Try multiple encoding strategies
        content = None
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', ]

        for encoding in encodings:
            try:
                content = r.content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        # If all encodings fail, use utf-8 with error handling
        if content is None:
            ecoding = 'utf-8 -- replace errors'
            content = r.content.decode('utf-8', errors='replace')
            print("Decoded with utf-8 using 'replace' error handling")

        # Alternative: use 'ignore' to skip invalid characters

        # Split into individual XML documents
        elements = content.split('<?xml version="1.0" encoding="utf-8"?>')[1:]

        elements = [
            '<?xml version="1.0" encoding="utf-8"?>' + e.split('</uspat:SpecificationDocument>')[0] + '</uspat:SpecificationDocument>'
            for e in elements
        ]

        # Process each document
        for i, xml_doc in enumerate(elements):
            # Extract information based on document type
            if "<uspat:SpecificationDocument" not in xml_doc[:100]:
                # wrong document type.
                continue
            result = {
                'index': i,
                'document_code': doc_code,
            }

            # If it's an abstract document, extract the abstract text
            if doc_code == 'ABST':
                abstract = extract_abstract(xml_doc)
                result['abstract'] = abstract

            elif doc_code == 'SPEC':
                spec = extract_spec(xml_doc)
                result['background'] = spec.get('background', "")
                result['summary'] = spec.get('summary', "")
            else:
                try:
                    abstract = extract_abstract(xml_doc)
                    result['abstract'] = abstract
                except Exception as e:
                    print(traceback.format_exc())

            for section in sections:
                if result.get(section) and len(result[section]) > len(best_result[section]):
                    best_result[section] = result[section]

    return best_result

def get_all_patents(config, first_page=0):
    length = 10000
    page = first_page
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


def get_bulk_docs(df, page, config, limit=100):

    patents = df[page*limit:(page +1)*limit].to_dict('records')
    # for i, row in patents.iterrows():
    updated = []
    application_number = None
    for i, row in enumerate(patents):
        application_number = row['application_number']
        print(f"***** PATENT {application_number} ****")
        try:
            specs = get_docs(row['application_number'], config, ['SPEC'])
        except UnboundLocalError:
            # try one more time
            specs = get_docs(row['application_number'], config, ['SPEC'])
        try:
            abstracts = get_docs(row['application_number'], config, ['ABST'])
        except UnboundLocalError:
            # try one more time
            abstracts = get_docs(row['application_number'], config, ['ABST'])

        abstract_bags = [opt for bag in abstracts for opt in bag['downloadOptionBag']]
        for bag in abstract_bags:
            bag['DOC_TYPE'] = "ABST"

        spec_bags = [opt for bag in specs for opt in bag['downloadOptionBag']]
        for bag in spec_bags:
            bag['DOC_TYPE'] = "SPEC"

        details = {
            'abstract': None,
            'summary': None,
            'background': None,
        }
        bags = spec_bags + abstract_bags

        try:
            details = parse_all_xml(bags, config)

        except NotFoundError:
            print(f"No XML found for {row['application_number']}")
        # Update the dataframe at this specific index
        row['abstract'] = details['abstract']
        row['summary'] = details['summary']
        row['background'] = details['background']
        updated.append(row)

    updated_patents = pd.DataFrame(updated)
    batch = page//100
    csv_file = f'./patents_with_details__{batch}.csv'

    # First batch - write with headers
    if not os.path.exists(csv_file):
        updated_patents.to_csv(csv_file, index=False)
    else:
        # Subsequent batches - append without headers
        updated_patents.to_csv(csv_file, mode='a', header=False, index=False)

    return application_number


def save_batch(page, batch_file):
    open(f'data_batches/{batch_file}', 'w').write(str(page))


def load_batch(batch_file, first_page):
    try:
        return int(open(f'data_batches/{batch_file}').read()) + 1
    except:
        return first_page


def batch_pull_details(batch_file='batch.txt', last_page=1000, first_page=0):
    df = pd.read_csv('./patents_left_to_capture.csv')
    df = df.reset_index()
    most_recent_page = load_batch(batch_file, first_page)
    print(most_recent_page)
    page = most_recent_page
    limit = 5

    while page < last_page:
        last_application_number = get_bulk_docs(df, page, config, limit=limit)
        if last_application_number is None:
            print(f"Seem to have completed on application page {page - 1}")
            break
        print(f"Completed Page {page} with limit {limit}. Final Application number: {last_application_number}")
        save_batch(page, batch_file)
        page += 1


def _get_batch(batch):
    patents_cited = []
    applications_cited = []
    endpoint = f"us_patent_citation/"

    # Query with multiple patent numbers
    query = {
        "q": {"patent_id": batch},
        "f": ["patent_id", "citation_patent_id", "citation_date", "citation_category"]
    }
    response = requests.post(
        f"{config['USPTO']['URL']}{endpoint}",
        headers={'X-API-KEY': config["USPTO"]["KEY"], 'content-type': 'application/json'},
        json=query
    )

    response = response.json()

    if response.get("detail") and "Request was throttled." in response['detail']:
        match = re.search(r'(\d+)\s*second', response['detail'], re.IGNORECASE)
        if not match:
            sleep_time = 31
        else:
            sleep_time = int(match.group(1)) + 5
        print(f"Sleeping {sleep_time} seconds")
        time.sleep(sleep_time + 1)
        return _get_batch(batch)

    patent_response = response

    endpoint = f"us_application_citation/"

    query['f'] = ["patent_id", "citation_document_number", "citation_date", "citation_category"]
    response = requests.post(
        f"{config['USPTO']['URL']}{endpoint}",
        headers={'X-API-KEY': config["USPTO"]["KEY"], 'content-type': 'application/json'},
        json=query
    ).json()
    if response.get("detail") and "Request was throttled." in response['detail']:
        match = re.search(r'(\d+)\s*second', response['detail'], re.IGNORECASE)
        if not match:
            sleep_time = 31
        else:
            sleep_time = int(match.group(1)) + 5
        print(f"Sleeping {sleep_time} seconds")
        time.sleep(sleep_time)
        return _get_batch(batch)

    return patent_response.get('us_patent_citations', []), response.get('us_application_citations', [])



def get_patent_citations(beginning_batch=0):
    df = pd.read_csv('./patents_for_citations_02_22_2026.csv')
    patent_ids = df[df['patent_number'].notnull()]['patent_number'].unique().tolist()

    def safe_to_int(value):
        """
        Safely converts a string (or other value) to a float.
        Returns the float if conversion is successful, otherwise returns the default value.
        """
        try:
            return int(float(value))
        except (ValueError, TypeError):
            # Catches cases where float() conversion fails (e.g., "hello", "", None)
            return value
    patent_ids = [safe_to_int(patent) for patent in patent_ids]

    count = 1
    patents_cited = []
    applications_cited = []
    batch_size = 100
    num_batches = len(patent_ids) // batch_size + 1
    for j in range(num_batches-beginning_batch):

        batch = patent_ids[(j+beginning_batch)*batch_size:(j+1+beginning_batch)*batch_size]

        patents_cited, applications_cited = _get_batch(batch)
        patents_cited_df = pd.DataFrame(patents_cited)
        applications_cited_df = pd.DataFrame(applications_cited)
        patents_cited_df.to_csv('./data/patents_cited.csv', mode="a", header=False, index=False)
        applications_cited_df.to_csv('./data/applications_cited.csv', mode="a", header=False, index=False)
        print(f"Finished with batch {j+beginning_batch}")

def _get_patent_app_numbers(batch):
    endpoint = f'publication/'
    query = {
        "q": {"document_number": batch},
        "f": ['document_number', 'granted_pregrant_crosswalk']
    }
    response = requests.post(
        f"https://search.patentsview.org/api/v1/{endpoint}",
        headers={'X-API-KEY': config["USPTO"]["KEY"], 'content-type': 'application/json'},
        json=query
    ).json()

    if response.get("detail") and "Request was throttled." in response['detail']:
        match = re.search(r'(\d+)\s*second', response['detail'], re.IGNORECASE)
        if not match:
            sleep_time = 31
        else:
            sleep_time = int(match.group(1)) + 5
        print(f"Sleeping {sleep_time} seconds")
        time.sleep(sleep_time)
        return _get_patent_app_numbers(batch)

    publications = response.get('publications',[])

    rows = []

    for pub in publications:
        for cw in pub.get('granted_pregrant_crosswalk', []):
            rows.append(
                {
                    'patent_id': cw.get('patent_id'),
                    'application_number': cw.get('application_number'),
                    'citation_document_number': pub.get('document_number')
                }
            )
    return rows

def get_application_patent_numbers(beginning_batch=0):

    applications = pd.read_csv('./data/applications_cited.csv')

    document_numbers = applications['citation_document_number'].unique().tolist()

    batch_size = 200
    num_batches = len(document_numbers)//batch_size + 1

    for i in range(num_batches - beginning_batch):
        batch = document_numbers[(i+beginning_batch)*batch_size:(i+1+beginning_batch)*batch_size]
        batch = [str(b) for b in batch]

        patent_application_numbers = _get_patent_app_numbers(batch)

        df = pd.DataFrame(patent_application_numbers)
        df.to_csv('./data/patent_application_citation_crosswalk.csv', mode='a', header=False, index=False)
        print(f"Finished batch {i-beginning_batch}")



if __name__ == '__main__':
    method = input("""
        Which method?

        [1] batch_pull_details
        [2] get_all_patents
        [3] get_patent_citations
        [4] get_application_patent_numbers
    """)

    method = int(method[0])
    parser = argparse.ArgumentParser(description='Batch pull patent details')
    parser.add_argument('-f', '--file', type=str, default='batch.txt',
                        help='Name of the batch file (default: batch.txt)')
    parser.add_argument('-lp', '--lastpage', type=int, default=1000,
                        help='The last page to pull from')
    parser.add_argument('-fp', '--firstpage', type=int, default=1000,
                        help='The first page to pull from. Only needed if batch file empty')
    parser.add_argument('-b', '--batch', type=int, default=0)
    args = parser.parse_args()


    if method == 1:
        try:
            batch_pull_details(args.file, args.lastpage, args.firstpage)
        except KeyboardInterrupt:
            print("Gracefully exiting.")
    elif method == 2:
        try:
            get_all_patents(config, 0)
        except KeyboardInterrupt:
            print("Gracefully exiting.")
    elif method == 3:
        try:
            get_patent_citations(args.batch)
        except KeyboardInterrupt:
            print("Gracefully exiting.")
    elif method == 4:
        try:
            get_application_patent_numbers(args.batch)
        except KeyboardInterrupt:
            print("Gracefully exiting.")
