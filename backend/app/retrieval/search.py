import json
from typing import Protocol
from urllib.parse import urlencode
from app.models.retrieval import SearchHit
from app.retrieval.fetcher import PublicHTTPSFetcher, RetrievalError


class SearchProvider(Protocol):
    name: str
    def search(self, query: str, count: int) -> list[SearchHit]: ...


class BraveSearchProvider:
    name = 'brave-web-v1'

    def __init__(self, api_key: str, transport: PublicHTTPSFetcher | None = None):
        self._api_key = api_key
        self.transport = transport or PublicHTTPSFetcher(max_bytes=1_000_000)

    def search(self, query: str, count: int) -> list[SearchHit]:
        if not self._api_key:
            raise RetrievalError('search_not_configured')
        if len(query) > 600 or len(query.split()) > 75:
            raise RetrievalError('query_too_long')
        url = 'https://api.search.brave.com/res/v1/web/search?' + urlencode(
            {'q': query, 'count': min(count, 5), 'search_lang': 'en', 'spellcheck': 'false'})
        page = self.transport.request(url, {'application/json'},
            headers={'X-Subscription-Token': self._api_key, 'Accept': 'application/json'}, redirects=0)
        try:
            data = json.loads(page.body)
            items = data.get('web', {}).get('results', [])
            if not isinstance(items, list):
                raise ValueError()
            return [SearchHit(url=item['url'], title=item.get('title'), snippet=item.get('description'))
                    for item in items[:count]]
        except (ValueError, TypeError, KeyError, AttributeError):
            raise RetrievalError('invalid_search_response') from None
