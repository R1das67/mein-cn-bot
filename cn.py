from keep_alive import keep_alive
import discord
from discord.ext import commands
keep_alive()
import re
import asyncio
import os

TOKEN = os.getenv('DISCORD_TOKEN') or 'DeinTokenHier'

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.webhooks = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Whitelist (IDs als int)
WEBHOOK_WHITELIST = {843180408152784936,662596869221908480,1159469934989025290,830212609961754654,1206001825556471820}
INVITE_WHITELIST = {843180408152784936,662596869221908480,1159469934989025290,830212609961754654,1206001825556471820}
ROLE_WHITELIST = {843180408152784936,662596869221908480,1159469934989025290,830212609961754654,1206001825556471820}
CHANNEL_WHITELIST = {843180408152784936,662596869221908480,1159469934989025290,830212609961754654,1206001825556471820}
USER_WHITELIST = {843180408152784936,662596869221908480,1159469934989025290,830212609961754654,1206001825556471820}

DELETE_TIMEOUT = 3600  # 1 Stunde Timeout in Sekunden

# State für Timeout bei Kanal/Rollen löschen
delete_timeout_active = False

# Invite-Verstöße pro User (user_id: count)
invite_violations = {}

# Timeout für User (user_id: timestamp bis wann)
user_timeouts = {}

invite_pattern = re.compile(r"(https?:\/\/)?(www\.)?(discord\.gg|discordapp\.com\/invite)\/\w+", re.I)

@bot.event
async def on_ready():
    print(f'{bot.user} ist online!')

# --- Webhook direkt löschen, wenn nicht whitelist ---
@bot.event
async def on_webhook_update(channel):
    try:
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.id not in WEBHOOK_WHITELIST:
                # Auditlog für User, der Webhook erstellt hat
                guild = channel.guild
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                    if entry.target.id == webhook.id:
                        user = entry.user
                        break
                else:
                    user = None

                await webhook.delete(reason="Anti-Webhook - nicht auf Whitelist")
                print(f"Webhook {webhook.name} gelöscht.")

                if user and user.id not in USER_WHITELIST:
                    # Optional: zähle Verstöße für Webhook-Erstellung? (kann man ergänzen)
                    print(f"Webhook erstellt von {user}, gelöscht.")
    except Exception as e:
        print(f"Fehler bei Webhook Update: {e}")

# --- Invite-Link Kontrolle ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in USER_WHITELIST:
        await bot.process_commands(message)
        return

    # Timeout prüfen
    if message.author.id in user_timeouts:
        from datetime import datetime
        if user_timeouts[message.author.id] > datetime.utcnow().timestamp():
            try:
                await message.delete()
                print(f"Nachricht von getimtem User {message.author} gelöscht.")
            except:
                pass
            return
        else:
            del user_timeouts[message.author.id]

    if invite_pattern.search(message.content):
        try:
            await message.delete()
            print(f"Invite-Link von {message.author} gelöscht.")
        except Exception as e:
            print(f"Fehler beim Löschen der Nachricht: {e}")

        # Zähle Verstöße
        count = invite_violations.get(message.author.id, 0) + 1
        invite_violations[message.author.id] = count
        if count >= 3:
            # Timeout User 1h
            try:
                await message.author.timeout(duration=DELETE_TIMEOUT, reason="3x Einladungslink gepostet")
                print(f"User {message.author} für 1h getimeoutet wegen 3x Invite-Verstoß.")
                user_timeouts[message.author.id] = (discord.utils.utcnow().timestamp() + DELETE_TIMEOUT)
            except Exception as e:
                print(f"Fehler beim Timeout setzen: {e}")

    await bot.process_commands(message)

# --- Rollen löschen: User kicken statt timeout ---
@bot.event
async def on_guild_role_delete(role):
    global delete_timeout_active

    if role.id in ROLE_WHITELIST:
        return

    guild = role.guild
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
        if entry.target.id == role.id:
            user = entry.user
            break
    else:
        user = None

    if user is None or user.id in USER_WHITELIST:
        return

    if delete_timeout_active:
        print(f"Löschung der Rolle {role.name} von {user} geblockt (Timeout aktiv).")
        return

    delete_timeout_active = True
    print(f"User {user} wird gekickt wegen Rollen-Löschung.")

    try:
        member = guild.get_member(user.id)
        if member:
            await member.kick(reason="Rolle gelöscht ohne Erlaubnis")
            print(f"User {user} gekickt.")
    except Exception as e:
        print(f"Fehler beim Kick von {user}: {e}")

    async def reset_timeout():
        global delete_timeout_active
        await asyncio.sleep(DELETE_TIMEOUT)
        delete_timeout_active = False
        print("Timeout für Rollen/Kanäle beendet.")

    bot.loop.create_task(reset_timeout())

# --- Kanal löschen: User kicken statt timeout ---
@bot.event
async def on_guild_channel_delete(channel):
    global delete_timeout_active

    if channel.id in CHANNEL_WHITELIST:
        return

    guild = channel.guild
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
        if entry.target.id == channel.id:
            user = entry.user
            break
    else:
        user = None

    if user is None or user.id in USER_WHITELIST:
        return

    if delete_timeout_active:
        print(f"Löschung des Kanals {channel.name} von {user} geblockt (Timeout aktiv).")
        return

    delete_timeout_active = True
    print(f"User {user} wird gekickt wegen Kanal-Löschung.")

    try:
        member = guild.get_member(user.id)
        if member:
            await member.kick(reason="Kanal gelöscht ohne Erlaubnis")
            print(f"User {user} gekickt.")
    except Exception as e:
        print(f"Fehler beim Kick von {user}: {e}")

    async def reset_timeout():
        global delete_timeout_active
        await asyncio.sleep(DELETE_TIMEOUT)
        delete_timeout_active = False
        print("Timeout für Rollen/Kanäle beendet.")

    bot.loop.create_task(reset_timeout())

bot.run(TOKEN)
