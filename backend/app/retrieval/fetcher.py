"""Public HTTPS only. Pin validated DNS addresses; retain hostname for TLS/SNI.

No environment proxies, cookies, JS, decompression or authenticated page access.
Socket operations have timeouts and reads check elapsed time. OS DNS resolution
itself has no portable hard deadline; a durable worker deadline is future work.
"""
from dataclasses import dataclass
import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit, urljoin


class RetrievalError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_url(url: str) -> str:
    if not url or len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url) or '\\' in url:
        raise RetrievalError('unsafe_url')
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme.lower() != 'https' or not host or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            raise ValueError()
        host = host.encode('idna').decode('ascii').lower().rstrip('.')
        if '%' in host or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (not address.is_global or address.is_multicast or address.is_reserved):
            raise ValueError()
        authority = f'[{host}]' if ':' in host else host
        # Preserve query semantics; do not merge potentially different resources.
        return urlunsplit(('https', authority, parsed.path or '/', parsed.query, ''))
    except (ValueError, UnicodeError):
        raise RetrievalError('unsafe_url') from None


def public_addresses(host: str) -> list[str]:
    try:
        addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
        if not addresses or any((not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).is_multicast or ipaddress.ip_address(a).is_reserved) for a in addresses):
            raise RetrievalError('unsafe_address')
        return addresses
    except (OSError, ValueError):
        raise RetrievalError('dns_failed') from None


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        # Numeric address means no second host lookup after validation.
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    content_type: str
    body: bytes
    raw_sha256: str


class SourceFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class PublicHTTPSFetcher:
    def __init__(self, timeout: float = 10, max_bytes: int = 2_000_000):
        self.timeout, self.max_bytes = timeout, max_bytes

    def fetch(self, url: str) -> FetchedPage:
        return self.request(url, {'text/html', 'text/plain', 'application/xhtml+xml'})

    def request(self, url: str, allowed_types: set[str], headers: dict[str, str] | None = None,
                redirects: int = 3) -> FetchedPage:
        started = time.monotonic()
        current = canonical_url(url)
        for hop in range(redirects + 1):
            parsed = urlsplit(current)
            addresses = public_addresses(parsed.hostname)
            remaining = self.timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise RetrievalError('fetch_timeout')
            connection = PinnedHTTPSConnection(parsed.hostname, addresses[0], remaining)
            try:
                request_headers = {'User-Agent': 'VerifiStream/0.1 (evidence retrieval)', 'Accept-Encoding': 'identity'}
                request_headers.update(headers or {})
                connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers=request_headers)
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if hop == redirects or not location:
                        raise RetrievalError('redirect_limit')
                    # Credentialed calls must never redirect.
                    if headers:
                        raise RetrievalError('redirect_blocked')
                    current = canonical_url(urljoin(current, location))
                    continue
                if response.status != 200:
                    raise RetrievalError(f'http_{response.status}')
                content_type = response.getheader('Content-Type', '').split(';')[0].strip().lower()
                if content_type not in allowed_types:
                    raise RetrievalError('unsupported_content_type')
                if response.getheader('Content-Encoding', 'identity').lower() not in ('identity', ''):
                    raise RetrievalError('unsupported_content_encoding')
                length = response.getheader('Content-Length')
                if length and int(length) > self.max_bytes:
                    raise RetrievalError('source_too_large')
                chunks, total = [], 0
                while True:
                    remaining = self.timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise RetrievalError('fetch_timeout')
                    if connection.sock is not None:
                        connection.sock.settimeout(remaining)
                    chunk = response.read1(min(65536, self.max_bytes + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise RetrievalError('source_too_large')
                body = b''.join(chunks)
                return FetchedPage(current, content_type, body, hashlib.sha256(body).hexdigest())
            except (TimeoutError, socket.timeout):
                raise RetrievalError('fetch_timeout') from None
            except (OSError, http.client.HTTPException, ValueError):
                raise RetrievalError('fetch_failed') from None
            finally:
                connection.close()
        raise RetrievalError('redirect_limit')
