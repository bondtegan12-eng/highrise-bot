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

        # --- 1. COORDINATE TRACKER COMMAND ---
        if message == "!coords":
            try:
                room_users = await self.highrise.get_room_users()
                # Updated SDK unpacking loop syntax
                for item in room_users.content:
                    room_user = item[0]
                    position = item[1]
                    if room_user.id == user.id:
                        await self.highrise.send_whisper(user.id, f"📍 Your Coords: x={position.x}, y={position.y}, z={position.z}")
                        return
            except Exception as e:
                print(f"Error finding coords: {e}")
                return

        # --- 2. MODERATOR LOUNGE COMMAND ---
        elif message == "!mod":
            try:
                # Custom Owner Override Bypass Block (Catches variations of your name)
                current_username = user.username.lower()
                if "bondtegan" in current_username:
                    await self.highrise.teleport_user(user.id, self.mod_area)
                    await self.highrise.chat(f"Teleported Owner {user.username} to the Moderator Lounge!")
                    return

                # Check for standard Room Mod permissions
                privilege_response = await self.highrise.get_room_privilege(user.id)
                is_mod = getattr(privilege_response, 'moderator', False) or getattr(privilege_response, 'is_owner', False)
                
                # Check if the player belongs to your specific crew ID
                is_crew = False
                try:
                    user_info = await self.highrise.get_user_info(user.id)
                    if getattr(user_info, 'crew_id', None) == self.crew_id:
                        is_crew = True
                except Exception as e:
                    print(f"Error checking user info on profile lookup: {e}")

                if is_mod or is_crew:
                    await self.highrise.teleport_user(user.id, self.mod_area)
                    await self.highrise.chat(f"Teleported {user.username} to the Moderator Lounge!")
                else:
                    await self.highrise.chat(f"Sorry {user.username}, this command is strictly for Crew & Mods.")
            except Exception as e:
                print(f"Error executing !mod command: {e}")
                await self.highrise.chat("⚠️ An error occurred validating permissions. Please try again.")

        # --- 3. VIP LOUNGE COMMAND ---
        elif message == "!vip":
            if user.id in self.vip_users:
                await self.highrise.teleport_user(user.id, self.vip_area)
            else:
                await self.highrise.chat(f"You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")

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
    loop.create_task(start_web_server())
    
    room = os.environ.get("room_id")
    token = os.environ.get("api_token")
        
    definitions = [BotDefinition(MyBot(), room, token)]
    loop.run_until_complete(main(definitions))
