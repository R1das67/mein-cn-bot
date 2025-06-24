from keep_alive import keep_alive
import discord
from discord.ext import commands
import re
import asyncio
import os
from datetime import datetime

keep_alive()

TOKEN = os.getenv('DISCORD_TOKEN') or 'DeinTokenHier'

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.webhooks = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Whitelist-IDs (Admins, Bots etc.)
WHITELIST = {
    843180408152784936, 662596869221908480,
    1159469934989025290, 830212609961754654,
    1206001825556471820
}

DELETE_TIMEOUT = 3600  # 1 Stunde in Sekunden
invite_pattern = re.compile(r"(https?:\/\/)?(www\.)?(discord\.gg|discordapp\.com\/invite)\/\w+", re.I)

invite_violations = {}
user_timeouts = {}
webhook_violations = {}
delete_timeout_active = False

# --- BOT START ---
@bot.event
async def on_ready():
    print(f'✅ {bot.user} ist online!')

# --- Invite-Link Kontrolle inkl. Bots ---
@bot.event
async def on_message(message):
    if message.author.id in WHITELIST:
        return await bot.process_commands(message)

    if invite_pattern.search(message.content):
        try:
            await message.delete()
            print(f"🚫 Invite-Link gelöscht von {message.author} ({message.author.id})")
        except Exception as e:
            print(f"❌ Fehler beim Löschen des Links: {e}")

        if message.author.bot:
            print(f"🤖 Bot {message.author} hat Invite gepostet – gelöscht.")
            return

        count = invite_violations.get(message.author.id, 0) + 1
        invite_violations[message.author.id] = count

        if count >= 3:
            try:
                await message.author.timeout(
                    duration=DELETE_TIMEOUT,
                    reason="🔇 3x Invite gepostet"
                )
                user_timeouts[message.author.id] = datetime.utcnow().timestamp() + DELETE_TIMEOUT
                print(f"⏱ {message.author} wurde für 1 Stunde getimeoutet.")
            except Exception as e:
                print(f"❌ Timeout fehlgeschlagen: {e}")

    # Prüfe laufende Timeouts
    if message.author.id in user_timeouts:
        if user_timeouts[message.author.id] > datetime.utcnow().timestamp():
            try:
                await message.delete()
                print(f"🕒 Nachricht von getimeten User {message.author} gelöscht.")
            except:
                pass
            return
        else:
            del user_timeouts[message.author.id]

    await bot.process_commands(message)

# --- Webhook Schutz ---
@bot.event
async def on_webhooks_update(channel):
    try:
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.user and webhook.user.id not in WHITELIST:
                guild = channel.guild
                user = None
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
                    if entry.target.id == webhook.id:
                        user = entry.user
                        break

                await webhook.delete(reason="❌ Webhook nicht erlaubt")
                print(f"🧹 Webhook {webhook.name} gelöscht.")

                if user:
                    count = webhook_violations.get(user.id, 0) + 1
                    webhook_violations[user.id] = count
                    print(f"⚠ Webhook-Verstoß #{count} von {user}")

                    if count >= 2:
                        await reset_user_roles(user, guild)

    except Exception as e:
        print(f"❌ Fehler bei Webhook-Kontrolle: {e}")

# --- Rollenentzug nach Webhook-Verstoß ---
async def reset_user_roles(user, guild):
    member = guild.get_member(user.id)
    if not member:
        print(f"⚠ User {user} nicht gefunden.")
        return

    try:
        roles_to_remove = [role for role in member.roles if role.name != "@everyone"]
        await member.remove_roles(*roles_to_remove, reason="🚫 Webhook-Verstoß")
        print(f"🔁 Rollen von {user} entfernt.")
    except Exception as e:
        print(f"❌ Fehler beim Entfernen der Rollen: {e}")

# --- Kanal löschen ---
@bot.event
async def on_guild_channel_delete(channel):
    global delete_timeout_active
    guild = channel.guild

    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
        if entry.target.id == channel.id:
            user = entry.user
            break
    else:
        return

    if not user or user.id in WHITELIST:
        return

    if delete_timeout_active:
        print(f"⏳ Timeout aktiv – kein Kick für {user}")
        return

    delete_timeout_active = True
    member = guild.get_member(user.id)

    if member:
        try:
            await member.kick(reason="🧨 Kanal gelöscht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Kanal gelöscht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

    await asyncio.sleep(DELETE_TIMEOUT)
    delete_timeout_active = False
    print("✅ Timeout für Kanal-Kick aufgehoben.")

# --- Rolle löschen ---
@bot.event
async def on_guild_role_delete(role):
    global delete_timeout_active
    guild = role.guild

    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
        if entry.target.id == role.id:
            user = entry.user
            break
    else:
        return

    if not user or user.id in WHITELIST:
        return

    if delete_timeout_active:
        print(f"⏳ Timeout aktiv – kein Kick für {user}")
        return

    delete_timeout_active = True
    member = guild.get_member(user.id)

    if member:
        try:
            await member.kick(reason="🧨 Rolle gelöscht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Rolle gelöscht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

    await asyncio.sleep(DELETE_TIMEOUT)
    delete_timeout_active = False
    print("✅ Timeout für Rollen-Kick aufgehoben.")

bot.run(TOKEN)
