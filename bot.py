import asyncio
import os
import sys
from aiohttp import web
from highrise import BaseBot, Position, CurrencyItem
from highrise.models import SessionMetadata, User

# --- KEEP-ALIVE WEB SERVER LOGIC ---
async def handle_ping(request):
    return web.Response(text="Bot is running and awake!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Keep-Alive server active on port {port}")

# --- CORE HIGHRISE BOT LOGIC ---
class MyBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.vip_users = set() 
        self.mod_area = Position(x=7, y=9, z=24, facing="Front")
        self.vip_area = Position(x=15, y=9, z=18, facing="Front")
        self.dj_area = Position(x=16, y=0, z=24, facing="FrontRight")
        self.crew_id = "69bf2d0c5654e2325acf9318"

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        asyncio.create_task(start_web_server())

    async def on_chat(self, user: User, message: str) -> None:
        # Standard bulletproof extraction matching Highrise API requirements
        username_lower = user.username.lower()
        msg_lower = message.lower().strip()

        # --- 1. EXCLUSIVE DJ BOOTH COMMAND ---
        if msg_lower == "!dj":
            if username_lower == "nxmb_" or username_lower == "sexytegann" or username_lower == "bondtegan":
                await self.highrise.teleport_user(user.id, self.dj_area)
                await self.highrise.chat(f"🎧 Welcome to the stage, DJ {user.username}!")
                return
            else:
                await self.highrise.chat(f"Sorry {user.username}, the DJ Booth is reserved exclusively for @nxmb_")
                return

        # --- 2. MODERATOR LOUNGE COMMAND ---
        elif msg_lower == "!mod":
            # Direct Owner check - skips all external lookups entirely
            if username_lower == "sexytegann" or username_lower == "bondtegan":
                await self.highrise.teleport_user(user.id, self.mod_area)
                await self.highrise.chat(f"Teleported Owner {user.username} to the Moderator Lounge!")
                return

            # Fallback check for Crew members
            try:
                user_info = await self.highrise.get_user_info(user.id)
                if hasattr(user_info, 'crew_id') and user_info.crew_id == self.crew_id:
                    await self.highrise.teleport_user(user.id, self.mod_area)
                    await self.highrise.chat(f"Teleported Crew Member {user.username} to the Moderator Lounge!")
                    return
            except Exception:
                pass

            await self.highrise.chat(f"Sorry {user.username}, this command is strictly for Crew & Mods.")
            return

        # --- 3. VIP LOUNGE COMMAND ---
        elif msg_lower == "!vip":
            if user.id in self.vip_users:
                await self.highrise.teleport_user(user.id, self.vip_area)
            else:
                await self.highrise.chat(f"You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")
            return

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.id and tip.type == "gold":
            if tip.amount >= 500:
                self.vip_users.add(sender.id)
                await self.highrise.send_whisper(sender.id, "🎉 Thank you for the tip! You have unlocked the !vip lounge for this session.")
                await self.highrise.chat(f"🌟 {sender.username} just tipped 500g and unlocked VIP status! 🌟")

if __name__ == "__main__":
    from highrise.__main__ import main, BotDefinition
    
    os.environ["api_token"] = "2c001cb06c4370e639be2d7a24cf4e7a0a860ef708d45d11cde0960653d0e8a6"
    os.environ["room_id"] = "64a094a74134ad0fd77b8734"
    
    loop = asyncio.get_event_loop()
    room = os.environ.get("room_id")
    token = os.environ.get("api_token")
        
    definitions = [BotDefinition(MyBot(), room, token)]
    loop.run_until_complete(main(definitions))
