"""Assina payloads do webhook nos testes com o segredo configurado em platform_settings."""
import hmac
import hashlib
import json
import os
import requests

WEBHOOK_TEST_SECRET = "ravi-wh-test-9f8e7d6c5b4a39281706f5e4d3c2b1a0f8e7d6c5b4a3928170"

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


def signed_webhook_post(payload: dict):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(WEBHOOK_TEST_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return requests.post(f"{API}/webhooks/whatsapp", data=body, headers={
        "Content-Type": "application/json", "X-Hub-Signature-256": sig})
