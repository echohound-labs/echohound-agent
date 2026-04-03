import asyncio
import logging
from web3 import Web3
from telegram import Bot
from telegram.ext import Application

# ── CONFIG ──────────────────────────────────────────────
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
RPC_URL = "https://x1-rpc-url-here"  # X1 RPC endpoint

TOKEN_CONTRACT = "0xYOUR_TOKEN_ADDRESS"
PAIR_CONTRACT  = "0xYOUR_PAIR_ADDRESS"   # LP pair address

# Minimum buy in native token (XNT) to trigger alert
MIN_BUY = 0.01

# ── ABI (minimal swap event) ────────────────────────────
PAIR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "sender",     "type": "address"},
            {"indexed": False, "name": "amount0In",  "type": "uint256"},
            {"indexed": False, "name": "amount1In",  "type": "uint256"},
            {"indexed": False, "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "name": "amount1Out", "type": "uint256"},
            {"indexed": True,  "name": "to",         "type": "address"},
        ],
        "name": "Swap",
        "type": "event",
    }
]

# ── SETUP ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
w3   = Web3(Web3.HTTPProvider(RPC_URL))
pair = w3.eth.contract(address=Web3.to_checksum_address(PAIR_CONTRACT), abi=PAIR_ABI)
bot  = Bot(token=TELEGRAM_TOKEN)

# ── HELPERS ──────────────────────────────────────────────
def format_message(buyer: str, amount_in: float, amount_out: float) -> str:
    return (
        f"🟢 NEW BUY — X1 XEN\n\n"
        f"💰 Spent:    {amount_in:.4f} XNT\n"
        f"🪙 Received: {amount_out:,.0f} XEN\n"
        f"👤 Buyer:    {buyer[:6]}...{buyer[-4:]}\n\n"
        f"🔥 LFG! ❌"
    )

# ── MAIN LOOP ────────────────────────────────────────────
async def monitor_buys():
    last_block = w3.eth.block_number
    logging.info(f"Buy bot started at block {last_block}")

    while True:
        try:
            current_block = w3.eth.block_number

            if current_block > last_block:
                events = pair.events.Swap.get_logs(
                    fromBlock=last_block + 1,
                    toBlock=current_block
                )

                for event in events:
                    args = event["args"]

                    # Detect buys: XNT in → XEN out (adjust index for your pair)
                    amount_in  = w3.from_wei(args["amount0In"],  "ether")
                    amount_out = w3.from_wei(args["amount1Out"], "ether")

                    if float(amount_in) >= MIN_BUY and float(amount_out) > 0:
                        buyer = args["to"]
                        msg   = format_message(buyer, float(amount_in), float(amount_out))
                        await bot.send_message(chat_id=CHAT_ID, text=msg)
                        logging.info(f"Buy alert sent: {buyer}")

                last_block = current_block

        except Exception as e:
            logging.error(f"Error: {e}")

        await asyncio.sleep(3)  # poll every 3 seconds

# ── ENTRY ────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(monitor_buys())
