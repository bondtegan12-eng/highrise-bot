import asyncio
import os
from aiohttp import web
import psycopg2
from highrise import BaseBot, Position, CurrencyItem
from highrise.models import SessionMetadata, User

# --- DATABASE LOGIC ---
# Paste your Supabase URI string here
DB_URI = "YOUR_SUPABASE_CONNECTION_STRING_HERE"

def init_db():
    try:
        conn = psycopg2.connect(DB_URI)
        conn.close()
        print(" Successfully connected to Supabase database!")
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")

def load_vips():
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM vip_users;")
        vips = set(row[0] for row in cur.fetchall())
        cur.close()
        conn.close()
        return vips
    except Exception as e:
        print(f"Error loading VIPs: {e}")
        return set()

def save_vip(user_id):
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute("INSERT INTO vip_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving VIP: {e}")

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
        init_db()
        self.vip_users = load_vips()
        
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
            self.vip_users = load_vips()
            if user.id in self.vip_users:
                await self.highrise.teleport_user(user.id, self.vip_area)
            else:
                await self.highrise.chat(f" You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.id and tip.type == "gold":
            if tip.amount >= 500:
                save_vip(sender.id)
                self.vip_users.add(sender.id)
                await self.highrise.send_whisper(sender.id, "🎉 Thank you for the tip! You have permanently unlocked the !vip lounge.")
                await self.highrise.chat(f"🌟 {sender.username} just tipped 500g and unlocked VIP status! 🌟")

# Launcher block configures both Highrise and the WebServer to start up at the same time
if __name__ == "__main__":
    from highrise.__main__ import main
    
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    
    room_id = "64a094a74134ad0fd77b8734"
    api_token = "2c001cb06c4370e639be2d7a24cf4e7a0a860ef708d45d11cde0960633d0e8a6"
    bot_class = "MyBot"
    
    loop.run_until_complete(main(bot_class, room_id, api_token))


