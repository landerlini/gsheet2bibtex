from fastapi import FastAPI
import json
import os
from fastapi.responses import PlainTextResponse
import urllib, urllib.request
import csv
import logging

BASE_URL = os.getenv("BASE_URL", "/")
DEBUG = os.getenv("DEBUG", "false").lower() in ["1", "true", "yes"]
app = FastAPI(root_path=BASE_URL)

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)15s | %(name)15s | %(levelname)8s | %(message)s'
    )

def urllib_get(url: str, timeout: int = 10):
    """
    Simple urllib GET with User-Agent header and timeout
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def read_gsheet(spreadsheet_id: str):
    """
    Read a simple spreadsheet from Google Sheets and loops over the row as dictionaries {column: value}
    """
    address = "https://docs.google.com/spreadsheets/d/%s/export?format=csv" % spreadsheet_id
    logger = logging.getLogger("read_gsheet")
    logger.debug(f"Accessing spreadsheet from {address}")

    try:
        resp = urllib_get(address)
    except urllib.error.HTTPError as exception:
        logger.error(f"Error {exception} accessing {address}")
        raise exception
        
    headers = None
    for row in csv.reader(str(resp, 'utf-8').split('\r\n')):
        if headers is None: 
            headers = row
        else:        
            logger.debug(f"Processing row {row}")
            yield {k: v for k, v in zip(headers, row)}


def generate_bibtex(spreadsheet_id: str) -> str:
    """Connects to INSPIRE to generate the BibTeX and concatenates them in the returned string"""
    ret = []
    logger = logging.getLogger("generate_bibtex")
    for row in read_gsheet(spreadsheet_id):
        inspire_id = row.get("InspireId")
        if not inspire_id or inspire_id in ['', ' ', '  ']:
            logger.error(f"Missing InspireId in row {row}")
            continue


        bibtex = row.get("BibTeX")
        if not '{' in bibtex or bibtex.startswith("%"):
            try:
                resp = urllib_get("https://inspirehep.net/api/literature?q=%s" % inspire_id)
            except urllib.error.HTTPError as exception:
                logger.error(f"Error {exception} accessing inspire record {inspire_id}")
                ret.append(f"%% INSPIRE ERROR FOR {inspire_id} ({row.get('Comment', '')})")
                continue

            try:
                decoded_resp = json.loads(resp)
            except json.JSONDecodeError:
                logger.error(f"Failed decoding JSON:\n{str(resp, 'utf-8')}")
                ret.append(f"%% INSPIRE ERROR FOR {inspire_id} ({row.get('Comment', '')})")
                continue
            
            if len(decoded_resp['hits']) == 0:
                logger.error(f"Failed retrieving BibTeX for {inspire_id}")
                ret.append(f"%% INSPIRE ERROR FOR {inspire_id} ({row.get('Comment', '')})")
                continue
                
            inspire_number = json.loads(resp)['hits']['hits'][0]['id']
            try:
                resp = urllib_get("https://inspirehep.net/api/literature/%d?format=bibtex" % int(inspire_number))
            except urllib.error.HTTPError as exception:
                logger.error(f"Failed retrieving BibTeX for {inspire_id} (#{inspire_number}): {exception}")
                ret.append(f"%% ERROR RETRIEVEING BIBTEX FOR {inspire_id} ({row.get('Comment', '')})")
                continue
                
            bibtex = str(resp, 'utf-8')

        ret.append(f"%%  {row.get('Comment', '')} \n%%  {row.get('Title', '')}\n{bibtex}")
    
    return "\n\n".join(ret)

@app.get(BASE_URL + "{gsheet_id}.csv", response_class=PlainTextResponse)
async def read_root(gsheet_id: str):
    return generate_bibtex(gsheet_id)