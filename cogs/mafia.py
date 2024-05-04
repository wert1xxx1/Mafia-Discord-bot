import asyncio
import datetime

import disnake
from disnake.ext import commands
from disnake.ext.commands import InteractionBot

import config
from tools.tools import get_member_list_description
from ui.manage_ui import Manage
from ui.register_ui import Register


class MafiaCog(commands.Cog):
    def __init__(self, client):
        self.client: InteractionBot = client
        self.db = self.client.cluster.mafia_darkness
        self.collection = self.db.collection
        self.fol = self.db.fol

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: disnake.Role, after: disnake.Role):
        if await self.collection.find_one({"created_guild_id": after.guild.id}) is None:
            return
        if before.name in ["Ведущий", "Дон", "Мафия"]:
            await after.edit(name=before.name, reason="Названия данных ролей нельзя изменять!")

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
                await member.send(f"Вернитесь в войс <#{query['voice']}> "
                                  f"Если вы не вернетесь в войс в течении **3 минут** мафия завершится!")
            except disnake.Forbidden:
                pass
            await asyncio.sleep(30)
            if member.voice and member.voice.channel.id == query['voice']:
                return
            if await self.collection.find_one({"_id": query['_id']}) is None:
                return
            if await self.collection.find_one({"members_ids": member.id}) is None:
                return
            try:
                await member.send("Вы были **исключены**!")
            except disnake.Forbidden:
                pass
            members_ids = (await self.collection.find_one({"_id": query['_id']}))['members_ids']
            members = (await self.collection.find_one({"_id": query['_id']}))['members']
            try:
                members_ids.remove(member.id)
            except ValueError:
                pass
            member_role = None
            for doc in members:
                if doc['id'] == member.id:
                    member_role = doc['role']
                    members.remove(doc)
            if member_role:
                await self.collection.update_one({"_id": query['_id']}, {"$push": {
                    "other_roles": member_role
                }})
            guild_document = (await self.collection.find_one({"_id": query['_id']}))['created_guild']
            if guild_document:
                don = guild_document['don']
                if member.id in don:
                    don.remove(member.id)
                mafia = guild_document['mafia']
                if member.id in mafia:
                    mafia.remove(member.id)
            await self.collection.update_one({"_id": query['_id']}, {"$set": {
                "members": members,
                "members_ids": members_ids,
                "created_guild": guild_document
            }})

            msg = self.client.get_message(query['register_message'])
            if msg:
                emb = disnake.Embed(
                    color=0x2f3136, title='Записаться на мафию')
                emb.description = get_member_list_description(
                    members, f'<@{query["_id"]}>')
                emb.timestamp = datetime.datetime.now()
                try:
                    await msg.edit(embed=emb)
                except disnake.NotFound:
                    pass

            leader = await member.guild.getch_member(query['_id'])
            if leader:
                try:
                    _ = ""
                    if member_role:
                        _ = f" Роль участника которого вы выгнали: ``{member_role}``"
                    await leader.send(f"{member.mention} **исключен** из игры!{_}")
                except disnake.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        if await self.collection.find_one({"created_guild_id": member.guild.id}) is None:
            return
        guild_document = (await self.collection.find_one({"created_guild_id": member.guild.id}))
        if guild_document['_id'] == member.id:
            role = disnake.utils.get(member.guild.roles, name='Ведущий')
            await member.add_roles(role)
        elif member.id in guild_document['created_guild']['don']:
            role = disnake.utils.get(member.guild.roles, name='Дон')
            await member.add_roles(role)
        elif member.id in guild_document['created_guild']['mafia']:
            role = disnake.utils.get(member.guild.roles, name='Мафия')
            await member.add_roles(role)

    @commands.has_any_role(1234081338168967231)
    @commands.slash_command(name='mafia-create', description='Зарегистрировать мафию')
    async def create(self, inter: disnake.AppCmdInter):
        await inter.response.defer()
        _ = [doc async for doc in self.collection.find({})]
        if len(_) == 10:
            return await inter.send("Бот не может провести больше 10 мафий", ephemeral=True)
        if await self.collection.find_one({"_id": inter.author.id}):
            return await inter.send("Вы не можете запустить еще одну мафию!", ephemeral=True)
        try:
            await inter.author.edit(nick='!Ведущий')
        except disnake.Forbidden:
            await inter.author.send(
                "У бота не хватает прав вам изменить ник. Пожалуйста, измените ник на ``!Ведущий``")
        emb = disnake.Embed(title=f"**Создание мафии — {inter.author}**",
                            description=f"{inter.author.mention}, Каналы создаются",
                            color=0x2F3136)
        emb.set_thumbnail(url=inter.author.display_avatar.url)
        await inter.edit_original_response(embed=emb)
        pos_category = disnake.utils.get(
            inter.guild.categories, id=1235335802171424768).position
        category = await inter.guild.create_category(name=f'МАФИЯ・{inter.author}', position=pos_category)
        verify_role = disnake.utils.get(
            inter.guild.roles, id=config.BOT_INFO['VERIFY_ROLE_ID'])
        if verify_role:
            await category.set_permissions(verify_role, view_channel=True, connect=True, send_messages=True)
        mafia_ban = inter.guild.get_role(config.BOT_INFO['MAFIA_BAN_ROLE_ID'])
        if mafia_ban:
            await category.set_permissions(mafia_ban, connect=False, send_messages=False)
        unverify_role = disnake.utils.get(
            inter.guild.roles, id=config.BOT_INFO['UNVERIFY_ROLE_ID'])
        if unverify_role:
            await category.set_permissions(unverify_role, view_channel=False, connect=False, send_messages=False)
        manage_channel = await category.create_text_channel(name='🔴・управление')
        await manage_channel.set_permissions(inter.guild.default_role, send_messages=False,
                                             read_message_history=False,
                                             read_messages=False, view_channel=False)
        await manage_channel.set_permissions(inter.author, view_channel=True, send_messages=True,
                                             read_message_history=True, read_messages=True)
        information_channel = await category.create_text_channel(name='📑・информация')
        overwrites = information_channel.overwrites_for(
            inter.guild.default_role)
        overwrites.update(send_messages=False)
        await information_channel.set_permissions(inter.guild.default_role, overwrite=overwrites)
        embed = disnake.Embed(
            title='Описания игры',
            description=config.BOT_INFO['INFORMATION_DESCRIPTION'],
            color=0xff0000
        )

        embed.set_author(name='Мафия')
        await information_channel.send(embed=embed)
        registration_channel = await category.create_text_channel(name='🕵️・регистрация')
        overwrites = registration_channel.overwrites_for(
            inter.guild.default_role)
        overwrites.update(send_messages=False)
        await registration_channel.set_permissions(inter.guild.default_role, overwrite=overwrites)
        chat = await category.create_text_channel(name='💬・чат')
        overwrites = chat.overwrites_for(inter.guild.default_role)
        overwrites.update(send_messages=False)
        await chat.set_permissions(inter.guild.default_role, overwrite=overwrites)
        await chat.edit(slowmode_delay=2)
        voice = await category.create_voice_channel(name='🌃・стол')
        await voice.set_permissions(inter.guild.default_role, change_nickname=False)
        await voice.set_permissions(inter.author, connect=True, mute_members=True, deafen_members=True)
        await voice.edit(user_limit=11)
        emb = disnake.Embed(
            title='Управление мафией',
            description=f'**Информационный канал:** {information_channel.mention}\n**Голосовой канал:** {voice.mention}\n**Текстовый канал:** {chat.mention}',
            color=0x2F3136
        )
        emb.timestamp = datetime.datetime.now()
        emb.set_thumbnail(url=inter.author.display_avatar.url)
        emb.set_footer(text=f'Ведущий・{inter.author}',
                       icon_url=inter.guild.icon.url if inter.guild.icon else None)
        await manage_channel.send(embed=emb, view=Manage(self.collection, inter.author, category, chat, voice, self.fol))
        emb = disnake.Embed(color=0x2f3136, title='Запись на стол мафии')
        emb.description = f"""
            👥⠀**Список записавшихся**
            **01** - Пусто
            **02** - Пусто
            **03** - Пусто
            **04** - Пусто
            **05** - Пусто
            **06** - Пусто
            **07** - Пусто
            **08** - Пусто
            **09** - Пусто
            **10** - Пусто
            
            Записано игроков: **0**
            Ведущий стола: {inter.author.mention}
        """
        emb.timestamp = datetime.datetime.now()
        msg = await registration_channel.send(embed=emb, view=Register(self.collection, inter.author, category, voice,
                                                                       self.fol))
        if await self.collection.find_one({"_id": inter.author.id}):
            await self.collection.delete_one({"_id": inter.author.id})
        await self.collection.insert_one({
            "_id": inter.author.id,
            "started": False,
            "members": [],
            "members_ids": [],
            "created_guild_id": None,
            "created_guild": None,
            "voice": voice.id,
            "register_channel": registration_channel.id,
            "register_message": msg.id,
            "category": category.id,
            "mafia_channel": None,
            "other_roles": [],
            "mute": False,
            "deafen": False
        })
        emb = disnake.Embed(title=f"**Создание мафии — {inter.author}**",
                            description=f"{inter.author.mention},Ивент создан.",
                            color=0x2F3136)
        emb.set_thumbnail(url=inter.author.display_avatar.url)
        await inter.edit_original_response(embed=emb)


def setup(client: InteractionBot):
    client.add_cog(MafiaCog(client))