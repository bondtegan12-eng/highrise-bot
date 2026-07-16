import asyncio
import os
import time
from aiohttp import web
from highrise import BaseBot, Position, CurrencyItem
from highrise.models import SessionMetadata, User

# --- FIX RENDER PORT BINDING ---
async def start_web_server():
    app = web.Application()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Read the exact port Render expects from your dashboard variable
    port = int(os.environ.get("PORT", 8080)) 
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Keep-Alive web system securely active on port {port}!")

# --- THE UN-CRASHABLE BOT LOGIC ---
class MyBot(BaseBot):
    def __init__(self):
        super().__init__()
        # Temporary memory to store who bought VIP during this session
        self.vip_users = set() 
        
        # Exact rounded integer coordinates to prevent Highrise server kicks
        self.mod_area = Position(x=7, y=9, z=24, facing="Front")
        self.dj_area = Position(x=16, y=0, z=24, facing="FrontRight")
        self.vip_area = Position(x=15, y=9, z=18, facing="Front")

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        pass  # Clean and empty to prevent double-starting errors

    async def on_chat(self, user: User, message: str) -> None:
        try:
            username_clean = str(user.username).lower().strip()
            msg_clean = message.lower().strip()

            # --- 1. MODERATOR LOUNGE COMMAND ---
            if msg_clean == "!mod":
                if username_clean == "sexytegann" or username_clean == "bondtegan":
                    await self.highrise.teleport(user.id, self.mod_area)
                    await self.highrise.chat(f"Teleported Owner {user.username} to the Moderator Lounge!")
                else:
                    await self.highrise.chat(f"Sorry {user.username}, this command is strictly for the Owner.")

            # --- 2. DJ STAGE COMMAND ---
            elif msg_clean == "!dj":
                if username_clean == "nxmb_" or username_clean == "sexytegann" or username_clean == "bondtegan":
                    await self.highrise.teleport(user.id, self.dj_area)
                    await self.highrise.chat(f" Welcome to the stage, DJ {user.username}!")
                else:
                    await self.highrise.chat(f"Sorry {user.username}, the DJ Booth is reserved exclusively for @nxmb_")

            # --- 3. VIP LOUNGE COMMAND ---
            elif msg_clean == "!vip":
                if user.id in self.vip_users or username_clean == "sexytegann" or username_clean == "bondtegan":
                    await self.highrise.teleport(user.id, self.vip_area)
                else:
                    await self.highrise.chat(f"You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")

        except Exception as e:
            print(f"Safety caught a chat processing error: {e}")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        try:
            if receiver.id == self.id and tip.type == "gold":
                if tip.amount >= 500:
                    self.vip_users.add(sender.id)
                    await self.highrise.send_whisper(sender.id, "🎉 Thank you for the tip! You have unlocked the !vip lounge for this session.")
                    await self.highrise.chat(f"🌟 {sender.username} just tipped 500g and unlocked VIP status! 🌟")
        except Exception as e:
            print(f"Safety caught a tip processing error: {e}")

if __name__ == "__main__":
    from highrise.__main__ import main, BotDefinition
    
    loop = asyncio.get_event_loop()
    
    # Start the web server first so Render detects the open port immediately
    loop.run_until_complete(start_web_server())
    
    room = os.environ.get("room_id")
    token = os.environ.get("api_token")
        
    definitions = [BotDefinition(MyBot(), room, token)]
        
    while True:
        try:
            loop.run_until_complete(main(definitions))
        except Exception as e:
            print(f"Connection dropped: {e}. Waiting 20 seconds to clear ghost bots safely...")
            time.sleep(20)
