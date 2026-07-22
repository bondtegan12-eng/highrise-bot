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
    # Render automatically sets a $PORT environment variable. We must bind to it.
    port = int(os.environ.get("PORT", 8080))
    server = http.server.HTTPServer(("0.0.0.0", port), KeepAliveServer)
    print(f"[Web Server] Keeping bot awake on port {port}")
    server.serve_forever()

# Start the web server thread immediately so Render's health check passes
threading.Thread(target=run_web_server, daemon=True).start()

# --- HIGHRISE CONFIGURATION ---
ROOM_ID = os.environ.get("HIGHRISE_ROOM_ID", "64a094a74134ad0fd77b8734")
CREW_ID = "69bf2d0c5654e2325acf9318"
OWNER_USER_ID = "61ccb2a0fa2db3178100252c"
F1_OWNER_USER_ID = "61ccb2a0fa2db3178100252c"
VIP_TIP_THRESHOLD_GOLD = 500

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
            cursor.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
            conn.commit()

    def _get_tip_total(self, user_id: str) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gold_amount FROM tips WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def _add_tip(self, user_id: str, amount: int) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tips (user_id, gold_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET gold_amount = gold_amount + ?", (user_id, amount, amount))
            conn.commit()
        return self._get_tip_total(user_id)

    def _get_state(self, key: str, default: str | None = None) -> str | None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def _set_state(self, key: str, value: str) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?", (key, value, value))
            conn.commit()

    async def on_start(self, session_metadata) -> None:
        print(f"[TeleportBot] Connected to Highrise as bot account ID={self.highrise.my_id}")

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        try:
            await self.highrise.chat("WELCOME TO BAMBS BDAY BASH JOIN THE PARTY -- tip me 500g for VIP!")
        except Exception as exc:
            print(f"[TeleportBot] Failed welcome message: {exc}")

        dj_id = self._get_state("dj_user_id")
        if user.id == dj_id:
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
        is_room_mod = permissions.moderator or user.id == OWNER_USER_ID

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
                await self.highrise.chat(f"@{user.username}, only Room Moderators can use !mod.")

        elif command == "!dj":
            dj_id = self._get_state("dj_user_id")
            if user.id == dj_id or user.id == OWNER_USER_ID:
                await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!dj"])
            else:
                await self.highrise.chat(f"@{user.username}, you are not the active DJ.")

        elif command.startswith("!setdj "):
            if user.id == OWNER_USER_ID:
                target_username = message.split(" ", 1)[1].replace("@", "").strip()
                room_users = await self.highrise.get_room_users()
                target_user = next((u for u in room_users.content if u.username.lower() == target_username.lower()), None)
                
                if target_user:
                    self._set_state("dj_user_id", target_user.id)
                    await self.highrise.chat(f"DJ successfully set to @{target_user.username}!")
                else:
                    await self.highrise.chat(f"Could not find user @{target_username} in the room.")
            else:
                await self.highrise.chat("Only the bot owner can set the DJ.")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.highrise.my_id and isinstance(tip, CurrencyItem):
            new_total = self._add_tip(sender.id, tip.amount)
            if new_total >= VIP_TIP_THRESHOLD_GOLD:
                await self.highrise.chat(f"🎉 @{sender.username} has unlocked permanent VIP access by reaching {new_total}g tipped!")


