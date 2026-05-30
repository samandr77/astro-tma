#!/usr/bin/env python3
"""Manage the Telegram bot webhook.

Reads TELEGRAM_BOT_TOKEN / TELEGRAM_WEBHOOK_URL / TELEGRAM_WEBHOOK_SECRET
from a .env in the current directory (or pass --env <path>).

Usage:
    python webhook.py info       # print getWebhookInfo + getMe
    python webhook.py set        # register/refresh webhook
    python webhook.py delete     # unregister webhook

Designed to be run from the project root (or /opt/astro-tma on the VPS).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def _load_env(path: str) -> dict[str, str]:
    if not os.path.isfile(path):
        sys.exit(f"env file not found: {path}")
    env: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _http(method: str, url: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def info(token: str) -> None:
    me = _http("GET", f"https://api.telegram.org/bot{token}/getMe")
    hook = _http("GET", f"https://api.telegram.org/bot{token}/getWebhookInfo")
    print("=== getMe ===")
    print(json.dumps(me, indent=2, ensure_ascii=False))
    print("\n=== getWebhookInfo ===")
    print(json.dumps(hook, indent=2, ensure_ascii=False))


def set_webhook(token: str, url: str, secret: str) -> None:
    payload = {
        "url": url,
        "secret_token": secret,
        "allowed_updates": ["message", "pre_checkout_query", "callback_query"],
        "drop_pending_updates": False,
    }
    result = _http("POST", f"https://api.telegram.org/bot{token}/setWebhook", payload)
    print("=== setWebhook ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nVerifying with getWebhookInfo...")
    info_check = _http("GET", f"https://api.telegram.org/bot{token}/getWebhookInfo")
    print(json.dumps(info_check, indent=2, ensure_ascii=False))


def delete_webhook(token: str) -> None:
    result = _http(
        "POST",
        f"https://api.telegram.org/bot{token}/deleteWebhook",
        {"drop_pending_updates": False},
    )
    print("=== deleteWebhook ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["info", "set", "delete"])
    parser.add_argument("--env", default=".env", help="Path to .env (default: ./.env)")
    args = parser.parse_args()

    env = _load_env(args.env)
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN missing from .env")

    if args.command == "info":
        info(token)
        return
    if args.command == "delete":
        delete_webhook(token)
        return
    # set
    url = env.get("TELEGRAM_WEBHOOK_URL")
    secret = env.get("TELEGRAM_WEBHOOK_SECRET")
    if not url or not secret:
        sys.exit("TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET required in .env")
    set_webhook(token, url, secret)


if __name__ == "__main__":
    main()
