import asyncio
import datetime
import random
from random import choice
from typing import Optional

import disnake

import config
from tools.tools import edit_nicks, enumerate_members, get_member_list_description


class Manage(disnake.ui.View):
    def __init__(
            self,
            collection,
            leader: disnake.Member,
            category: disnake.CategoryChannel,
            chat: disnake.TextChannel,
            voice: disnake.VoiceChannel,
            fol
    ):
        super().__init__(timeout=None)
        self.voice = voice
        self.chat = chat
        self.collection = collection
        self.leader = leader
        self.category = category
        self.is_started = False
        self.guild: Optional[disnake.Guild] = None
        self.fol = fol

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        return interaction.user == self.leader

    @disnake.ui.button(label='Начать', style=disnake.ButtonStyle.green)
    async def start_btn(self, _: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        if self.is_started:
            return await inter.send("**Игра началась!**", ephemeral=True)
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if len(members) < config.BOT_INFO['COUNT_MEMBERS']:
            return await inter.send("**Не все участники собрались!**", ephemeral=True)
        mafia_roles = ['Мафия'] * config.BOT_INFO['MAFIA_COUNT']
        don_roles = ['Дон'] * config.BOT_INFO['DON_COUNT']
        commissar_roles = ['Комиссар'] * config.BOT_INFO['COMMISSAR_COUNT']
        doctor_roles = ['Доктор'] * config.BOT_INFO['DOCTOR_COUNT']
        civilian_roles = ['Мирный житель'] * config.BOT_INFO['CIVILIAN_COUNT']
        roles = mafia_roles + don_roles + commissar_roles + doctor_roles + civilian_roles
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if len(members) != len(roles):
            return print("Неправильно настроены роли в боте")
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "started": True
        }})
        msg = ""
        register_channel = inter.guild.get_channel((await self.collection.find_one(
            {"_id": self.leader.id}))['register_channel'])
        if register_channel:
            await register_channel.delete()
        created_guild = await inter.bot.create_guild(name=f'Мафия. Ведущий: {self.leader.id}')
        await self.collection.update_one({"_id": self.leader.id}, {
            "$set": {"created_guild_id": created_guild.id, "created_guild": {'don': [], 'mafia': []}}})
        self.guild = created_guild
        for channel in created_guild.channels:
            await channel.delete()
        created_channel = await created_guild.create_text_channel(name='чат')
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "mafia_channel": created_channel.id
        }})
        perms = disnake.Permissions(administrator=True)
        await created_guild.create_role(name='Ведущий', permissions=perms, hoist=True)
        await created_guild.create_role(name='Дон', hoist=True)
        await created_guild.create_role(name='Мафия', hoist=True)
        invite = await created_channel.create_invite()
        try:
            await self.leader.send(invite.url)
        except disnake.Forbidden:
            pass
        for member_id in members:
            try:
                member = await inter.guild.fetch_member(member_id['id'])
            except disnake.NotFound:
                continue
            role = choice(roles)
            roles.remove(role)
            member_id['role'] = role
            try:
                if role in ['Мафия', 'Дон']:
                    guild_document = (await self.collection.find_one({"_id": self.leader.id}))['created_guild']
                    if role == 'Дон':
                        guild_document['don'] += [member.id]
                    elif role == 'Мафия':
                        guild_document['mafia'] += [member.id]
                    await member.send(f"Ваша роль: ``{role}``\nСсылка на сервер: {invite.url}")
                    await self.collection.update_one({"_id": self.leader.id},
                                                     {"$set": {"created_guild": guild_document}})
                else:
                    await member.send(f"Ваша роль: ``{role}``")
            except disnake.Forbidden:
                msg += f"{member.mention} - ``{role}`` (Боту не удалось отправить ему сообщение)\n"
            else:
                msg += f"{member.mention} - ``{role}``\n"

        await self.collection.update_one({"_id": self.leader.id}, {"$set": {"members": members}})

        try:
            await self.leader.send(msg)
            await inter.send("Игра начата!", ephemeral=True)
        except disnake.Forbidden:
            await inter.send(msg, ephemeral=True)
        self.is_started = True
        await edit_nicks(inter.guild, self.leader, self.collection, self.fol)
        await inter.edit_original_response(
            view=ManageBoard(self.collection, self.category, self.leader, self.chat, self.voice, created_guild,
                             created_channel, self.fol))

    @disnake.ui.button(label='Изменить никнеймы участников', style=disnake.ButtonStyle.gray)
    async def edit_nicks(self, _: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        await edit_nicks(inter.guild, self.leader, self.collection, self.fol)
        await inter.send("Успешно изменены никнеймы!", ephemeral=True)

    @disnake.ui.button(label='Завершить', style=disnake.ButtonStyle.red)
    async def stop_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        await self.collection.delete_one({"_id": self.leader.id})
        if self.guild:
            await self.guild.delete()
        for channel in self.category.channels:
            await channel.delete(reason='Завершение мафии.')
        await self.category.delete(reason='Завершение мафии.')
        for member_document in members:
            member = await interaction.guild.getch_member(member_document['id'])
            if not member:
                continue
            try:
                await member.edit(mute=False, deafen=False)
            except disnake.HTTPException:
                def check(member_voice: disnake.Member, _, after: disnake.VoiceState):
                    return member_voice == member and after.channel

                await interaction.bot.wait_for('voice_state_update', check=check)
                await member.edit(mute=False, deafen=False)


class Select(disnake.ui.StringSelect):
    def __init__(self, parent: disnake.ui.View, options: dict):
        self.parent = parent
        options_select = []
        for option in options:
            options_select.append(disnake.SelectOption(
                label=option['name'], value=str(option['id'])))
        super().__init__(options=options_select,
                         placeholder="Выберите участника...", max_values=1, min_values=1)

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.defer()
        self.view.value = int(self.values[0])
        self.view.stop()


class SelectUi(disnake.ui.View):
    def __init__(self, author: disnake.Member, options):
        super().__init__(timeout=60)
        self.author = author
        self.value = None
        self.add_item(Select(self, options))

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        return self.author == interaction.author


class ManageBoard(disnake.ui.View):
    def __init__(
            self,
            collection,
            category: disnake.CategoryChannel,
            leader: disnake.Member,
            chat: disnake.TextChannel,
            voice: disnake.VoiceChannel,
            guild: disnake.Guild,
            mafia_channel: disnake.TextChannel,
            fol
    ):
        super().__init__(timeout=None)
        self.fol = fol
        self.mafia_channel = mafia_channel
        self.category = category
        self.guild = guild
        self.voice = voice
        self.chat = chat
        self.leader = leader
        self.collection = collection

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        return interaction.user == self.leader

    @disnake.ui.button(label='Изменить никнеймы участников', style=disnake.ButtonStyle.gray, row=1)
    async def edit_nicks(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        await edit_nicks(interaction.guild, self.leader, self.collection, self.fol)
        await interaction.followup.send("Успешно изменены никнеймы!", ephemeral=True)

    @disnake.ui.button(label='Зарегистрировать участника', style=disnake.ButtonStyle.gray, row=1)
    async def register_btn(self, _: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if len(members) == config.BOT_INFO['COUNT_MEMBERS']:
            return await inter.send("Лимит участников превышен!", ephemeral=True)
        await inter.send("Укажите участника.", ephemeral=True)
        try:
            def check(message: disnake.Message):
                return message.author == inter.author and message.channel == inter.channel \
                    and message.mentions and len(message.mentions) == 1

            msg: disnake.Message = await inter.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            return inter.send("Время вышло!", ephemeral=True)
        member = msg.mentions[0]
        members_ids = await self.collection.find_one({"members_ids": member.id})
        fol_doc = await self.fol.find_one({"_id": member.id})
        if fol_doc['date_expired']:
            return await inter.send("Данный пользователь имеет мафия бан!", ephemeral=True)
        if members_ids:
            return await inter.send("Данный пользователь уже участвует в игре!", ephemeral=True)
        if not member.voice or member.voice.channel != self.voice:
            return await inter.send(f"Данный пользователь не находится в войсе {self.voice.mention}!",
                                    ephemeral=True)
        random_role = None
        roles = (await self.collection.find_one({'_id': self.leader.id}))['other_roles']
        if roles:
            random_role = random.choice(roles)
            await self.collection.update_one({"_id": self.leader.id}, {"$pull": {
                "other_roles": random_role
            }})
            if random_role in ['Мафия', 'Дон']:
                invite = await self.guild.text_channels[0].create_invite()
                guild_document = (await self.collection.find_one({"_id": self.leader.id}))['created_guild']
                if random_role == 'Дон':
                    guild_document['don'] += [member.id]
                elif random_role == 'Мафия':
                    guild_document['mafia'] += [member.id]
                _ = ""
                try:
                    await member.send(f"Ваша роль: ``{random_role}``\nСсылка на сервер: {invite.url}")
                    _ += f"{member.mention} - ``{random_role}``"
                except disnake.Forbidden:
                    _ += f"{member.mention} - ``{random_role}`` (Боту не удалось отправить ему сообщение)"
                leader = await member.guild.getch_member(self.leader.id)
                if leader:
                    await leader.send(_)
                await self.collection.update_one({"_id": self.leader.id},
                                                 {"$set": {"created_guild": guild_document}})

        await self.collection.update_one({"_id": self.leader.id}, {"$push": {
            "members": {
                "id": member.id,
                "role": random_role,
                "killed": False
            },
            "members_ids": member.id
        }})
        await edit_nicks(inter.guild, self.leader, self.collection, self.fol)

    @disnake.ui.button(label='День', style=disnake.ButtonStyle.gray, row=1)
    async def day_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        role = disnake.utils.get(
            interaction.guild.roles, id=config.BOT_INFO['VERIFY_ROLE_ID'])
        target_1 = role if role else interaction.guild.default_role
        perms = self.chat.overwrites_for(target_1)
        perms.update(send_messages=True)
        await self.chat.set_permissions(target_1, overwrite=perms)
        target_2 = self.guild.default_role
        perms = self.mafia_channel.overwrites_for(target_2)
        perms.update(send_messages=False)
        await self.mafia_channel.set_permissions(target_2, overwrite=perms)
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        for member_doc in members:
            member = await interaction.guild.getch_member(member_doc['id'])
            if not member:
                continue
            if member_doc['killed']:
                continue
            if not member.voice:
                continue
            if member.voice.channel != self.voice:
                continue
            await member.edit(mute=False, deafen=False)
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "mute": False,
            "deafen": False
        }})

    @disnake.ui.button(label='Ночь', style=disnake.ButtonStyle.gray, row=1)
    async def night_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        role = disnake.utils.get(
            interaction.guild.roles, id=config.BOT_INFO['VERIFY_ROLE_ID'])
        target_1 = role if role else interaction.guild.default_role
        perms = self.chat.overwrites_for(target_1)
        perms.update(send_messages=True)
        await self.chat.set_permissions(target_1, overwrite=perms)
        target_2 = self.guild.default_role
        perms = self.mafia_channel.overwrites_for(target_2)
        perms.update(send_messages=True)
        await self.mafia_channel.set_permissions(target_2, overwrite=perms)
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        for member_doc in members:
            member = await interaction.guild.getch_member(member_doc['id'])
            if not member:
                continue
            if member_doc['killed']:
                continue
            if not member.voice:
                continue
            if member.voice.channel != self.voice:
                continue
            await member.edit(mute=True, deafen=True)
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "mute": True,
            "deafen": True
        }})

    @disnake.ui.button(label='Тех Пауза', style=disnake.ButtonStyle.blurple, row=2)
    async def pause_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        role = disnake.utils.get(
            interaction.guild.roles, id=config.BOT_INFO['VERIFY_ROLE_ID'])
        target_1 = role if role else interaction.guild.default_role
        perms = self.chat.overwrites_for(target_1)
        perms.update(send_messages=False)
        await self.chat.set_permissions(target_1, overwrite=perms)
        await self.chat.send("**Временная тех пауза!**")
        target_2 = self.guild.default_role
        perms = self.mafia_channel.overwrites_for(target_2)
        perms.update(send_messages=False)
        await self.mafia_channel.set_permissions(target_2, overwrite=perms)
        await self.mafia_channel.send("**Временная тех пауза!**")
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        for member_doc in members:
            member = await interaction.guild.getch_member(member_doc['id'])
            if not member:
                continue
            if not member.voice:
                continue
            if member.voice.channel != self.voice:
                continue
            await member.edit(mute=True, deafen=False)
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "mute": True,
            "deafen": False
        }})

    @disnake.ui.button(label='Снять тех паузу', style=disnake.ButtonStyle.blurple, row=2)
    async def un_pause_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        role = disnake.utils.get(
            interaction.guild.roles, id=config.BOT_INFO['VERIFY_ROLE_ID'])
        target_1 = role if role else interaction.guild.default_role
        perms = self.chat.overwrites_for(target_1)
        perms.update(send_messages=True)
        await self.chat.set_permissions(target_1, overwrite=perms)
        await self.chat.send("**Тех пауза закончилась!**")
        target_2 = self.guild.default_role
        perms = self.mafia_channel.overwrites_for(target_2)
        perms.update(send_messages=True)
        await self.mafia_channel.set_permissions(target_2, overwrite=perms)
        await self.mafia_channel.send("**Тех пауза закончилась!**")
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        for member_doc in members:
            member = await interaction.guild.getch_member(member_doc['id'])
            if not member:
                continue
            if not member.voice:
                continue
            if member.voice.channel != self.voice:
                continue
            await member.edit(mute=False, deafen=False)
        await self.collection.update_one({"_id": self.leader.id}, {"$set": {
            "mute": False,
            "deafen": False
        }})

    @disnake.ui.button(label='Показать роли участников', style=disnake.ButtonStyle.blurple, row=2)
    async def show_roles_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        embed = disnake.Embed(color=0x2f3136, title='Роли участников')
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.timestamp = datetime.datetime.now()
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if not members:
            embed.description = '**Участников нету!**'
        else:
            for nick, member_doc in enumerate_members(members):
                member = await interaction.guild.getch_member(member_doc['id'])
                if member is None:
                    continue
                embed.add_field(name=f"{member} ({nick})",
                                value=f'```{member_doc["role"] if member_doc["role"] else "Нету"}```')

        await interaction.send(embed=embed, ephemeral=True)

    @disnake.ui.button(label='Убить', style=disnake.ButtonStyle.red, row=2)
    async def kill_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        members = []
        embed = disnake.Embed(color=0x2f3136, title='Убить участника',
                              description='**Выберите участника**, которого нужно **убить**!')
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.timestamp = datetime.datetime.now()
        members_documents = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if members_documents:
            for doc in members_documents:
                if doc['killed']:
                    continue
                user = await interaction.guild.getch_member(doc['id'])
                if not user:
                    continue
                members.append({"id": user.id, "name": str(user)})
        if not members:
            embed.description = '**Нету участников**, которых можно **убить**!'
            return await interaction.send(embed=embed, ephemeral=True)
        view = SelectUi(interaction.author, members)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.value is None:
            embed.description = '**Время вышло**!'
            return await msg.edit(embed=embed, view=None)

        query = await self.collection.find_one({"members_ids": view.value})
        if not query:
            embed.description = 'Данный **участник**, уже **не участвует** в игре!'
            return await msg.edit(embed=embed, view=None)
        member = await interaction.guild.getch_member(view.value)
        if not member:
            embed.description = 'Данный **участник**, **не находится** на сервере!'
            return await msg.edit(embed=embed, view=None)
        members = query['members']
        for doc in members:
            if doc['id'] == member.id:
                doc['killed'] = True
        await self.collection.update_one({"_id": query['_id']}, {"$set": {
            "members": members
        }})
        await edit_nicks(interaction.guild, query['_id'], self.collection, self.fol)
        await self.chat.set_permissions(member, send_messages=False)
        embed.description = f'{interaction.author.mention}, Вы успешно **убили** участника {member.mention}!'
        await msg.edit(embed=embed, view=None)

    @disnake.ui.button(label='Поднять', style=disnake.ButtonStyle.red, row=2)
    async def un_kill_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        members = []
        embed = disnake.Embed(color=0x2f3136, title='Поднять участника',
                              description='**Выберите участника**, которого нужно **поднять**!')
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.timestamp = datetime.datetime.now()
        members_documents = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if members_documents:
            for doc in members_documents:
                if not doc['killed']:
                    continue
                user = await interaction.guild.getch_member(doc['id'])
                if not user:
                    continue
                members.append({"id": user.id, "name": str(user)})
        if not members:
            embed.description = '**Нету участников**, которых можно **поднять**!'
            return await interaction.send(embed=embed, ephemeral=True)

        view = SelectUi(interaction.author, members)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.value is None:
            embed.description = '**Время вышло**!'
            return await msg.edit(embed=embed, view=None)
        query = await self.collection.find_one({"members_ids": view.value})
        if not query:
            embed.description = 'Данный **участник**, уже **не участвует** в игре!'
            return await msg.edit(embed=embed, view=None)
        member = await interaction.guild.getch_member(view.value)
        if not member:
            embed.description = 'Данный **участник**, **не находится** на сервере!'
            return await msg.edit(embed=embed, view=None)
        members = query['members']
        for doc in members:
            if doc['id'] == member.id:
                doc['killed'] = False
        await self.collection.update_one({"_id": query['_id']}, {"$set": {
            "members": members
        }})
        await edit_nicks(interaction.guild, query['_id'], self.collection, self.fol)
        await self.chat.set_permissions(member, overwrite=None)
        if member.voice:
            await member.edit(mute=False)
        embed.description = f'{interaction.author.mention}, Вы успешно **подняли** участника {member.mention}!'
        await msg.edit(embed=embed, view=None)

    @disnake.ui.button(label='Выдать фол', style=disnake.ButtonStyle.blurple, row=4)
    async def fol_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        members = []
        embed = disnake.Embed(color=0x2f3136, title='Выдать фол',
                              description='**Выберите участника**, которому нужно **выдать фол**!')
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.timestamp = datetime.datetime.now()
        members_documents = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if members_documents:
            for doc in members_documents:
                user = await interaction.guild.getch_member(doc['id'])
                if not user:
                    continue
                members.append({"id": user.id, "name": str(user)})
        if not members:
            embed.description = '**Нету участников**, которым можно **выдать фол**!'
            return await interaction.send(embed=embed, ephemeral=True)
        view = SelectUi(interaction.author, members)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.value is None:
            embed.description = '**Время вышло**!'
            return await msg.edit(embed=embed, view=None)
        query = await self.collection.find_one({"members_ids": view.value})
        if not query:
            embed.description = 'Данный **участник**, уже **не участвует** в игре!'
            return await msg.edit(embed=embed, view=None)
        member = await interaction.guild.getch_member(view.value)
        if not member:
            embed.description = 'Данный **участник**, **не находится** на сервере!'
            return await msg.edit(embed=embed, view=None)
        if await self.fol.find_one({"_id": member.id}) is None:
            await self.fol.insert_one({"_id": member.id, "fol": 0, "date_expired": None})
        await self.fol.update_one({"_id": member.id}, {"$inc": {"fol": 1}})
        fol = (await self.fol.find_one({"_id": member.id}))['fol']
        if fol == config.BOT_INFO['COUNT_FOL_TO_MAFIA_BAN']:
            date_expired = datetime.datetime.now(
            ) + datetime.timedelta(days=config.BOT_INFO['FOL_DAYS'])
            await self.fol.update_one({"_id": member.id}, {"$set": {"fol": 0, "date_expired": date_expired}})
            mafia_ban = interaction.guild.get_role(
                config.BOT_INFO['MAFIA_BAN_ROLE_ID'])
            if mafia_ban:
                await member.add_roles(mafia_ban)
            try:
                await member.send(f"Вы были **исключены**, т.к вы получили "
                                  f"**{config.BOT_INFO['COUNT_FOL_TO_MAFIA_BAN']}** фола!")
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

            msg = interaction.bot.get_message(query['register_message'])
            if msg:
                emb = disnake.Embed(
                    color=0x2f3136, title='Запись на стол мафии')
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
                        _ = f" Его ролью была: ``{member_role}``"
                    await leader.send(f"{member.mention} **исключен** из игры!{_}\nОн получил "
                                      f"{config.BOT_INFO['COUNT_FOL_TO_MAFIA_BAN']} фола!")
                except disnake.Forbidden:
                    pass
        else:
            try:
                await member.send(f"Вы получили {fol} фол!")
            except disnake.Forbidden:
                pass
        embed.description = f'{interaction.author.mention}, Вы успешно **выдали фол** участнику {member.mention}!'
        await edit_nicks(interaction.guild, interaction.author, self.collection, self.fol)
        try:
            await msg.edit(embed=embed, view=None)
        except disnake.NotFound:
            pass

    @disnake.ui.button(label='Удалить фол', style=disnake.ButtonStyle.blurple, row=4)
    async def un_fol_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        members = []
        embed = disnake.Embed(color=0x2f3136, title='Выдать фол',
                              description='**Выберите участника**, которому нужно **убрать фол**!')
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.timestamp = datetime.datetime.now()
        members_documents = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if members_documents:
            for doc in members_documents:
                user = await interaction.guild.getch_member(doc['id'])
                if not user:
                    continue
                members.append({"id": user.id, "name": str(user)})
        if not members:
            embed.description = '**Нету участников**, которым можно **убрать фол**!'
            return await interaction.send(embed=embed)
        view = SelectUi(interaction.author, members)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.value is None:
            embed.description = '**Время вышло**!'
            return await msg.edit(embed=embed, view=None)
        query = await self.collection.find_one({"members_ids": view.value})
        if not query:
            embed.description = 'Данный **участник**, уже **не участвует** в игре!'
            return await msg.edit(embed=embed, view=None)
        member = await interaction.guild.getch_member(view.value)
        if not member:
            embed.description = 'Данный **участник**, **не находится** на сервере!'
            return await msg.edit(embed=embed, view=None)
        fol = (await self.fol.find_one({"_id": member.id}))['fol']
        if not fol:
            embed.description = f'Пользователь {member.mention}, ни разу **не получал фол**!'
            return await msg.edit(embed=embed, view=None)
        await self.fol.update_one({"_id": member.id}, {"$inc": {"fol": -1}})
        fol = (await self.fol.find_one({"_id": member.id}))['fol']
        if fol == 0:
            mafia_ban = interaction.guild.get_role(
                config.BOT_INFO['MAFIA_BAN_ROLE_ID'])
            if mafia_ban:
                await member.remove_roles(mafia_ban)
            await self.fol.update_one({"_id": member.id}, {"$set": {"date_expired": None}})
        embed.description = f'{interaction.author.mention}, Вы успешно **удалили фол** у пользователя {member.mention}!'
        await edit_nicks(interaction.guild, interaction.author, self.collection, self.fol)
        await msg.edit(embed=embed, view=None)

    @disnake.ui.button(label='Завершить', style=disnake.ButtonStyle.red, row=4)
    async def stop_btn(self, _: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        members = (await self.collection.find_one({"_id": self.leader.id}))['members']
        await self.collection.delete_one({"_id": self.leader.id})
        if self.guild:
            await self.guild.delete()
        for channel in self.category.channels:
            await channel.delete(reason='Завершение мафии.')
        await self.category.delete(reason='Завершение мафии.')
        for member_document in members:
            member = await interaction.guild.getch_member(member_document['id'])
            if not member:
                continue
            try:
                await member.edit(mute=False, deafen=False)
            except disnake.HTTPException:
                def check(member_voice: disnake.Member, _, after: disnake.VoiceState):
                    return member_voice == member and after.channel

                await interaction.bot.wait_for('voice_state_update', check=check)
                await member.edit(mute=False, deafen=False)
