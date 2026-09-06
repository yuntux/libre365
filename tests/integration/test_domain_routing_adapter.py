"""
Offline self-test for conftest.py's `DomainRoutingAdapter` - the mechanism
that lets this suite reach Caddy's domain-based virtual hosting
(sso.libre365.example.org, etc.) from outside the k3d cluster with no real
DNS for that domain (see dev-cluster/README.md's "Testing Keycloak
SSO/OIDC end-to-end").

Needs no live cluster, no Keycloak, nothing from `base_urls`: it proves the
adapter's request-rewriting logic against a throwaway local HTTP server
started in a background thread, so this test always runs (not marked
`sso`/`smoke`/`slow`) and gives real confidence in the mechanism
independent of whether a k3d cluster is available to exercise it
end-to-end.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from conftest import DomainRoutingAdapter


class _EchoHostHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"Host: {self.headers.get('Host')}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep pytest's output clean


@pytest.fixture(scope="module")
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHostHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)


def test_domain_routing_adapter_rewrites_matching_domain_but_keeps_host_header(echo_server):
    session = requests.Session()
    session.mount("http://", DomainRoutingAdapter("libre365.test", "127.0.0.1", echo_server.server_port))

    # ".test" is IANA/RFC 2606-reserved, guaranteed to never resolve on the
    # real internet - if the adapter failed to rewrite the connection
    # target, this request would fail with a DNS error instead of reaching
    # the local echo server at all.
    response = session.get("http://sso.libre365.test/")

    assert response.status_code == 200
    assert response.text == "Host: sso.libre365.test"


def test_domain_routing_adapter_leaves_non_matching_hosts_untouched(echo_server):
    session = requests.Session()
    session.mount("http://", DomainRoutingAdapter("libre365.test", "127.0.0.1", echo_server.server_port))

    # 127.0.0.1 does not end with ".libre365.test" - the adapter must not
    # rewrite this request at all; it already points at the echo server
    # directly, so the Host header it receives should be the untouched
    # original ("127.0.0.1:<port>").
    response = session.get(f"http://127.0.0.1:{echo_server.server_port}/")

    assert response.status_code == 200
    assert response.text == f"Host: 127.0.0.1:{echo_server.server_port}"


def test_domain_routing_adapter_matches_the_bare_suffix_too(echo_server):
    session = requests.Session()
    session.mount("http://", DomainRoutingAdapter("libre365.test", "127.0.0.1", echo_server.server_port))

    response = session.get("http://libre365.test/")

    assert response.status_code == 200
    assert response.text == "Host: libre365.test"
