from __future__ import annotations

import asyncio
import http.server
import json
import os
import sqlite3
import threading
from pathlib import Path

from highrise import AnchorPosition, BaseBot, Position, User
from highrise.__main__ import BotDefinition
from highrise.__main__ import main as run_bots

# --- WEB SERVER WORKAROUND FOR RENDER FREE ---
class KeepAliveServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = http.server.HTTPServer(("0.0.0.0", port), KeepAliveServer)
    print(f"[Web Server] Keeping bot awake on port {port}")
    server.serve_forever()

# Start the web server thread immediately so Render's health check passes
threading.Thread(target=run_web_server, daemon=True).start()

# --- HIGHRISE HARDCODED CONFIGURATION ---
ROOM_ID = "64a094a74134ad0fd77b8734"
API_TOKEN = "2c001cb06c4370e639be2d7a24cf4e7a0a860ef708d45d11cde0960653d0e8a6"
CREW_ID = "69bf2d0c5654e2325acf9318"
OWNER_USER_ID = "61ccb2a0fa2db3178100252c"
VIP_TIP_THRESHOLD_GOLD = 500
TARGET_DJ_USERNAME = "nxmb_"

TELEPORT_DESTINATIONS: dict[str, Position] = {
    "!vip": Position(x=17, y=9, z=18, facing="FrontRight"),
    "!mod": Position(x=6, y=9, z=29, facing="FrontRight"),
    "!dj": Position(x=16, y=0, z=24, facing="FrontRight"),
}

DB_PATH = Path("/tmp/bot_data.db") if os.path.exists("/tmp") else Path("bot_data.db")

class TeleportBot(BaseBot):
    def __init__(self) -> None:
        super().__init__()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS tips (user_id TEXT PRIMARY KEY, gold_amount INTEGER DEFAULT 0)")
            conn.commit()

    def _get_tip_total(self, user_id: str) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gold_amount FROM tips WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row if row else 0

    def _add_tip(self, user_id: str, amount: int) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tips (user_id, gold_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET gold_amount = gold_amount + ?", (user_id, amount, amount))
            conn.commit()
        return self._get_tip_total(user_id)

    async def on_start(self, session_metadata) -> None:
        print(f"[TeleportBot] Connected to Highrise room {ROOM_ID}")

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        try:
            await self.highrise.chat("WELCOME TO BAMBS BDAY BASH JOIN THE PARTY -- tip me 500g for VIP!")
        except Exception as exc:
            print(f"[TeleportBot] Failed welcome message: {exc}")

        # Auto-teleport targeted user nxmb_ to DJ area when they join
        if user.username.lower() == TARGET_DJ_USERNAME.lower():
            await self._delayed_teleport(user, TELEPORT_DESTINATIONS["!dj"])

    async def _delayed_teleport(self, user: User, position: Position, delay: float = 2.0) -> None:
        await asyncio.sleep(delay)
        try:
            await self.highrise.teleport(user.id, position)
        except Exception as exc:
            print(f"[TeleportBot] Teleport failed for {user.username}: {exc}")

    async def on_chat(self, user: User, message: str) -> None:
        command = message.strip().lower()
        permissions = await self.highrise.get_room_permissions(user.id)
        
        # Check if they are a Room Mod OR Bot Owner OR have the specified Crew ID
        is_room_mod = permissions.moderator or user.id == OWNER_USER_ID or (hasattr(user, 'crew_id') and getattr(user, 'crew_id') == CREW_ID)

        if command == "!vip":
            total_tipped = self._get_tip_total(user.id)
            if total_tipped >= VIP_TIP_THRESHOLD_GOLD or user.id == OWNER_USER_ID:
                await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!vip"])
            else:
                await self.highrise.chat(f"@{user.username}, you need to tip {VIP_TIP_THRESHOLD_GOLD}g total for VIP access. You have tipped {total_tipped}g.")

        elif command == "!mod":
            if is_room_mod:
                await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!mod"])
            else:
                await self.highrise.chat(f"@{user.username}, only Crew or Room Moderators can use !mod.")

        elif command == "!dj":
            if user.username.lower() == TARGET_DJ_USERNAME.lower() or user.id == OWNER_USER_ID:
                await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!dj"])
            else:
                await self.highrise.chat(f"@{user.username}, only @{TARGET_DJ_USERNAME} can use !dj.")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.highrise.my_id and isinstance(tip, CurrencyItem):
            new_total = self._add_tip(sender.id, tip.amount)
            if new_total >= VIP_TIP_THRESHOLD_GOLD:
                await self.highrise.chat(f"🎉 @{sender.username} has unlocked permanent VIP access by reaching {new_total}g tipped!")

# --- DIRECT EXECUTION ENTRY POINT ---
if __name__ == "__main__":
    definitions = [
        BotDefinition(
            bot_class_path="bot:TeleportBot",
            room_id=ROOM_ID,
            api_token=API_TOKEN
        )
    ]
    # Run the Highrise engine directly using our defined configuration lists
    asyncio.run(run_bots(definitions))





