"""Portable public raw-source recordings, separated from operational caches."""
import base64
import gzip
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from .response_archive import public_url
from .transport import Response


def write_bundle(archive, directory, *, part_bytes=524288):
    if type(part_bytes) is not int or not 1024<=part_bytes<=1048576:
        raise ValueError('bounded bundle part size required')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    # Each line is one exact observation; no SQLite schemas, headers or caches.
    temporary=directory/'source-recordings.jsonl.gz.tmp'
    count=0
    try:
        with temporary.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as compressed:
                for row in archive.observations():
                    response=archive.get(row['url'],row['sha256'],datetime.fromisoformat(row['retrieved_at']))
                    if response is None:raise ValueError('source observation absent')
                    payload=dict(row,body_base64=base64.b64encode(response.body).decode('ascii'))
                    compressed.write(json.dumps(payload,separators=(',',':')).encode()+b'\n');count+=1
        sha=hashlib.sha256();parts=[]
        with temporary.open('rb') as raw:
            while True:
                body=raw.read(part_bytes)
                if not body:break
                sha.update(body);name=f'sources.jsonl.gz.part{len(parts):04d}'
                (directory/name).write_bytes(body)
                parts.append(dict(file=name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        result=dict(schema_version=1,format='gzip-jsonl-public-response-observations-v1',observations=count,
                    compressed_sha256=sha.hexdigest(),parts=parts,headers_stored=False,credentials_stored=False)
        (directory/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:
        if temporary.exists():temporary.unlink()


def read_bundle(directory):
    """Validate all part and body hashes before yielding reconstructed responses."""
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('schema_version')!=1 or manifest.get('format')!='gzip-jsonl-public-response-observations-v1':
        raise ValueError('unsupported evidence bundle')
    combined=io.BytesIO()
    for index,part in enumerate(manifest['parts']):
        if part['file']!=f'sources.jsonl.gz.part{index:04d}':raise ValueError('invalid part path/order')
        body=(directory/part['file']).read_bytes()
        if len(body)!=part['bytes'] or hashlib.sha256(body).hexdigest()!=part['sha256']:raise ValueError('bundle part integrity failure')
        combined.write(body)
    if hashlib.sha256(combined.getvalue()).hexdigest()!=manifest['compressed_sha256']:raise ValueError('bundle integrity failure')
    combined.seek(0);count=0
    with gzip.GzipFile(fileobj=combined,mode='rb') as raw:
        for line in raw:
            p=json.loads(line);public_url(p['url'])
            r=Response(p['url'],base64.b64decode(p['body_base64'],validate=True),datetime.fromisoformat(p['retrieved_at']))
            if r.sha256!=p['sha256'] or r.retrieved_at.utcoffset() is None:raise ValueError('raw source integrity failure')
            count+=1
    if count!=manifest['observations']:raise ValueError('observation count mismatch')
    combined.seek(0)
    with gzip.GzipFile(fileobj=combined,mode='rb') as raw:
        for line in raw:
            p=json.loads(line)
            yield Response(p['url'],base64.b64decode(p['body_base64'],validate=True),datetime.fromisoformat(p['retrieved_at']))
