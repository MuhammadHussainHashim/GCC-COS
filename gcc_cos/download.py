"""Fail-closed robots/permission checks, bounded downloads, verified HTTPS."""
import hashlib
import time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import requests

AGENT = "GCC-COS/0.1"
MAX_BYTES = 30 * 1024 * 1024


class DownloadBlocked(ValueError):
    def __init__(self, message, error_code, http_status, next_action):
        super().__init__(message)
        self.error_code, self.http_status, self.next_action = error_code, http_status, next_action


def failure_info(exc):
    return dict(error_code=getattr(exc, 'error_code', type(exc).__name__),
                http_status=getattr(exc, 'http_status', None),
                next_action=getattr(exc, 'next_action', 'Inspect the source error; correct prerequisites before retrying'))


def permitted(source):
    if source.get("reuse_permitted") is not True or not source.get("license") or not source.get("license_url"):
        raise ValueError("Download/import blocked: documented reuse permission and license required")


def download(source, cache):
    permitted(source)
    url = source["url"]
    hosts = source.get("allowed_hosts", [])
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    for _ in range(6):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
            raise ValueError("HTTPS URL host is not approved in source registry")
        robots_url = f"https://{parsed.netloc}/robots.txt"
        robots = session.get(robots_url, timeout=30, allow_redirects=False)
        delay = max(1.0, float(source.get("min_interval_seconds", 1)))
        if robots.status_code == 200:
            policy = RobotFileParser()
            policy.parse(robots.text.splitlines())
            if not policy.can_fetch(AGENT, url):
                raise ValueError("robots.txt disallows download")
            delay = max(delay, policy.crawl_delay(AGENT) or 0)
            rate = policy.request_rate(AGENT)
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
        elif robots.status_code not in (404, 410):
            raise DownloadBlocked(f"Cannot establish robots permission: HTTP {robots.status_code}",
                                  'robots_access_unavailable', robots.status_code,
                                  'Stop collection. Review robots/publisher/network permission; do not bypass or repeatedly retry.')
        time.sleep(delay)
        with session.get(url, timeout=(15, 90), stream=True, allow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            if response.status_code in (401, 403, 429):
                raise DownloadBlocked(f"Source access stopped: HTTP {response.status_code}",
                                      'access_denied' if response.status_code in (401, 403) else 'rate_limited', response.status_code,
                                      'Stop this source. Use a documented permitted API/download or obtain access; no host/header/proxy bypass and no automatic retry.')
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError("Document exceeds 30 MiB limit")
        digest = hashlib.sha256(content).hexdigest()
        expected = source.get("sha256")
        if expected and digest != expected:
            raise ValueError("Source checksum mismatch")
        path = Path(cache) / (digest + "." + source["format"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path
    raise ValueError("Too many redirects")
