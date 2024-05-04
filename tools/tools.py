import disnake
from typing import Union


def enumerate_members(sequence):
    n = 1
    for i in sequence:
        yield (f"0{n}" if len(str(n)) != 2 else str(n)), i
        n += 1


async def edit_nicks(guild: disnake.Guild, leader: Union[disnake.Member, int], collection, fol):
    query = await collection.find_one({"_id": leader.id if isinstance(leader, disnake.Member) else leader})
    members = query['members']
    for nick, document in enumerate_members(members):
        member = await guild.getch_member(document['id'])
        if not member: continue
        try:
            if document['killed']:
                nick += " (Убит)"
                if member.voice and member.voice.channel.id == query['voice']:
                    await member.edit(mute=True, deafen=False)
            _ = await fol.find_one({"_id": member.id})
            if _:
                doc = await fol.find_one({"_id": member.id})
                nick += " "
                nick += "Ф"*doc['fol']
            if nick == member.display_name: continue
            await member.edit(nick=nick)
        except disnake.Forbidden:
            await member.send(
                f"У бота не хватает прав вам изменить ник. Пожалуйста, измените ник на ``{nick}``")
            continue


def safe_list_get(list_: list, index: int, default):
    try:
        return f'<@{list_[index]["id"]}>'
    except IndexError:
        return default


def get_member_list_description(members: list, leader: Union[disnake.Member, str]):
    return f"""
                    👥⠀**Список записавшихся**
                    **01** - {safe_list_get(members, 0, 'Пусто')}
                    **02** - {safe_list_get(members, 1, 'Пусто')}
                    **03** - {safe_list_get(members, 2, 'Пусто')}
                    **04** - {safe_list_get(members, 3, 'Пусто')}
                    **05** - {safe_list_get(members, 4, 'Пусто')}
                    **06** - {safe_list_get(members, 5, 'Пусто')}
                    **07** - {safe_list_get(members, 6, 'Пусто')}
                    **08** - {safe_list_get(members, 7, 'Пусто')}
                    **09** - {safe_list_get(members, 8, 'Пусто')}
                    **10** - {safe_list_get(members, 9, 'Пусто')}

                    Записано игроков: **{len(members)}**
                    Ведущий стола: {leader.mention if isinstance(leader, disnake.Member) else leader}
                """
