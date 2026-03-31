"""
X1 Price Tool for EchoHound
Fetches XNT price and market data from X1 ecosystem sources.
"""

import os
import json
import requests
from typing import Optional, Dict
from datetime import datetime, timedelta


class X1PriceTool:
    """
    Fetches XNT price data from various X1 sources.
    Uses caching to avoid rate limits.
    """

    CACHE_DURATION = 60  # seconds

    def __init__(self, cache_dir: str = "./memory/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "x1_price.json")

    def _load_cache(self) -> Optional[dict]:
        """Load cached price data if fresh."""
        if not os.path.exists(self.cache_file):
            return None

        with open(self.cache_file, "r") as f:
            data = json.load(f)

        cached_time = datetime.fromisoformat(data["timestamp"])
        if datetime.now() - cached_time < timedelta(seconds=self.CACHE_DURATION):
            return data

        return None

    def _save_cache(self, data: dict):
        """Save price data to cache."""
        data["timestamp"] = datetime.now().isoformat()
        with open(self.cache_file, "w") as f:
            json.dump(data, f)

    def get_xnt_price(self) -> Dict:
        """
        Fetch current XNT price.
        Returns dict with price, change, and source.
        """
        # Check cache first
        cached = self._load_cache()
        if cached:
            return {
                "price": cached.get("price"),
                "change_24h": cached.get("change_24h"),
                "source": cached.get("source", "cached"),
                "timestamp": cached.get("timestamp"),
                "cached": True,
            }

        # Try multiple sources
        sources = [
            self._fetch_from_xdex,
            self._fetch_from_dexscreener,
            self._fetch_from_coingecko,
        ]

        for source_fn in sources:
            try:
                result = source_fn()
                if result and result.get("price"):
                    self._save_cache(result)
                    result["cached"] = False
                    return result
            except Exception as e:
                continue

        # All sources failed
        return {
            "price": None,
            "error": "Unable to fetch XNT price from any source",
            "timestamp": datetime.now().isoformat(),
        }

    def _fetch_from_xdex(self) -> Optional[dict]:
        """Fetch from XDEX API."""
        try:
            url = "https://xdex.solanatracker.io/tokens/X1NT..."  # Replace with actual XNT address
            response = requests.get(url, timeout=5)
            data = response.json()

            return {
                "price": data.get("price"),
                "change_24h": data.get("priceChange", {}).get("h24"),
                "volume_24h": data.get("volume", {}).get("h24"),
                "source": "xdex",
            }
        except:
            return None

    def _fetch_from_dexscreener(self) -> Optional[dict]:
        """Fetch from DexScreener."""
        try:
            # XNT token address on X1
            token_address = "X1NT..."  # Replace with actual
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = requests.get(url, timeout=5)
            data = response.json()

            pairs = data.get("pairs", [])
            if pairs:
                top_pair = pairs[0]
                return {
                    "price": float(top_pair.get("priceUsd", 0)),
                    "change_24h": top_pair.get("priceChange", {}).get("h24"),
                    "volume_24h": top_pair.get("volume", {}).get("h24"),
                    "source": "dexscreener",
                }
        except:
            return None

        return None

    def _fetch_from_coingecko(self) -> Optional[dict]:
        """Fetch from CoinGecko."""
        try:
            # XNT ID on CoinGecko (if listed)
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "x1-network-token",  # Replace with actual ID
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            token_data = data.get("x1-network-token", {})
            return {
                "price": token_data.get("usd"),
                "change_24h": token_data.get("usd_24h_change"),
                "source": "coingecko",
            }
        except:
            return None

    def format_price(self, data: dict) -> str:
        """Format price data for display."""
        if data.get("error"):
            return f"❌ {data['error']}"

        price = data.get("price")
        change = data.get("change_24h")

        if price is None:
            return "❌ Price unavailable"

        # Format price with appropriate decimals
        if price < 0.01:
            price_str = f"${price:.6f}"
        elif price < 1:
            price_str = f"${price:.4f}"
        else:
            price_str = f"${price:.2f}"

        # Format change with emoji
        if change is not None:
            emoji = "🟢" if change >= 0 else "🔴"
            change_str = f"{emoji} {change:+.2f}% (24h)"
        else:
            change_str = "📊 24h change unavailable"

        source = data.get("source", "unknown")
        cached = " (cached)" if data.get("cached") else ""

        return f"💰 XNT Price: {price_str}\n{change_str}\n📡 Source: {source}{cached}"


# Convenience function
def get_xnt_price() -> str:
    """Quick function to get formatted XNT price."""
    tool = X1PriceTool()
    data = tool.get_xnt_price()
    return tool.format_price(data)
