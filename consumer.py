from scrapi_tools import lint
from scrapi_tools.document import RawDocument, NormalizedDocument
from lxml import etree
import requests
import datetime
import re

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(1)
NAME = 'SciTech'


def consume(days_back=1, end_date=None, **kwargs):
    """A function for querying the SciTech Connect database for raw XML. The XML is chunked into smaller pieces, each representing data
    about an article/report. If there are multiple pages of results, this function iterates through all the pages."""

    start_date = (TODAY - datetime.timedelta(days_back)).strftime('%m/%d/%Y')
    base_url = 'http://www.osti.gov/scitech/scitechxml'
    parameters = kwargs
    parameters['EntryDateFrom'] = start_date
    parameters['EntryDateTo'] = end_date
    parameters['page'] = 0
    morepages = 'true'
    xml_list = []
    elements_url = 'http://purl.org/dc/elements/1.1/'

    while morepages == 'true':
        xml = requests.get(base_url, params=parameters).text
        xml_root = etree.XML(xml.encode('utf-8'))
        for record in xml_root.find('records'):
            xml_list.append(RawDocument({
                'doc': etree.tostring(record, encoding='ASCII'),
                'source': NAME,
                'doc_id': record.find(str(etree.QName(elements_url, 'ostiId'))).text,
                'filetype': 'xml',
            }))
        parameters['page'] += 1
        morepages = xml_root.find('records').attrib['morepages']
    return xml_list


def normalize(raw_doc, timestamp):
    """A function for parsing the list of XML objects returned by the consume function.
    Returns a list of Json objects in a format that can be recognized by the OSF scrapi."""
    raw_doc = raw_doc.get('doc')
    terms_url = 'http://purl.org/dc/terms/'
    elements_url = 'http://purl.org/dc/elements/1.1/'
    record = etree.XML(raw_doc)

    contributor_list = record.find(str(etree.QName(elements_url, 'creator'))).text.split(';') or ['DoE']
    # for now, scitech does not grab emails, but it could soon?
    contributors = []
    for name in contributor_list:
        name = name.strip()
        if name[0] in ['/', ',', 'et. al']:
            continue
        if '[' in name:
            name = name[:name.index('[')].strip()
        contributor = {}
        contributor['full_name'] = name
        contributor['email'] = ''
        contributors.append(contributor)

    tags = record.find(str(etree.QName(elements_url, 'subject'))).text
    tags = re.split(',(?!\s\&)|;', tags) if tags is not None else []
    tags = [tag.strip() for tag in tags]

    normalized_dict = {
        'title': record.find(str(etree.QName(elements_url, 'title'))).text,
        'contributors': contributors,
        'properties': {
            'article_type': record.find(str(etree.QName(elements_url, 'type'))).text or 'Not provided',
            'date_entered': record.find(str(etree.QName(elements_url, 'dateEntry'))).text or 'Not provided',
            'research_org': record.find(str(etree.QName(terms_url, 'publisherResearch'))).text or 'Not provided',
            'research_sponsor': record.find(str(etree.QName(terms_url, 'publisherSponsor'))).text or 'Not provided',
            'research_country': record.find(str(etree.QName(terms_url, 'publisherCountry'))).text or 'Not provided',
            'identifier_info': {
                'identifier': record.find(str(etree.QName(elements_url, 'identifier'))).text or "Not provided",
                'identifier_report': record.find(str(etree.QName(elements_url, 'identifierReport'))).text or "Not provided",
                'identifier_contract': record.find(str(etree.QName(terms_url, 'identifierDOEcontract'))) or "Not provided",
                'identifier_citation': record.find(str(etree.QName(terms_url, 'identifier-citation'))) or "Not provided",
                'identifier_other': record.find(str(etree.QName(elements_url, 'identifierOther'))) or "Not provided"
            },
            'relation': record.find(str(etree.QName(elements_url, 'relation'))).text or "Not provided",
            'coverage': record.find(str(etree.QName(elements_url, 'coverage'))).text or "Not provided",
            'format': record.find(str(etree.QName(elements_url, 'format'))).text or "Not provided",
            'language': record.find(str(etree.QName(elements_url, 'language'))).text or "Not provided"
        },
        'meta': {},
        'id': {
            'service_id': record.find(str(etree.QName(elements_url, 'ostiId'))).text,
            'doi': record.find(str(etree.QName(elements_url, 'doi'))).text or 'Not provided',
            'url': record.find(str(etree.QName(terms_url, 'identifier-purl'))).text or "Not provided",
        },
        'source': NAME,
        'timestamp': str(timestamp),
        'date_created': record.find(str(etree.QName(elements_url, 'date'))).text,
        'description': record.find(str(etree.QName(elements_url, 'description'))).text or 'No description provided',
        'tags': tags or [],
    }
    return NormalizedDocument(normalized_dict)


if __name__ == '__main__':
    print(lint(consume, normalize))
