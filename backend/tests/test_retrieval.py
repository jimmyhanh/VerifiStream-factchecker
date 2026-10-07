"""M5 deterministic network fixtures, lineage and meaningful error-path coverage."""
import hashlib
import json
from uuid import UUID, uuid4
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.shared.config import Settings
from app.models.video import VideoRecord, VideoStatus
from app.models.retrieval import SearchHit, RetrievalRequest
from app.models.proposition import DecompositionRun
from app.database.repository import JsonVideoRepository
from app.claims.repository import JsonClaimRepository
from app.decomposition.repository import JsonDecompositionRepository
from app.retrieval.repository import JsonRetrievalRepository
from app.retrieval.fetcher import (PublicHTTPSFetcher, FetchedPage, RetrievalError,
    canonical_url, public_addresses, PinnedHTTPSConnection)
from app.retrieval.search import BraveSearchProvider
from app.retrieval.passages import LexicalPassageExtractor
from test_decomposition import source_run

BODY = b'<html><head><title>City report</title><meta property="og:site_name" content="City Office"><meta property="article:published_time" content="2024-06-01"></head><body><script>made up hidden school story</script><p>In 2024, London opened 2 schools.</p><p>Other services are unchanged.</p></body></html>'


def page(url='https://example.org/report', body=BODY, content_type='text/html'):
    return FetchedPage(url, content_type, body, hashlib.sha256(body).hexdigest())


class Search:
    name = 'fixture-search-v1'
    def __init__(self, hits=None, error=None):
        self.hits = hits if hits is not None else [SearchHit(url='https://example.org/report')]
        self.error, self.calls = error, []
    def search(self, query, count):
        self.calls.append((query, count))
        if self.error: raise self.error
        return self.hits


class Fetcher:
    def __init__(self): self.calls = []
    def fetch(self, url):
        self.calls.append(url)
        if url.endswith('/failed'): raise RetrievalError('http_403')
        return page(url)


@pytest.fixture
def setup(tmp_path):
    config = Settings(storage_root=tmp_path)
    video = VideoRecord(id=uuid4(), status=VideoStatus.completed, original_filename='sample.mp4',
        size_bytes=1, sha256='a'*64, duration_seconds=8)
    JsonVideoRepository(tmp_path).save(video)
    claim = source_run('In 2024, London opened 2 schools.', video.id)
    JsonClaimRepository(tmp_path).save(claim)
    search, fetcher = Search(), Fetcher()
    client = TestClient(create_app(config, search_provider=search, source_fetcher=fetcher))
    base = f'/videos/{video.id}'
    source = client.post(base+'/decompositions', json={}).json()
    assert source['status']=='completed'
    proposition = source['results'][0]['propositions'][0]
    return config, client, base, source, proposition, search, fetcher


def body(setup, **kwargs):
    return {'proposition_ids':[setup[4]['id']], **kwargs}


def test_retrieval_exact_passages_restart_and_immutable_history(setup):
    config, client, base, source, proposition, search, fetcher = setup
    response = client.post(base+'/retrievals', json=body(setup))
    assert response.status_code == 201
    run = response.json()
    assert run['status']=='completed' and run['results'][0]['status']=='retrieved'
    assert run['decomposition_snapshot']==source
    assert run['decomposition_run_id']==source['id'] and len(run['decomposition_sha256'])==64
    assert run['results'][0]['proposition_id']==proposition['id']
    snapshot = run['sources'][0]
    assert snapshot['publisher']=='City Office' and snapshot['publication_date']=='2024-06-01'
    assert snapshot['primary_secondary']=='unknown' and snapshot['independence']=='unknown'
    assert 'hidden' not in snapshot['text']
    assert snapshot['text_sha256']==hashlib.sha256(snapshot['text'].encode()).hexdigest()
    for passage in run['results'][0]['passages']:
        assert snapshot['text'][passage['char_start']:passage['char_end']]==passage['text']
    restarted = TestClient(create_app(config))
    assert restarted.get(base+'/retrievals/'+run['id']).json()==run
    second=client.post(base+'/retrievals',json=body(setup)).json()
    assert second['id']!=run['id']
    assert len(restarted.get(base+'/retrievals').json())==2
    repo=JsonRetrievalRepository(config.storage_root)
    with pytest.raises(ValueError): repo.save(repo.get(UUID(source['video_id']),UUID(run['id'])))


