"""
X1 Price Tool — EchoHound
==========================
Fetch XNT price and validator data from XDEX API.
Built for the X1 community.
"""

import requests
from typing import Dict, Any

XDEX_API_BASE = "https://api.xdex.com"
DEFAULT_TOKEN = "XNT"  # Native token


def get_xnt_price() -> Dict[str, Any]:
    """
    Get current XNT price and 24h stats from XDEX.
    
    Returns:
        Dict with price, volume, change_24h
    """
    try:
        # XDEX price endpoint
        url = f"{XDEX_API_BASE}/v1/tokens/{DEFAULT_TOKEN}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "token": DEFAULT_TOKEN,
            "price_usd": data.get("price_usd", "N/A"),
            "price_xlm": data.get("price_xlm", "N/A"),
            "volume_24h": data.get("volume_24h", "N/A"),
            "change_24h_percent": data.get("change_24h", "N/A"),
            "market_cap": data.get("market_cap", "N/A"),
            "last_updated": data.get("last_updated", "N/A"),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch XNT price: {str(e)}",
            "token": DEFAULT_TOKEN,
        }


def get_token_price(token_symbol: str) -> Dict[str, Any]:
    """
    Get price for any token on X1 via XDEX.
    
    Args:
        token_symbol: Token symbol (e.g., "XNT", "PROOF", "BTC")
    
    Returns:
        Dict with price data
    """
    try:
        url = f"{XDEX_API_BASE}/v1/tokens/{token_symbol.upper()}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "token": token_symbol.upper(),
            "price_usd": data.get("price_usd", "N/A"),
            "price_xlm": data.get("price_xlm", "N/A"),
            "volume_24h": data.get("volume_24h", "N/A"),
            "change_24h_percent": data.get("change_24h", "N/A"),
            "market_cap": data.get("market_cap", "N/A"),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch {token_symbol} price: {str(e)}",
            "token": token_symbol.upper(),
        }


def get_xnt_holders() -> Dict[str, Any]:
    """Get XNT holder stats."""
    try:
        url = f"{XDEX_API_BASE}/v1/tokens/{DEFAULT_TOKEN}/holders"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "token": DEFAULT_TOKEN,
            "holders": data.get("holders", "N/A"),
            "top_10_percent": data.get("top_10_percent", "N/A"),
            "top_50_percent": data.get("top_50_percent", "N/A"),
            "distribution_gini": data.get("distribution_gini", "N/A"),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch holder data: {str(e)}",
        }


def get_gas_stats() -> Dict[str, Any]:
    """Get X1 gas fee stats."""
    try:
        url = f"{XDEX_API_BASE}/v1/network/gas"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "safe_low": data.get("safe_low", "N/A"),
            "standard": data.get("standard", "N/A"),
            "fast": data.get("fast", "N/A"),
            "unit": "gwei",
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch gas stats: {str(e)}",
        }


def format_price_response(data: Dict[str, Any]) -> str:
    """Format price data for human-readable output."""
    if not data.get("success"):
        return f"❌ {data.get('error', 'Unknown error')}"
    
    token = data.get("token", "XNT")
    price = data.get("price_usd", "N/A")
    change = data.get("change_24h_percent", "N/A")
    volume = data.get("volume_24h", "N/A")
    
    emoji = "📈" if isinstance(change, (int, float)) and change >= 0 else "📉"
    change_str = f"+{change}%" if isinstance(change, (int, float)) and change >= 0 else f"{change}%"
    
    return (
        f"💰 *{token} Price*\n\n"
        f"Price: ${price}\n"
        f"24h Change: {emoji} {change_str}\n"
        f"24h Volume: ${volume}\n"
    )


# Tool definitions for agent integration
TOOL_DEFINITIONS = [
    {
        "name": "x1_get_price",
        "description": "Get the current price of XNT (X1 native token) in USD",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "x1_get_token_price",
        "description": "Get the current price of any token on X1 by symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "token_symbol": {
                    "type": "string",
                    "description": "Token symbol like XNT, PROOF, BTC, etc."
                }
            },
            "required": ["token_symbol"],
        },
    },
    {
        "name": "x1_get_holders",
        "description": "Get XNT holder statistics and distribution info",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "x1_get_gas",
        "description": "Get current X1 gas fee recommendations",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# Tool map for execution
TOOL_MAP = {
    "x1_get_price": get_xnt_price,
    "x1_get_token_price": get_token_price,
    "x1_get_holders": get_xnt_holders,
    "x1_get_gas": get_gas_stats,
}


if __name__ == "__main__":
    # Test the tools
    print("Testing X1 price tools...")
    print("\nXNT Price:")
    print(get_xnt_price())
    print("\nPROOF Price:")
    print(get_token_price("PROOF"))
    print("\nGas Stats:")
    print(get_gas_stats())
