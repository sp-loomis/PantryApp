"""End-to-end tests for the Slack integration endpoints.

Run through the real ``lambda_handler`` (``api`` fixture), which sets
``ENVIRONMENT=local`` so SlackService uses no-network local mode: the dev-stub
connect route is enabled and Slack calls return canned responses. This traces
the whole connect -> list -> channels -> test -> disconnect flow without AWS or
Slack.
"""

import urllib.parse


def _connect(api):
    """Create a connection via the local dev-stub route; return its public dict."""
    resp = api.call("POST", "/slack/connections/dev-stub", body={"team_name": "Acme"})
    assert resp.status_code == 201
    return resp.body["connection"]


def test_dev_stub_connect_returns_public_shape(api):
    conn = _connect(api)
    assert conn["team_name"] == "Acme"
    assert conn["connection_id"]
    # The token must never appear in an API response.
    assert "bot_token_cipher" not in conn


def test_list_connections(api):
    _connect(api)
    resp = api.call("GET", "/slack/connections")
    assert resp.status_code == 200
    conns = resp.body["connections"]
    assert len(conns) == 1
    assert "bot_token_cipher" not in conns[0]


def test_list_channels(api):
    conn = _connect(api)
    resp = api.call("GET", f"/slack/connections/{conn['connection_id']}/channels")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.body["channels"]}
    assert {"general", "random"} <= names


def test_channels_unknown_connection_404(api):
    resp = api.call("GET", "/slack/connections/nope/channels")
    assert resp.status_code == 404


def test_test_endpoint_posts(api):
    conn = _connect(api)
    resp = api.call(
        "POST", f"/slack/connections/{conn['connection_id']}/test",
        body={"channel_id": "C_LOCAL_GENERAL"},
    )
    assert resp.status_code == 200
    assert resp.body["ok"] is True


def test_test_endpoint_requires_channel(api):
    conn = _connect(api)
    resp = api.call("POST", f"/slack/connections/{conn['connection_id']}/test", body={})
    assert resp.status_code == 400


def test_disconnect_then_gone(api):
    conn = _connect(api)
    cid = conn["connection_id"]
    resp = api.call("DELETE", f"/slack/connections/{cid}")
    assert resp.status_code == 200
    assert resp.body["deleted"] is True

    resp = api.call("GET", "/slack/connections")
    assert resp.body["connections"] == []


def test_disconnect_unknown_404(api):
    resp = api.call("DELETE", "/slack/connections/nope")
    assert resp.status_code == 404


def test_oauth_start_returns_url(api):
    resp = api.call("GET", "/slack/oauth/start")
    assert resp.status_code == 200
    assert resp.body["authorize_url"].startswith("https://slack.com/oauth/v2/authorize")


def test_oauth_callback_happy_redirects_and_stores(api):
    # Mint a real signed state by starting the flow, then complete it.
    start = api.call("GET", "/slack/oauth/start")
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.body["authorize_url"]).query
    )["state"][0]

    resp = api.call("GET", "/slack/oauth/callback", query={"code": "abc", "state": state})
    assert resp.status_code == 302

    # The canned oauth exchange created a stored connection.
    listing = api.call("GET", "/slack/connections")
    assert len(listing.body["connections"]) == 1


def test_oauth_callback_bad_state_redirects_error(api):
    resp = api.call("GET", "/slack/oauth/callback", query={"code": "abc", "state": "bad"})
    assert resp.status_code == 302
    # No connection is created on a rejected state.
    listing = api.call("GET", "/slack/connections")
    assert listing.body["connections"] == []


def test_oauth_callback_state_is_single_use(api):
    """Replaying a once-used state creates no second connection (nonce consumed)."""
    start = api.call("GET", "/slack/oauth/start")
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.body["authorize_url"]).query
    )["state"][0]

    first = api.call("GET", "/slack/oauth/callback", query={"code": "abc", "state": state})
    assert first.status_code == 302

    # Replay the exact same state — rejected, so still exactly one connection.
    replay = api.call("GET", "/slack/oauth/callback", query={"code": "abc", "state": state})
    assert replay.status_code == 302
    listing = api.call("GET", "/slack/connections")
    assert len(listing.body["connections"]) == 1