def test_manual_mode_no_search_and_url_content_duplicates(setup):
    _, client, base, _, p, search, fetcher=setup
    request=body(setup,mode='manual_urls',source_urls={p['id']:[
        'https://example.org/report#one','https://example.org/report#two','https://another.org/copy','https://example.org/failed']})
    run=client.post(base+'/retrievals',json=request).json()
    assert search.calls==[] and len(fetcher.calls)==3
    assert run['discovery_provider']=='manual-urls-v1'
    assert run['results'][0]['status']=='partial'
    assert run['results'][0]['attempts'][1]['status']=='duplicate_url'
    assert run['sources'][1]['duplicate_of_source_id']==run['sources'][0]['id']
    assert len(run['results'][0]['passages'])==2


def test_missing_context_does_not_search_and_user_context_preserved(setup):
    config,client,base,source,p,search,_=setup
    source=DecompositionRun.model_validate_json(json.dumps(source));source.id=uuid4()
    source.results[0].propositions[0].needs_context=True
    JsonDecompositionRepository(config.storage_root).save(source)
    data=body(setup,decomposition_run_id=str(source.id))
    run=client.post(base+'/retrievals',json=data).json()
    assert run['results'][0]['status']=='needs_context' and not search.calls
    data['contexts']={p['id']:'London local education authority, calendar year 2024'}
    run=client.post(base+'/retrievals',json=data).json()
    assert run['results'][0]['context_origin']=='user_supplied'
    assert run['decomposition_snapshot']['results'][0]['propositions'][0]['text']==p['text']
    assert 'calendar year 2024' in search.calls[0][0]


@pytest.mark.parametrize('extra',[
    {'proposition_ids':[]}, {'proposition_ids':['bad']}, {'contexts':{str(uuid4()):'unknown'}},
    {'mode':'manual_urls'}, {'mode':'search','source_urls':{str(uuid4()):['https://example.org/']}}])
def test_bad_requests(setup,extra):
    assert setup[1].post(setup[2]+'/retrievals',json=body(setup,**extra)).status_code==422


def test_unknown_ids_failed_source_and_tampered_lineage(setup):
    config,client,base,source,*_=setup
    assert client.post(base+'/retrievals',json=body(setup,proposition_ids=[str(uuid4())])).status_code==404
    assert client.post(base+'/retrievals',json=body(setup,decomposition_run_id=str(uuid4()))).status_code==404
    assert client.get(base+'/retrievals/'+str(uuid4())).status_code==404
    assert client.get(f'/videos/{uuid4()}/retrievals').status_code==404
    for status,hash_value in [('failed',source['claim_snapshot_sha256']),('completed','bad')]:
        changed=DecompositionRun.model_validate_json(json.dumps(source));changed.id=uuid4();changed.status=status
        changed.claim_snapshot_sha256=hash_value
        JsonDecompositionRepository(config.storage_root).save(changed)
        assert client.post(base+'/retrievals',json=body(setup,decomposition_run_id=str(changed.id))).status_code==409


def test_no_results_and_failed_search_history(setup):
    config,client,base,_,_,search,_=setup
    search.hits=[]
    first=client.post(base+'/retrievals',json=body(setup)).json()
    assert first['results'][0]['status']=='no_passages' and first['sources']==[]
    search.error=RuntimeError('secret-token')
    failed=client.post(base+'/retrievals',json=body(setup))
    assert failed.json()['status']=='failed' and 'secret-token' not in failed.text
    assert client.get(base+'/retrievals/'+first['id']).json()==first
    missing=TestClient(create_app(config)).post(base+'/retrievals',json=body(setup)).json()
    assert missing['results'][0]['error_code']=='search_not_configured'


