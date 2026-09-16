"""Service-layer tests for ``SlackService``.

These exercise the security-critical seams directly (no HTTP): signed OAuth
state, token encrypt/decrypt, the token never leaking into public shapes, and
the ``ok: false`` -> raise path of the Slack transport. They use the real mocked
DynamoDB table via ``dynamodb_tables`` plus tiny fake KMS/Secrets clients.
"""

import base64
import json

import pytest

from services import SlackService, SlackError
from tests.conftest import SLACK_CONNECTIONS_TABLE, SLACK_NONCES_TABLE

USER = "user-1"


class FakeKMS:
    """Round-trips a token so decrypt(encrypt(x)) == x, marking the blob."""

    def encrypt(self, KeyId, Plaintext):
        assert KeyId == "key-123"
        return {"CiphertextBlob": b"kms:" + Plaintext}

    def decrypt(self, CiphertextBlob):
        assert CiphertextBlob.startswith(b"kms:")
        return {"Plaintext": CiphertextBlob[len(b"kms:"):]}


class FakeSecrets:
    def get_secret_value(self, SecretId):
        return {"SecretString": json.dumps({
            "client_secret": "shh-client-secret",
            "state_hmac": "shh-state-hmac",
        })}


@pytest.fixture
def slack_service(dynamodb_tables):
    """A non-local SlackService backed by mocked DynamoDB + fake AWS clients."""
    return SlackService(
        dynamodb_tables.Table(SLACK_CONNECTIONS_TABLE),
        FakeKMS(),
        FakeSecrets(),
        client_id="client-abc",
        redirect_uri="https://api.example.com/slack/oauth/callback",
        kms_key_id="key-123",
        secret_arn="arn:secret",
        nonces_table=dynamodb_tables.Table(SLACK_NONCES_TABLE),
        local_mode=False,
    )


# -- OAuth state ------------------------------------------------------------

def test_state_round_trip_recovers_user(slack_service):
    state = slack_service._mint_state(USER)
    assert slack_service._verify_state(state) == USER


def test_state_tampered_signature_rejected(slack_service):
    state = slack_service._mint_state(USER)
    raw, _sig = state.split(".", 1)
    forged = raw + "." + base64.urlsafe_b64encode(b"not-the-real-sig").decode()
    with pytest.raises(ValueError):
        slack_service._verify_state(forged)


def test_state_tampered_payload_rejected(slack_service):
    """Changing the bound user_id must break the signature."""
    state = slack_service._mint_state(USER)
    _raw, sig = state.split(".", 1)
    evil_payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": "attacker", "nonce": "x", "exp": 9999999999}).encode()
    ).decode()
    with pytest.raises(ValueError):
        slack_service._verify_state(evil_payload + "." + sig)


def test_state_expired_rejected(slack_service):
    slack_service.STATE_TTL_SECONDS = -10  # mint already-expired state
    state = slack_service._mint_state(USER)
    with pytest.raises(ValueError):
        slack_service._verify_state(state)


def test_state_malformed_rejected(slack_service):
    with pytest.raises(ValueError):
        slack_service._verify_state("garbage-no-dot")


def test_state_is_single_use(slack_service):
    """A valid state verifies once; a replay is rejected (nonce consumed)."""
    state = slack_service._mint_state(USER)
    assert slack_service._verify_state(state) == USER
    with pytest.raises(ValueError, match="already used"):
        slack_service._verify_state(state)


def test_state_single_use_no_op_without_nonce_store(dynamodb_tables):
    """Without a nonce store, verification still works (signature+TTL only)."""
    svc = SlackService(
        dynamodb_tables.Table(SLACK_CONNECTIONS_TABLE),
        FakeKMS(),
        FakeSecrets(),
        client_id="c",
        redirect_uri="https://x/cb",
        kms_key_id="key-123",
        secret_arn="arn:secret",
        nonces_table=None,
        local_mode=False,
    )
    state = svc._mint_state(USER)
    assert svc._verify_state(state) == USER
    # No store => replay is NOT caught (documented degradation).
    assert svc._verify_state(state) == USER


def test_authorize_url_carries_verifiable_state(slack_service):
    import urllib.parse

    url = slack_service.build_authorize_url(USER)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert qs["client_id"] == ["client-abc"]
    assert qs["scope"] == [SlackService.SCOPES]
    assert slack_service._verify_state(qs["state"][0]) == USER


# -- token encryption -------------------------------------------------------

def test_encrypt_decrypt_round_trip(slack_service):
    cipher = slack_service._encrypt("xoxb-super-secret")
    assert "xoxb-super-secret" not in cipher  # stored as opaque base64 ciphertext
    assert slack_service._decrypt(cipher) == "xoxb-super-secret"


# -- token never leaks ------------------------------------------------------

def test_list_connections_strips_token(slack_service):
    # Store a raw row that DOES contain a ciphertext, then read it back.
    slack_service.connections_table.put_item(Item={
        "user_id": USER,
        "connection_id": "c1",
        "team_id": "T1",
        "team_name": "Acme",
        "bot_token_cipher": slack_service._encrypt("xoxb-secret"),
        "bot_user_id": "U1",
        "scopes": SlackService.SCOPES,
    })
    conns = slack_service.list_connections(USER)
    assert len(conns) == 1
    assert "bot_token_cipher" not in conns[0]
    assert conns[0]["team_name"] == "Acme"


def test_get_token_missing_connection_raises(slack_service):
    with pytest.raises(ValueError):
        slack_service._get_token(USER, "does-not-exist")


# -- Slack transport --------------------------------------------------------

def test_slack_call_raises_on_not_ok(slack_service, monkeypatch):
    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"ok": False, "error": "channel_not_found"}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResp())
    with pytest.raises(SlackError) as exc:
        slack_service._slack_call("chat.postMessage", {"channel": "C1"}, token="t")
    assert "channel_not_found" in str(exc.value)


def test_dev_stub_rejected_when_not_local(slack_service):
    with pytest.raises(PermissionError):
        slack_service.dev_stub_connect(USER)


def test_authorize_url_requires_configuration(dynamodb_tables):
    """An empty client_id raises instead of building a broken Slack URL."""
    svc = SlackService(
        dynamodb_tables.Table(SLACK_CONNECTIONS_TABLE),
        FakeKMS(),
        FakeSecrets(),
        client_id="",  # unconfigured
        redirect_uri="https://x/cb",
        kms_key_id="key-123",
        secret_arn="arn:secret",
        nonces_table=dynamodb_tables.Table(SLACK_NONCES_TABLE),
        local_mode=False,
    )
    with pytest.raises(ValueError, match="not configured"):
        svc.build_authorize_url(USER)
