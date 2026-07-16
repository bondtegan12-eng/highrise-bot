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
        # Database removed - VIPs will reset if bot restarts
        self.vip_users = set() 
        
        self.mod_area = Position(x=7.0, y=9.25, z=23.51, facing="Front")
        self.vip_area = Position(x=15.01, y=9.25, z=17.99, facing="Front")
        self.crew_id = "69bf2d0c5654e2325acf9318"

    async def announce_loop(self):
        while True:
            try:
                await asyncio.sleep(120)
                await self.highrise.chat("welcome to bambs bday bash, vip is 500g to the bot please")
            except Exception:
                pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        asyncio.create_task(self.announce_loop())

    async def on_chat(self, user: User, message: str) -> None:
        message = message.lower().strip()

        if message == "!mod":
            privilege_response = await self.highrise.get_room_privilege(user.id)
            is_mod = privilege_response.content.moderator or privilege_response.content.owner
            
            is_crew = False
            try:
                user_info = await self.highrise.get_user_info(user.id)
                if getattr(user_info.content, 'crew_id', None) == self.crew_id:
                    is_crew = True
            except Exception:
                pass

            if is_mod or is_crew:
                await self.highrise.teleport_user(user.id, self.mod_area)
                await self.highrise.chat(f" Teleported {user.username} to the Moderator Lounge!")
            else:
                await self.highrise.chat(f" Sorry {user.username}, this command is strictly for Crew & Mods.")

        elif message == "!vip":
            if user.id in self.vip_users:
                await self.highrise.teleport_user(user.id, self.vip_area)
            else:
                await self.highrise.chat(f" You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.id and tip.type == "gold":
            if tip.amount >= 500:
                self.vip_users.add(sender.id)
                await self.highrise.send_whisper(sender.id, "🎉 Thank you for the tip! You have unlocked the !vip lounge for this session.")
                await self.highrise.chat(f"🌟 {sender.username} just tipped 500g and unlocked VIP status! 🌟")

if __name__ == "__main__":
    from highrise.__main__ import main, BotDefinition
    
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    
   room_id = os.environ.get("ROOM_ID")
   api_token = os.environ.get("API_TOKEN")

    
    if not room_id or not api_token:
        print("❌ Error: room_id or api_token environment variables missing in Render dashboard.")
        sys.exit(1)
        
    definitions = [BotDefinition(MyBot(), room_id, api_token)]
    loop.run_until_complete(main(definitions))

