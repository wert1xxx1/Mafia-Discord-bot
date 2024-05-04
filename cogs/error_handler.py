import sys
import traceback

import disnake
from disnake.ext import commands


def perms(permissions):
    allow = {
        "use_application_commands": "Использовать слэш команды",
        "manage_events": "Управлять событиями",
        "manage_threads": "Убравлять ветками",
        "create_public_threads": "Создавать публичные ветки",
        "create_private_threads": "Создавать приватные ветки",
        "external_stickers": "Использовать стикеры с других серверов",
        "send_messages_in_threads": "Отправлять сообщения в ветки",
        "use_embedded_activities": "Использовать embed-действия",
        "moderate_members": "Модерировать участников",
        'add_reactions': 'Добавлять реакции',
        'administrator': 'Администратор',
        'attach_files': 'Прикреплять файлы',
        'ban_members': 'Банить участников',
        'change_nickname': 'Изменять никнейм',
        'connect': 'Подключаться',
        'create_instant_invite': 'Создавать приглашение',
        'deafen_members': 'Отключать участникам звук',
        'embed_links': 'Встраивать ссылки',
        'external_emojis': 'Использовать внешние эмодзи',
        'kick_members': 'Выгонять участников',
        'manage_channels': 'Управлять каналами',
        'manage_emojis': 'Управлять эмодзи',
        'manage_guild': 'Управлять сервером',
        'manage_messages': 'Управлять сообщениями',
        'manage_nicknames': 'Управлять никнеймами',
        'manage_permissions': 'Управлять разрешениями',
        'manage_roles': 'Управлять ролями',
        'manage_webhooks': 'Управлять вебхуками (webhooks)',
        'mention_everyone': 'Упоминание @everyone, @here и всех ролей',
        'move_members': 'Перемещать участников',
        'mute_members': 'Отключать участникам микрофон',
        'priority_speaker': 'Приоритетный режим',
        'read_message_history': 'Читать историю сообщений',
        'read_messages': 'Читать историю сообщений',
        'request_to_speak': 'Попросить выступить',
        'send_messages': 'Отправлять сообщения',
        'send_tts_messages': 'Отпрвлять сообщения text-to-speech',
        'speak': 'Говорить',
        'stream': 'Видео',
        'use_external_emojis': 'Использовать внешние эмодзи',
        'use_voice_activation': 'Использовать режим активации по голосу',
        'use_slash_commands': 'Использовать слэш-команды',
        'view_audit_log': 'Просматривать журнал аудита',
        'view_channel': 'Просматривать каналы',
        'view_guild_insights': 'Просмотр аналитики серверов'
    }
    perms_ = []
    for perm in permissions:
        perms_.append(f"``{allow[perm]}``")
    return perms_


class ErrorHandler(commands.Cog):
    def __init__(self, client: commands.InteractionBot):
        self.client = client

    @commands.Cog.listener("on_slash_command_error")
    async def error_handler(self, interaction: disnake.AppCmdInter, error: Exception) -> None:
        command = interaction.application_command
        if command and command.has_error_handler():
            return

        cog = command.cog
        if cog and cog.has_slash_error_handler():
            return
        if isinstance(error, commands.CommandNotFound):
            await interaction.send("Данной команды в этом боте не существует!", ephemeral=True)
            return
        if isinstance(error, commands.NoPrivateMessage):
            await interaction.send("Данная команда работает только на сервере!", ephemeral=True)
            return
        if isinstance(error, commands.MissingRole):
            await interaction.send(f"У вас не хватает роли - {error.missing_role}, чтобы выполнить команду!",
                                   ephemeral=True)
            return
        if isinstance(error, commands.MissingAnyRole):
            missing_roles = []
            for role in error.missing_roles:
                if isinstance(role, int):
                    missing_roles.append(disnake.utils.get(interaction.guild.roles, id=role).mention)
                if isinstance(role, str):
                    missing_roles.append(disnake.utils.get(interaction.guild.roles, name=role).mention)
            await interaction.send(
                f"У вас не хватает этих ролей: {', '.join(missing_roles)}. Чтобы выполнить команду!", ephemeral=True)
            return
        if isinstance(error, commands.MissingPermissions):
            await interaction.send(
                f"У вас не хватает прав: {', '.join(perms(error.missing_permissions))}. Чтобы выполнить команду!",
                ephemeral=True)
            return
        if isinstance(error, commands.BotMissingPermissions):
            await interaction.send(
                f"У бота не хватает прав: {', '.join(perms(error.missing_permissions))}. Чтобы выполнить команду!",
                ephemeral=True)
            return
        if isinstance(error, commands.CommandOnCooldown):
            await interaction.send(
                f"Подожди ``{error.retry_after:.2f}`` сек. чтобы выполнить команду!",
                ephemeral=True)
            return
        if isinstance(error, commands.CheckFailure):
            emb = disnake.Embed(color=0x2f3136, title="Неизвестная ошибка!")
            emb.description = f"**Вы не прошли проверку на выполнение данной команды.**\n" \
                              f"**Аргументы ошибки:** ``{error.args}``"
            await interaction.send(embed=emb)
        if isinstance(error, commands.CommandInvokeError):
            app_info = await self.client.application_info()
            emb = disnake.Embed(color=0x2f3136, title="Ошибка!")
            emb.description = f"**Произошла неизвестная ошибка на стороне бота!**\n" \
                              f"Напишите в личные сообщения Владельца бота о данной ошибке"
            emb.set_footer(text=f"Владелец бота: {str(app_info.owner)}", icon_url=app_info.owner.display_avatar.url)
            try:
                await interaction.send(embed=emb)
            except disnake.InteractionTimedOut:
                pass
            print(f"Ignoring exception in user command {command.name!r}:", file=sys.stderr)
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr
            )
            return



def setup(client):
    client.add_cog(ErrorHandler(client))
