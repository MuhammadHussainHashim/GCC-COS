"""Discover document candidates from an authorized HTML index; never infer reuse rights."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from .download import download

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


def candidates(html, page_url):
    parser = Links()
    parser.feed(html)
    urls = sorted({urljoin(page_url, link).split('#')[0] for link in parser.links})
    return [dict(url=url, format=urlsplit(url).path.rsplit('.', 1)[-1].lower(),
                 discovered_from=page_url, enabled=False, reuse_permitted=False,
                 license=None, license_url=None, connector_status='candidate_needs_permission_and_mapping')
            for url in urls if urlsplit(url).scheme == 'https'
            and urlsplit(url).path.rsplit('.', 1)[-1].lower() in {'csv', 'xlsx', 'json', 'pdf'}]


def discover(source, cache):
    # The index itself must have permission, not just the linked dataset.
    spec = source.get('discovery_document')
    if not spec:
        raise ValueError('Configure discovery_document with a permitted HTML URL, approved hosts and license first')
    path = download(dict(spec, format='html'), cache)
    return candidates(path.read_text(encoding='utf-8'), spec['url'])
