import asyncio
import os
from aiohttp import web
from highrise import BaseBot, Position, CurrencyItem
from highrise.models import SessionMetadata, User

# --- KEEP-ALIVE WEB SERVER LOGIC (AUTO-PORT SWITCHING) ---
async def start_web_server():
    app = web.Application()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Try the main port first, if it fails, fallback to a random open port
    try:
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"🌍 Keep-Alive server active on main port {port}")
    except OSError:
        # If port 10000 is already in use by a ghost bot, bind to an open port instead
        site = web.TCPSite(runner, '0.0.0.0', 0)
        await site.start()
        print("🌍 Keep-Alive server active on fallback port to bypass ghost bot clash!")


# --- CORE HIGHRISE BOT LOGIC ---
class MyBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.vip_users = set() 
        # Clean whole numbers to prevent coordinate glitches
        self.mod_area = Position(x=7, y=9, z=24, facing="Front")
        self.dj_area = Position(x=16, y=0, z=24, facing="FrontRight")

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        asyncio.create_task(start_web_server())

    async def on_chat(self, user: User, message: str) -> None:
        try:
            username_clean = str(user.username).lower().strip()
            msg_clean = message.lower().strip()

            # --- DJ TELEPORT (FIXED API COMMAND) ---
            if msg_clean == "!dj" and username_clean in ["nxmb_", "sexytegann", "bondtegan"]:
                await self.highrise.teleport(user.id, self.dj_area)
                await self.highrise.chat(f"🎧 Welcome to the stage, DJ {user.username}!")

            # --- MOD TELEPORT (FIXED API COMMAND) ---
            elif msg_clean == "!mod" and username_clean in ["sexytegann", "bondtegan"]:
                await self.highrise.teleport(user.id, self.mod_area)
                await self.highrise.chat(f"Teleported Owner {user.username} to the Moderator Lounge!")

        except Exception as e:
            print(f"Error handling chat command: {e}")

if __name__ == "__main__":
    from highrise.__main__ import main, BotDefinition
    
    os.environ["api_token"] = "2c001cb06c4370e639be2d7a24cf4e7a0a860ef708d45d11cde0960653d0e8a6"
    os.environ["room_id"] = "64a094a74134ad0fd77b8734"
    
    loop = asyncio.get_event_loop()
    definitions = [BotDefinition(MyBot(), os.environ["room_id"], os.environ["api_token"])]
    loop.run_until_complete(main(definitions))
