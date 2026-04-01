"""
utils/webhook.py — Webhook mode for production deployments
Usage: python telegram_bot_v2.py --webhook --domain yourdomain.com --port 8443
Requires a public domain with SSL (nginx + certbot recommended).
"""
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="EchoHound Telegram Bot")
    parser.add_argument("--webhook", action="store_true", help="Run in webhook mode instead of polling")
    parser.add_argument("--domain", type=str, default="", help="Public domain for webhook e.g. yourdomain.com")
    parser.add_argument("--port", type=int, default=8443, help="Port for webhook server (default 8443)")
    parser.add_argument("--health-port", type=int, default=8080, help="Port for health endpoint (default 8080)")
    return parser.parse_args()