def test_busy_health_and_capacity_release(setup):
    config,_,base,*_=setup
    entered,release=Event(),Event()
    class Blocking(Search):
        def search(self,query,count):
            entered.set();assert release.wait(5)
            return []
    client=TestClient(create_app(config,search_provider=Blocking()))
    with ThreadPoolExecutor() as executor:
        future=executor.submit(client.post,base+'/retrievals',json=body(setup))
        assert entered.wait(2)
        try:
            assert client.post(base+'/retrievals',json=body(setup)).status_code==503
            assert client.get('/health').status_code==200
        finally:release.set()
        assert future.result().status_code==201
    assert client.post(base+'/retrievals',json=body(setup)).status_code==201


@pytest.mark.parametrize('url',[
    'http://example.org/','file:///etc/passwd','https://127.0.0.1/','https://[::1]/',
    'https://169.254.169.254/','https://10.0.0.1/','https://user:pass@example.org/',
    'https://example.org:8443/','https://example.org/\r\nX:yes','https://a.local/',
    'https://example.org\\@127.0.0.1/','https://224.0.0.1/'])
def test_unsafe_urls(url):
    with pytest.raises(RetrievalError):canonical_url(url)


def test_dns_rejects_mixed_public_private_and_multicast(monkeypatch):
    import app.retrieval.fetcher as module
    for addresses in [['8.8.8.8','127.0.0.1'],['224.0.0.1']]:
        monkeypatch.setattr(module.socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',(ip,443)) for ip in addresses])
        with pytest.raises(RetrievalError):public_addresses('example.org')


class Response:
    def __init__(self,status=200,headers=None,body=b'Hello'):
        self.status=status;self.headers=headers or {'Content-Type':'text/plain'};self.body=body
    def getheader(self,key,default=None):return self.headers.get(key,default)
    def read1(self,n):chunk,self.body=self.body[:n],self.body[n:];return chunk


def transport(monkeypatch,responses):
    import app.retrieval.fetcher as module
    calls=[]
    monkeypatch.setattr(module,'public_addresses',lambda host:['8.8.8.8'])
    class Connection:
        sock=None
        def __init__(self,host,address,timeout):calls.append((host,address))
        def request(self,*args,**kwargs):calls.append(kwargs)
        def getresponse(self):return responses.pop(0)
        def close(self):pass
    monkeypatch.setattr(module,'PinnedHTTPSConnection',Connection)
    return calls


def test_redirect_revalidated_and_credentials_not_forwarded(monkeypatch):
    calls=transport(monkeypatch,[Response(302,{'Location':'https://127.0.0.1/secret'})])
    with pytest.raises(RetrievalError,match='unsafe_url'):PublicHTTPSFetcher().fetch('https://example.org/')
    assert len(calls)==2
    calls=transport(monkeypatch,[Response(302,{'Location':'https://another.org/'})])
    with pytest.raises(RetrievalError,match='redirect_blocked'):
        PublicHTTPSFetcher().request('https://example.org/',{'application/json'},headers={'X-Subscription-Token':'secret'})
    assert len(calls)==2


@pytest.mark.parametrize('response,code',[
    (Response(body=b'123456'),'source_too_large'),
    (Response(headers={'Content-Type':'application/pdf'}),'unsupported_content_type'),
    (Response(headers={'Content-Type':'text/plain','Content-Encoding':'gzip'}),'unsupported_content_encoding'),
    (Response(403),'http_403')])
def test_fetch_failures(monkeypatch,response,code):
    transport(monkeypatch,[response])
    with pytest.raises(RetrievalError,match=code):PublicHTTPSFetcher(max_bytes=5).fetch('https://example.org/')


def test_valid_fetch_and_redirect(monkeypatch):
    calls=transport(monkeypatch,[Response(302,{'Location':'/final'}),Response(body=b'school')])
    result=PublicHTTPSFetcher().fetch('https://example.org/start')
    assert result.final_url=='https://example.org/final' and result.body==b'school'
    assert result.raw_sha256==hashlib.sha256(b'school').hexdigest()
    assert calls[0]==('example.org','8.8.8.8')


def test_brave_auth_parameters_and_malformed_response():
    class Transport:
        def request(self,url,allowed_types,headers,redirects):
            assert 'q=London+schools' in url and 'count=5' in url
            assert headers['X-Subscription-Token']=='secret' and redirects==0
            return page(body=json.dumps({'web':{'results':[{'url':'https://example.org','title':'A'}]}}).encode())
    assert BraveSearchProvider('secret',Transport()).search('London schools',5)[0].title=='A'
    with pytest.raises(RetrievalError,match='search_not_configured'):BraveSearchProvider('').search('q',5)
    assert 'secret' not in repr(Settings(brave_search_api_key='secret'))


def test_passages_exact_unicode_no_match_and_bad_encoding():
    extractor=LexicalPassageExtractor()
    source=extractor.snapshot('https://example.org',page(body=('Café London schools. '+ 'Other words. '*200).encode(),content_type='text/plain'))
    passages=extractor.passages(source,'London schools')
    assert len(passages)==1 and passages[0].char_end<=1000
    assert passages[0].text==source.text[passages[0].char_start:passages[0].char_end]
    assert extractor.passages(source,'bananas')==[]
    with pytest.raises(RetrievalError,match='unsupported_text_encoding'):
        extractor.snapshot('https://example.org',page(body=b'\xff'))


def test_pinned_connection_uses_numeric_address_and_tls_hostname(monkeypatch):
    import app.retrieval.fetcher as module
    calls=[]
    class Socket:
        def close(self):pass
    raw=Socket()
    monkeypatch.setattr(module.socket,'create_connection',lambda address,timeout:(calls.append(address) or raw))
    connection=PinnedHTTPSConnection('example.org','8.8.8.8',1)
    class TLS:
        def wrap_socket(self,sock,server_hostname):
            assert sock is raw and server_hostname=='example.org'
            return raw
    connection._context=TLS()
    connection.connect()
    assert calls==[('8.8.8.8',443)]


def test_query_bounds_duplicate_ids_and_source_length(setup):
    _,client,base,_,p,search,_=setup
    assert client.post(base+'/retrievals',json=body(setup,proposition_ids=[p['id'],p['id']])).status_code==422
    assert client.post(base+'/retrievals',json=body(setup,contexts={p['id']:'x'*301})).status_code==422
    extractor=LexicalPassageExtractor()
    with pytest.raises(RetrievalError,match='source_text_too_large'):
        extractor.snapshot('https://example.org',page(body=b'x'*200001,content_type='text/plain'))


def test_failed_fetch_not_replaced_by_search_snippet(setup):
    _,client,base,_,_,search,_=setup
    search.hits=[SearchHit(url='https://example.org/failed',snippet='London opened 2 schools')]
    run=client.post(base+'/retrievals',json=body(setup)).json()
    assert run['status']=='failed' and not run['results'][0]['passages'] and not run['sources']


def test_invalid_passage_adapter_is_rejected(setup):
    config,_,base,_,_,search,fetcher=setup
    class Invalid(LexicalPassageExtractor):
        def passages(self,source,query):
            result=super().passages(source,query)
            result[0].text='Invented evidence'
            return result
    client=TestClient(create_app(config,search_provider=search,source_fetcher=fetcher,passage_extractor=Invalid()))
    run=client.post(base+'/retrievals',json=body(setup)).json()
    assert not run['results'][0]['passages']
    assert run['results'][0]['attempts'][-1]['error_code']=='invalid_passage'
