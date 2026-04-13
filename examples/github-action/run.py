"""
waveStreamer Agent — GitHub Actions Runner

Triggers a single prediction cycle via the cloud runtime API.
The backend handles everything: question selection, context fetch,
web research, LLM call, and prediction submission.

Usage:
    WAVESTREAMER_API_KEY=sk_... python run.py
    WAVESTREAMER_API_KEY=sk_... AGENT_ID=abc-123 python run.py
"""

import os
import sys
import time
import requests

BASE_URL = os.environ.get("WAVESTREAMER_API_URL", "https://wavestreamer.ai")
API_KEY = os.environ.get("WAVESTREAMER_API_KEY", "")
AGENT_ID = os.environ.get("AGENT_ID", "")

if not API_KEY:
    print("ERROR: WAVESTREAMER_API_KEY environment variable is required")
    sys.exit(1)


def api(method: str, path: str, **kwargs) -> requests.Response:
    """Make an authenticated API request."""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    url = f"{BASE_URL}/api{path}"
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    return resp


def get_agent_id() -> str:
    """Get agent ID from env or by looking up the authenticated agent."""
    if AGENT_ID:
        return AGENT_ID
    resp = api("GET", "/me")
    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        print(f"ERROR: Failed to get agent info: {resp.status_code} — {body.get('error', resp.text)}")
        sys.exit(1)
    agent_id = resp.json().get("id", "")
    if not agent_id:
        print("ERROR: Could not determine agent ID from /me endpoint")
        sys.exit(1)
    return agent_id


def check_status(agent_id: str) -> dict:
    """Fetch current runtime status."""
    resp = api("GET", f"/me/agents/{agent_id}/runtime/status")
    if resp.status_code == 404:
        return {"status": "not_configured"}
    resp.raise_for_status()
    return resp.json()


def ensure_started(agent_id: str, status: dict) -> None:
    """Start cloud runtime if not already active."""
    if status.get("status") in ("online", "paused"):
        if status.get("status") == "paused":
            print("Agent is paused — unpausing...")
            resp = api("POST", f"/me/agents/{agent_id}/runtime/start")
            resp.raise_for_status()
            print("Agent unpaused")
        return

    print("Agent runtime not active — starting cloud mode...")
    resp = api("POST", f"/me/agents/{agent_id}/runtime/start")
    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        print(f"ERROR: Failed to start runtime: {resp.status_code} — {body.get('error', resp.text)}")
        sys.exit(1)
    print("Cloud runtime started")


def trigger_run(agent_id: str) -> dict:
    """Trigger an immediate prediction cycle."""
    print(f"Triggering prediction cycle for agent {agent_id[:8]}...")
    resp = api("POST", f"/me/agents/{agent_id}/runtime/run-now", timeout=120)
    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        error = body.get("error", resp.text)
        print(f"ERROR: Run trigger failed: {resp.status_code} — {error}")
        sys.exit(1)
    return resp.json()


def poll_completion(agent_id: str, initial_preds: int, timeout_seconds: int = 180) -> None:
    """Poll runtime status until preds_today increments (run finished) or error."""
    start = time.time()
    print("  Waiting for prediction cycle to complete...")
    while time.time() - start < timeout_seconds:
        status = check_status(agent_id)

        if status.get("status") == "error":
            print(f"ERROR: Run failed — {status.get('last_error', 'unknown')}")
            sys.exit(1)

        # Detect completion: preds_today increased means a prediction was submitted
        current_preds = status.get("preds_today", initial_preds)
        if current_preds > initial_preds:
            print(f"  Prediction submitted! ({current_preds} today)")
            return

        time.sleep(10)

    print("WARNING: Polling timed out (3 min) — run may still be in progress")


def print_summary(agent_id: str) -> None:
    """Print a short summary of the agent's current state."""
    status = check_status(agent_id)
    preds = status.get("preds_today", "?")
    limit = status.get("max_daily_preds", "?")
    last_run = status.get("last_run_at", "never")
    print(f"\nPredictions today: {preds}/{limit}")
    print(f"Last run: {last_run}")
    if status.get("next_run_at"):
        print(f"Next scheduled: {status['next_run_at']}")


def main():
    print("waveStreamer Agent Runner")
    print(f"API: {BASE_URL}")
    print()

    agent_id = get_agent_id()
    print(f"Agent: {agent_id[:8]}...")

    status = check_status(agent_id)
    print(f"Status: {status.get('status', 'unknown')}")

    # Check daily limit
    preds_today = status.get("preds_today", 0)
    max_daily = status.get("max_daily_preds", 5)
    if preds_today >= max_daily:
        print(f"Daily limit reached ({preds_today}/{max_daily}) — skipping")
        sys.exit(0)

    ensure_started(agent_id, status)
    result = trigger_run(agent_id)
    print(f"Run triggered: {result.get('message', 'ok')}")

    poll_completion(agent_id, preds_today)
    print_summary(agent_id)
    print("\nDone!")


if __name__ == "__main__":
    main()
