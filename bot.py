import asyncio
import os
from highrise import BaseBot, Position, CurrencyItem
from highrise.models import SessionMetadata, User

class MyBot(BaseBot):
    def __init__(self):
        super().__init__()
        # Target paths for persistent file tracking
        self.filename = "vip_list.txt"
        self.vip_users = self.load_vips()
        
        # Room layouts and configurations
        self.mod_area = Position(x=7.0, y=9.25, z=23.51, facing="Front")
        self.vip_area = Position(x=15.01, y=9.25, z=17.99, facing="Front")
        self.crew_id = "69bf2d0c5654e2325acf9318"

    def load_vips(self):
        """Loads saved user IDs from text file into memory on startup"""
        if not os.path.exists(self.filename):
            return set()
        with open(self.filename, "r") as f:
            return set(line.strip() for line in f if line.strip())

    def save_vip(self, user_id):
        """Appends a new VIP user ID directly to the text file"""
        self.vip_users.add(user_id)
        with open(self.filename, "a") as f:
            f.write(f"{user_id}\n")

    async def announce_loop(self):
        """Background loop that automatically broadcasts messages every 2 minutes"""
        while True:
            try:
                await asyncio.sleep(120) # 120 seconds = 2 minutes
                await self.highrise.chat("welcome to bambs bday bash, vip is 500g to the bot please")
            except Exception:
                pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        """Triggers the announcement loop immediately when the bot boots up"""
        asyncio.create_task(self.announce_loop())

    async def on_chat(self, user: User, message: str) -> None:
        message = message.lower().strip()

        # --- MOD TELEPORT COMMAND ---
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

        # --- VIP TELEPORT COMMAND ---
        elif message == "!vip":
            if user.id in self.vip_users:
                await self.highrise.teleport_user(user.id, self.vip_area)
            else:
                await self.highrise.chat(f" You haven't unlocked VIP yet, {user.username}! Tip 500g to unlock.")

    # --- AUTOMATIC GOLD TIP LISTENER ---
    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem) -> None:
        if receiver.id == self.id and tip.type == "gold":
            if tip.amount >= 500:
                self.save_vip(sender.id) # Saves to the persistent text database file
                await self.highrise.send_whisper(sender.id, "🎉 Thank you for the tip! You have permanently unlocked the !vip lounge.")
                await self.highrise.chat(f"🌟 {sender.username} just tipped 500g and unlocked VIP status! 🌟")

