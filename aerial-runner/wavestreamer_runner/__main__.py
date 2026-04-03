"""
CLI entry point for wavestreamer-runner.

Usage:
    wavestreamer-runner --api-key sk_... --agent-id abc123
    aerial --api-key sk_... --provider ollama --model llama3.1
"""

import argparse
import logging
import os
import sys

from .runner import AgentRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wavestreamer-runner",
        description="Autonomous prediction agent for waveStreamer. "
                    "Researches questions, reasons with your LLM, submits predictions with citations.",
    )
    parser.add_argument("--api-key", default=os.environ.get("WAVESTREAMER_API_KEY", ""),
                        help="Agent API key (sk_...). Can also set WAVESTREAMER_API_KEY env var.")
    parser.add_argument("--agent-id", default=os.environ.get("WAVESTREAMER_AGENT_ID", ""),
                        help="Agent ID. If not set, fetched from API using the key.")
    parser.add_argument("--base-url", default=os.environ.get("WAVESTREAMER_URL", "https://wavestreamer.ai"),
                        help="Platform URL (default: https://wavestreamer.ai)")
    parser.add_argument("--auth-token", default=os.environ.get("WAVESTREAMER_AUTH_TOKEN", ""),
                        help="Owner JWT token for heartbeat reporting (optional).")
    parser.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "ollama"),
                        choices=["ollama", "openrouter", "anthropic", "google"],
                        help="LLM provider (default: ollama)")
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", ""),
                        help="LLM model name (default: auto-detect from Ollama)")
    parser.add_argument("--llm-api-key", default=os.environ.get("LLM_API_KEY", ""),
                        help="LLM API key (for openrouter/anthropic/google)")
    parser.add_argument("--llm-base-url", default=os.environ.get("LLM_BASE_URL", ""),
                        help="Custom LLM base URL (for Ollama on non-default port)")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("INTERVAL_MINS", "240")),
                        help="Minutes between prediction cycles (default: 240)")
    parser.add_argument("--max-daily", type=int, default=int(os.environ.get("MAX_DAILY", "5")),
                        help="Max predictions per day (default: 5)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single prediction cycle then exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.api_key:
        print("Error: --api-key required (or set WAVESTREAMER_API_KEY env var)")
        print("\nGet an API key:")
        print("  pip install wavestreamer-sdk")
        print("  wavestreamer register my-agent --model llama3.1")
        sys.exit(1)

    # If no agent-id, fetch from API
    agent_id = args.agent_id
    if not agent_id:
        try:
            from wavestreamer import WaveStreamer
            ws = WaveStreamer(args.base_url, api_key=args.api_key)
            me = ws.me()
            agent_id = me.get("id", "")
            if not agent_id:
                print("Error: Could not determine agent ID from API key. Use --agent-id.")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Could not connect to API: {e}")
            print("Use --agent-id to specify manually, or check your --api-key.")
            sys.exit(1)

    runner = AgentRunner(
        api_key=args.api_key,
        agent_id=agent_id,
        base_url=args.base_url,
        auth_token=args.auth_token,
        interval_mins=args.interval,
        max_daily=args.max_daily,
        provider=args.provider,
        model=args.model,
        llm_api_key=args.llm_api_key,
        llm_base_url=args.llm_base_url,
    )

    if args.once:
        result = runner.run_once()
        if result["status"] == "error":
            sys.exit(1)
    else:
        runner.run()


if __name__ == "__main__":
    main()
