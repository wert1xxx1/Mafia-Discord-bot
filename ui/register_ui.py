import datetime

import disnake

import config
from tools.tools import enumerate_members, get_member_list_description


class Register(disnake.ui.View):
    def __init__(
            self,
            collection,
            leader: disnake.Member,
            category: disnake.CategoryChannel,
            voice: disnake.VoiceChannel,
            fol
    ):
        super().__init__(timeout=None)
        self.fol = fol
        self.category = category
        self.collection = collection
        self.voice = voice
        self.leader = leader

    @disnake.ui.button(label='Записаться на игру', style=disnake.ButtonStyle.green)
    async def register_btn(self, _: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.defer()
        fol = await self.fol.find_one({"_id": inter.author.id})
        if fol and fol['date_expired']:
            emb = disnake.Embed(color=0x2f3136, title='Ошибка')
            emb.description = f'{inter.author.mention}, Вы **не можете** зарегистрироваться, **потому что** у Вас ' \
                              f'**мафия бан**! '
            emb.set_thumbnail(url=inter.author.display_avatar.url)
            return await inter.send(embed=emb, ephemeral=True)
        members: list = (await self.collection.find_one({"_id": self.leader.id}))['members']
        for document in members:
            if document['id'] == inter.author.id:
                emb = disnake.Embed(color=0x2f3136, title='Ошибка')
                emb.description = f'{inter.author.mention}, **Вы** уже **зарегистрированы**!'
                emb.set_thumbnail(url=inter.author.display_avatar.url)
                return await inter.send(embed=emb, ephemeral=True)
        if not inter.author.voice or inter.author.voice.channel != self.voice:
            emb = disnake.Embed(color=0x2f3136, title='Ошибка')
            emb.description = f'{inter.author.mention}, ' \
                              f'**зайдите** в **войс** {self.voice.mention}, чтобы **зарегистрироваться**!'
            emb.set_thumbnail(url=inter.author.display_avatar.url)
            return await inter.send(embed=emb, ephemeral=True)
        if inter.author == self.leader:
            emb = disnake.Embed(color=0x2f3136, title='Ошибка')
            emb.description = f'{inter.author.mention}, ' \
                              f'Вы **не можете** зарегистрироваться, **потому что** Вы **ведущий**!'
            emb.set_thumbnail(url=inter.author.display_avatar.url)
            return await inter.send(embed=emb, ephemeral=True)
        if len(members) >= config.BOT_INFO['COUNT_MEMBERS']:
            emb = disnake.Embed(color=0x2f3136, title='Ошибка')
            emb.description = f'{inter.author.mention}, ' \
                              f'Вы **не можете** зарегистрироваться, лимит **участников** превышен!'
            emb.set_thumbnail(url=inter.author.display_avatar.url)
            return await inter.send(embed=emb, ephemeral=True)
        if await self.collection.find_one({"members_ids": inter.author.id}):
            emb = disnake.Embed(color=0x2f3136, title='Ошибка')
            emb.description = f'{inter.author.mention}, ' \
                              f'Вы **не можете** зарегистрироваться, Вы **уже участвуете** в другой игре!'
            emb.set_thumbnail(url=inter.author.display_avatar.url)
            return await inter.send(embed=emb, ephemeral=True)
        await self.collection.update_one({"_id": self.leader.id}, {"$push": {
            "members": {
                "id": inter.author.id,
                "role": None,
                "killed": False
            },
            "members_ids": inter.author.id
        }})

        members: list = (await self.collection.find_one({"_id": self.leader.id}))['members']
        if len(members) == config.BOT_INFO['COUNT_MEMBERS']:
            for nick, member_id in enumerate_members(members):
                member = await inter.guild.getch_member(member_id['id'])
                if not member: continue
                try:
                    await member.edit(nick=nick)
                except disnake.Forbidden:
                    try:
                        await member.send(
                            f"У бота не хватает прав вам изменить ник. Пожалуйста, измените ник на ``{nick}``")
                    except disnake.Forbidden:
                        pass
                    continue
        members: list = (await self.collection.find_one({"_id": self.leader.id}))['members']
        emb = disnake.Embed(color=0x2f3136, title='Запись на стол мафии')
        emb.description = get_member_list_description(members, self.leader)
        emb.timestamp = datetime.datetime.now()
        try:
            await inter.edit_original_response(embed=emb, view=self)
        except disnake.HTTPException:
            pass
