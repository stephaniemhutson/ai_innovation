from configparser import ConfigParser
import requests
import pandas as pd
import json
from xml.etree import ElementTree as ET
import re
import os

import CONST

config = ConfigParser()
config.read('config.ini')


class NotFoundError(Exception):
    pass



def get_patents(config, page=0, limit=100):
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']
    url = config['ODP']['URL']

    r = requests.post(
        url = 'https://api.uspto.gov/api/v1/patent/applications/search',
        headers={api_base: api_key, 'content-type': 'application/json'},
        json={
            "q": '("data center*" OR datacenter*) OR (A?I OR AI OR "artificial intelligence" OR "machine learning") OR (?PU AND comput*) OR (cooling)',
            "filters": [
              {
                  "name": "applicationMetaData.cpcClassificationBag",
                  # Using values which end in 00 seems to broadly
                  "value": CONST.CPC_lui_2022
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
                # "applicationMetaData.applicationStatusDescriptionText",
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
            "applicationStatusCode": "status_code"
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
def get_docs(application_number, config):
    api_key = config['ODP']['KEY']
    api_base = config['ODP']['API_BASE']

    r = requests.get(
        f'https://api.uspto.gov/api/v1/patent/applications/{application_number}/documents',
        headers={api_base: api_key},
        params={
            "documentCodes": ["SPEC"]
        }
    )
    try:
        docs_bag = r.json()['documentBag']
    except KeyError:
        print(r.json())
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
            for p in paragraphs:
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
                        if len(abstract_text) > 50:
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
        return None

def extract_spec(xml_string, sections=None, debug=False):
    """
    Extract specification text from USPTO XML document.

    Args:
        xml_string: The XML string to parse
        sections: List of section names to extract (e.g., ['SUMMARY', 'BACKGROUND'])
                 If None, extracts all sections
        debug: If True, prints debugging information
    """
    try:
        root = ET.fromstring(xml_string)

        # Find all paragraph and heading elements
        paragraphs = root.findall('.//uscom:P', CONST.NAMESPACES)
        headings = root.findall('.//uscom:Heading', CONST.NAMESPACES)

        if debug:
            print(f"Found {len(headings)} headings and {len(paragraphs)} paragraphs")

        # Create a mapping of all elements by their position in the document
        element_map = {}

        for heading in headings:
            heading_text = ''.join(heading.itertext()).strip()
            heading_id = heading.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')

            # Only include actual section headings (short, all caps, no paragraph numbers)
            # Skip if it starts with [ or is very long (likely a paragraph misidentified as heading)
            if (len(heading_text) > 0 and
                not heading_text.startswith('[') and
                len(heading_text) < 100 and  # Headings should be short
                not heading_text.replace('.', '').replace('-', '').isdigit()):
                element_map[heading_id] = {
                    'type': 'heading',
                    'text': heading_text,
                    'id': heading_id
                }
                if debug:
                    print(f"Heading: '{heading_text}' (id: {heading_id})")
            else:
                paragraphs = paragraphs.append(heading)
                if debug:
                    print(f"SKIPPED Heading (too long or starts with [): '{heading_text[:50]}...' (id: {heading_id})")

        for p in paragraphs:
            p_number = p.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}pNumber')
            p_id = p.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}id')

            # Get ALL text content from the paragraph, including nested elements
            paragraph_text = ''.join(p.itertext()).strip()

            # Remove common metadata patterns
            # Filter out attorney docket numbers, page numbers, and reference IDs
            if paragraph_text and not (
                paragraph_text.startswith('Attorney Docket') or
                paragraph_text.startswith('{') or
                len(paragraph_text) < 20 or  # Very short snippets
                paragraph_text.replace('.', '').replace('-', '').replace('/', '').isdigit()  # Just numbers
            ):
                element_map[p_id] = {
                    'type': 'paragraph',
                    'text': paragraph_text,
                    'p_number': p_number,
                    'id': p_id
                }
                if debug:
                    print(f"Paragraph {p_number} (id: {p_id}): {paragraph_text[:100]}...")

        # Sort elements by their ID to maintain document order
        sorted_elements = sorted(element_map.values(), key=lambda x: x['id'])

        # If specific sections requested, filter to only those sections
        if sections:
            sections_upper = [s.upper() for s in sections]
            filtered_elements = []
            current_section = None
            include_current = False

            for element in sorted_elements:
                if element['type'] == 'heading':
                    heading_text_upper = element['text'].upper()
                    # Check if ANY of the requested sections appear in this heading
                    include_current = any(section in heading_text_upper for section in sections_upper)
                    current_section = element['text']

                    if include_current:
                        filtered_elements.append(element)
                        if debug:
                            print(f"Including section: {current_section}")
                    else:
                        if debug:
                            print(f"Skipping section: {current_section}")
                elif include_current:
                    filtered_elements.append(element)
                    if debug:
                        print(f"Including paragraph under {current_section}")

            sorted_elements = filtered_elements

        if debug:
            print(f"Final element count: {len(sorted_elements)}")

        # Build the specification text
        spec_parts = []
        for element in sorted_elements:
            if element['type'] == 'heading':
                spec_parts.append(f"\n{element['text']}\n")
            else:
                spec_parts.append(element['text'])

        spec_text = '\n\n'.join(spec_parts).strip()
        return spec_text

    except Exception as e:
        print(f"Error parsing specification: {e}")
        return None

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
            print(f"Successfully decoded with {encoding}")
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
            'xml': xml_doc
        }

        # If it's an abstract document, extract the abstract text
        if doc_code == 'ABST':
            abstract = extract_abstract(xml_doc)
            result['abstract'] = abstract
            print(f"\nDocument {i} - {doc_code}")
            print(f"Abstract: {abstract}")

        if doc_code == 'SPEC':
            spec = extract_spec(xml_doc, sections=['SUMMARY', 'BACKGROUND', 'TECHNICAL FIELD'], debug = True)
            result['spec'] = spec
            print(f"\nDocument {i} - {doc_code}")
            print(f"Spec: {spec}")
        else:
            print(f"\nDocument {i} - {doc_code}")

        results.append(result)

    return results


df = get_patents(config, limit=6)

print(df)

# for application_number in application_numbers:
#     docs_bag = get_docs(application_number, config)

#     for item in docs_bag:
#         print(f"Patent {application_number}")

#         docs = item['downloadOptionBag']
#         try:
#             results = parse_xml(docs, config)
#         except NotFoundError:
#             continue

#         abstract_doc = next((r for r in results if r['document_code'] == 'ABST'), None)
#         if abstract_doc:
#             print(abstract_doc['abstract'])

#         spec_doc = next((r for r in results if r['document_code'] == 'SPEC'), None)
#         if spec_doc:
#             print(spec_doc['spec'])


