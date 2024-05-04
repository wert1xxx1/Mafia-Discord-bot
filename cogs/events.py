import datetime

import disnake
from disnake.ext import commands, tasks
from disnake.ext.commands import InteractionBot

import config
from tools.tools import edit_nicks


class Events(commands.Cog):
    def __init__(self, client):
        self.client: InteractionBot = client
        self.db = self.client.cluster.mafia_darkness
        self.collection = self.db.collection
        self.fol = self.db.fol
        self.guild = self.client.get_guild(config.BOT_INFO['GUILD_ID'])
        self.check_fols.start()

    @tasks.loop(seconds=15)
    async def check_fols(self):
        await self.client.wait_until_ready()
        async for doc in self.fol.find({}):
            if not doc['date_expired']:
                continue
            if datetime.datetime.now() < doc['date_expired']:
                continue
            await self.fol.update_one({"_id": doc['_id']}, {"$set": {"date_expired": None}})
            member = await self.guild.getch_member(doc['_id'])
            if not member:
                continue
            mafia_ban = self.guild.get_role(
                config.BOT_INFO['MAFIA_BAN_ROLE_ID'])
            if mafia_ban:
                await member.remove_roles(mafia_ban)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: disnake.Member, before: disnake.VoiceState,
                                    after: disnake.VoiceState):
        query = await self.collection.find_one({"members_ids": member.id})
        if not query:
            return
        after_channel_id = after.channel.id if after.channel else None
        before_channel_id = before.channel.id if before.channel else None
        if after_channel_id == before_channel_id:
            return
        if after_channel_id != query['voice'] and before_channel_id in [query['voice'], None]:
            try:
                await member.edit(mute=False, deafen=False)
            except disnake.HTTPException:
                pass
            if not member.voice:
                def check(member_voice: disnake.Member, _: disnake.VoiceState,
                          after_voice: disnake.VoiceState):
                    if not after_voice.channel:
                        return False
                    return member_voice == member and after_voice.channel \
                        and after_voice.channel.id != query['voice']

                await self.client.wait_for('voice_state_update', check=check)
                await member.edit(mute=False, deafen=False)
        elif after_channel_id == query['voice'] and before_channel_id != query['voice']:
            try:
                if query['mute']:
                    await member.edit(mute=True)
                if query['deafen']:
                    await member.edit(deafen=True)
                for doc in (await self.collection.find_one({"members_ids": member.id}))['members']:
                    if doc['id'] == member.id and doc['killed']:
                        await member.edit(mute=True, deafen=False)
            except disnake.HTTPException:
                pass
            await edit_nicks(member.guild, query['_id'], self.collection, self.fol)


def setup(client: InteractionBot):
    client.add_cog(Events(client))
