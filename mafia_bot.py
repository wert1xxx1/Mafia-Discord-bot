import os

import disnake
from disnake.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

import config


class MafiaBot(commands.InteractionBot):
    def __init__(self):
        super().__init__(intents=disnake.Intents.all(),
                         test_guilds=[config.BOT_INFO['GUILD_ID']])
        mongodb_uri = config.BOT_INFO['MONGODB_URI'].replace("<username>", config.BOT_INFO['MONGODB_USER']).replace(
            '<password>', config.BOT_INFO['MONGODB_PASSWORD'])
        self.cluster = AsyncIOMotorClient(mongodb_uri)
        self.db = self.cluster.mafia_bot

    async def on_ready(self):
        guild = self.get_guild(475017106996330497)
        for filename in os.listdir(os.path.dirname(os.path.realpath(__file__)) + "/cogs"):
            if filename.endswith(".py"):
                self.load_extension(f"cogs.{filename[:-3]}")
        print(f"{self.user} is ready!")


bot = MafiaBot()
bot.run(config.BOT_INFO['TOKEN'])
