from __future__ import annotations

import asyncio
import http.server
import json
import os
import sqlite3
import threading
import time
import sys
from pathlib import Path

from highrise import AnchorPosition, BaseBot, Position, User

# --- WEB SERVER WORKAROUND ---
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

threading.Thread(target=run_web_server, daemon=True).start()

# --- HIGHRISE HARDCODED CONFIGURATION ---
ROOM_ID = "64a094a74134ad0fd77b8734"
OWNER_USER_ID = "61ccb2a0fa2db3178100252c"
CREW_ID = "69bf2d0c5654e2325acf9318"  # Hardcoded Crew ID
VIP_TIP_THRESHOLD_GOLD = 500
TARGET_DJ_USERNAME = "nxmb_"
OWNER_USERNAME = "sexytegann"

ANNOUNCEMENT_MESSAGE = "WELCOME TO BAMBS BDAY BASH JOIN THE PARTY -- tip me 500g for VIP!"

TELEPORT_DESTINATIONS: dict[str, Position] = {
    "!vip": Position(x=17, y=9, z=18, facing="FrontRight"),
    "!mod": Position(x=6, y=9, z=29, facing="FrontRight"),
    "!dj": Position(x=16, y=0, z=24, facing="FrontRight"),
    "!f1": Position(x=10, y=0, z=10, facing="FrontRight"),
}

# --- RAILWAY PERSISTENT DATABASE FIX ---
if os.path.exists("/data"):
    DB_PATH = Path("/data/bot_data.db")
else:
    DB_PATH = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")) / "bot_data.db"

class TeleportBot(BaseBot):
    def __init__(self) -> None:
        super().__init__()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS tips (user_id TEXT PRIMARY KEY, gold_amount INTEGER DEFAULT 0)")
            cursor.execute("CREATE TABLE IF NOT EXISTS active_zones (user_id TEXT PRIMARY KEY, zone_command TEXT)")
            conn.commit()

    def _get_tip_total(self, user_id: str) -> int:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT gold_amount FROM tips WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                return row if row else 0
        except Exception:
            return 0

    def _add_tip(self, user_id: str, amount: int) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tips (user_id, gold_amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET gold_amount = gold_amount + ?", (user_id, amount, amount))
            conn.commit()
        return self._get_tip_total(user_id)

    def _save_user_zone(self, user_id: str, zone_command: str) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO active_zones (user_id, zone_command) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET zone_command = ?", (user_id, zone_command, zone_command))
            conn.commit()

    def _clear_user_zone(self, user_id: str) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_zones WHERE user_id = ?", (user_id,))
            conn.commit()

    def _get_user_zone(self, user_id: str) -> str | None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT zone_command FROM active_zones WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                return row if row else None
        except Exception:
            return None

    async def on_start(self, session_metadata) -> None:
        print(f"[TeleportBot] Connected to Highrise room {ROOM_ID}")
        asyncio.create_task(self._announcement_loop())

    async def _announcement_loop(self) -> None:
        while True:
            await asyncio.sleep(300)
            try:
                print("[Timer] Sending automated room announcement...")
                await self.highrise.chat(ANNOUNCEMENT_MESSAGE)
            except Exception as announce_err:
                print(f"[Timer Error] Could not send message: {announce_err}")

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        saved_zone = self._get_user_zone(user.id)
        if saved_zone in TELEPORT_DESTINATIONS:
            print(f"[Auto-Teleport] Returning {user.username} back to {saved_zone}")
            await self._delayed_teleport(user, TELEPORT_DESTINATIONS[saved_zone])
            return

        if user.username.lower() == TARGET_DJ_USERNAME.lower():
            await self._delayed_teleport(user, TELEPORT_DESTINATIONS["!dj"])
            return

        try:
            await self.highrise.chat(ANNOUNCEMENT_MESSAGE)
        except Exception as exc:
            print(f"[TeleportBot] Failed welcome message: {exc}")

    async def _delayed_teleport(self, user: User, position: Position, delay: float = 2.5) -> None:
        await asyncio.sleep(delay)
        try:
            await self.highrise.teleport(user.id, position)
        except Exception as exc:
            print(f"[TeleportBot] Teleport failed for {user.username}: {exc}")

    async def on_chat(self, user: User, message: str) -> None:
        try:
            command = message.strip().lower()
            is_owner = user.id == OWNER_USER_ID or user.username.lower() == OWNER_USERNAME.lower()
            
            if command == "!vip":
                total_tipped = self._get_tip_total(user.id)
                if total_tipped >= VIP_TIP_THRESHOLD_GOLD or is_owner:
                    await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!vip"])
                    self._save_user_zone(user.id, "!vip")
                else:
                    await self.highrise.chat(f"@{user.username}, you need to tip {VIP_TIP_THRESHOLD_GOLD}g total for VIP access. You have tipped {total_tipped}g.")

            elif command == "!mod":
                # Start with assumption that they are not crew
                is_crew_member = False
                
                # Check message payload as a quick first layer
                if hasattr(user, 'crew_id') and getattr(user, 'crew_id') == CREW_ID:
                    is_crew_member = True

                # Forced Deep Scan: Fetch the entire room cache to verify against live profile records
                if not is_crew_member and not is_owner:
                    try:
                        room_data = await self.highrise.get_room_users()
                        for room_user, pos in room_data.content:
                            if room_user.id == user.id:
                                # Check the server-side profile data for the crew tag
                                if hasattr(room_user, 'crew_id') and getattr(room_user, 'crew_id') == CREW_ID:
                                    is_crew_member = True
                                break
                    except Exception as scan_err:
                        print(f"[Scan Error] Failed room cache scan: {scan_err}")

                # Process the teleport if they match any permission layer
                if is_crew_member or is_owner:
                    await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!mod"])
                    self._save_user_zone(user.id, "!mod")
                else:
                    await self.highrise.chat(f"@{user.username}, only members of our Crew can use !mod.")

            elif command == "!dj":
                if user.username.lower() == TARGET_DJ_USERNAME.lower() or is_owner:
                    await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!dj"])
                else:
                    await self.highrise.chat(f"@{user.username}, only @{TARGET_DJ_USERNAME} can use !dj.")

            elif command == "!f1":
                await self.highrise.teleport(user.id, TELEPORT_DESTINATIONS["!f1"])
                self._clear_user_zone(user.id)
                    
        except Exception as chat_err:
            print(f"[Chat Handling Log] Caught entry: {chat_err}")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.highrise.my_id and isinstance(tip, CurrencyItem):
            new_total = self._add_tip(sender.id, tip.amount)
            if new_total >= VIP_TIP_THRESHOLD_GOLD:
                await self.highrise.chat(f"🎉 @{sender.username} has unlocked permanent VIP access by reaching {new_total}g tipped!")

# --- PERSISTENT LOOP RUNNER WITH FORCED CRASH FIX ---
def start_bot_loop():
    from highrise.__main__ import BotDefinition, main as run_bots
    
    definitions = [
        BotDefinition(
            bot_class_path="bot:TeleportBot",
            room_id=ROOM_ID,
            api_token="2c001cb06c4370e639be2d7a24cf4e7a0a8600ef708d45d11cde0960653d0e8a6"
        )
    ]
    
    try:
        print("[System] Launching bot connection framework...")
        asyncio.run(run_bots(definitions))
    except Exception as loop_err:
        print(f"[Connection Dropped] Room went empty: {loop_err}")
    
    sys.exit(1)

if __name__ == "__main__":
    start_bot_loop()





