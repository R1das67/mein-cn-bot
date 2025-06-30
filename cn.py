from keep_alive import keep_alive
import discord
from discord.ext import commands
import re
import asyncio
import os
import json
from discord import app_commands
from datetime import datetime, timezone

keep_alive()

TOKEN = os.getenv('DISCORD_TOKEN') or 'DeinTokenHier'

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.webhooks = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

WHITELIST = {
    843180408152784936, 662596869221908480,
    1159469934989025290, 830212609961754654,
    1206001825556471820, 557628352828014614,
    491769129318088714, 235148962103951360,
    1308474671796326500
}

AUTO_KICK_IDS = {
    1325204584829947914,
    1169714843784335504,
}

DELETE_TIMEOUT = 3600
invite_violations = {}
user_timeouts = {}
webhook_violations = {}
kick_violations = {}
ban_violations = {}

AUTHORIZED_ROLE_ID = 1387413152873975993
MAX_ALLOWED_KICKS = 3
MAX_ALLOWED_BANS = 3

invite_pattern = re.compile(
    r"(https?:\/\/)?(www\.)?(discord\.gg|discord(app)?\.com\/(invite|oauth2\/authorize))\/\w+|(?:discord(app)?\.com.*invite)", re.I
)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} ist online!')
    try:
        synced = await tree.sync()
        print(f"🔃 {len(synced)} Slash-Commands synchronisiert.")
    except Exception as e:
        print("❌ Fehler beim Slash-Sync:", e)

def is_whitelisted(user_id):
    return user_id in WHITELIST

async def reset_rules_for_user(user, guild):
    member = guild.get_member(user.id)
    if member:
        try:
            roles_to_remove = [r for r in member.roles if r.name != "@everyone"]
            await member.remove_roles(*roles_to_remove, reason="Reset nach 2x Webhook-Verstoß")
            print(f"🔁 Rollen von {user} entfernt.")
        except Exception as e:
            print(f"❌ Fehler bei Rollenentfernung: {e}")
    else:
        print(f"⚠ Mitglied {user} nicht gefunden.")

@bot.event
async def on_webhooks_update(channel):
    print(f"🔄 Webhook Update erkannt in {channel.name}")
    await asyncio.sleep(3)
    try:
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            print(f"🧷 Webhook gefunden: {webhook.name} ({webhook.id})")
            if webhook.user and is_whitelisted(webhook.user.id):
                print(f"✅ Whitelisted: {webhook.user}")
                continue
            user = None
            async for entry in channel.guild.audit_logs(limit=10, action=discord.AuditLogAction.webhook_create):
                if entry.target and entry.target.id == webhook.id:
                    user = entry.user
                    break
            await webhook.delete(reason="🔒 Unautorisierter Webhook")
            print(f"❌ Webhook {webhook.name} gelöscht")
            if user and not is_whitelisted(user.id):
                count = webhook_violations.get(user.id, 0) + 1
                webhook_violations[user.id] = count
                print(f"⚠ Webhook-Verstoß #{count} von {user}")
                if count >= 2:
                    await reset_rules_for_user(user, channel.guild)
    except Exception as e:
        print("❌ Fehler bei Webhook Handling:")
        import traceback
        traceback.print_exc()

@bot.event
async def on_message(message):
    if is_whitelisted(message.author.id):
        await bot.process_commands(message)
        return
    now_ts = datetime.now(timezone.utc).timestamp()
    if message.author.id in user_timeouts:
        if user_timeouts[message.author.id] > now_ts:
            try:
                await message.delete()
                print(f"🚫 Nachricht von getimtem User {message.author} gelöscht.")
            except:
                pass
            return
        else:
            del user_timeouts[message.author.id]
    if invite_pattern.search(message.content):
        try:
            await message.delete()
            print(f"🚫 Invite-Link gelöscht von {message.author}")
        except Exception as e:
            print(f"❌ Fehler beim Invite-Löschen: {e}")
        count = invite_violations.get(message.author.id, 0) + 1
        invite_violations[message.author.id] = count
        print(f"⚠ Invite-Verstoß #{count} von {message.author}")
        if count >= 3:
            try:
                await message.author.timeout(duration=DELETE_TIMEOUT, reason="🔇 3x Invite-Verstoß")
                user_timeouts[message.author.id] = now_ts + DELETE_TIMEOUT
                print(f"⏱ {message.author} wurde für 1 Stunde getimeoutet.")
            except Exception as e:
                print(f"❌ Fehler beim Timeout: {e}")
    await bot.process_commands(message)

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
        if entry.target.id == role.id:
            user = entry.user
            break
    else:
        return
    if not user or is_whitelisted(user.id):
        return
    member = guild.get_member(user.id)
    if member:
        try:
            await member.kick(reason="🧨 Rolle gelöscht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Rolle gelöscht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
        if entry.target.id == channel.id:
            user = entry.user
            break
    else:
        return
    if not user or is_whitelisted(user.id):
        return
    member = guild.get_member(user.id)
    if member:
        try:
            await member.kick(reason="🧨 Kanal gelöscht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Kanal gelöscht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_guild_role_create(role):
    guild = role.guild
    await asyncio.sleep(2)
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
        if entry.target.id == role.id:
            user = entry.user
            break
    else:
        return
    if is_whitelisted(user.id):
        return
    try:
        await role.delete(reason="🔒 Rolle von unautorisiertem Nutzer erstellt")
        print(f"❌ Rolle {role.name} gelöscht")
    except Exception as e:
        print(f"❌ Fehler beim Löschen der Rolle: {e}")
    member = guild.get_member(user.id)
    if member:
        try:
            await member.kick(reason="🧨 Rolle erstellt ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Rolle erstellt).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    await asyncio.sleep(2)
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
        if entry.target.id == channel.id:
            user = entry.user
            break
    else:
        return
    if is_whitelisted(user.id):
        return
    try:
        await channel.delete(reason="🔒 Kanal von unautorisiertem Nutzer erstellt")
        print(f"❌ Kanal {channel.name} gelöscht")
    except Exception as e:
        print(f"❌ Fehler beim Löschen des Kanals: {e}")
    member = guild.get_member(user.id)
    if member:
        try:
            await member.kick(reason="🧨 Kanal erstellt ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Kanal erstellt).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_member_remove(member):
    await asyncio.sleep(2)
    guild = member.guild
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
        if entry.target.id == member.id:
            kicker = entry.user
            break
    else:
        return
    if not kicker or is_whitelisted(kicker.id):
        return
    member_obj = guild.get_member(kicker.id)
    if not member_obj:
        return
    if any(role.id == AUTHORIZED_ROLE_ID for role in member_obj.roles):
        count = kick_violations.get(kicker.id, 0) + 1
        kick_violations[kicker.id] = count
        print(f"⚠ Kick #{count} von {kicker}")
        if count > MAX_ALLOWED_KICKS:
            try:
                await member_obj.kick(reason="🧨 Zu viele Kicks mit eingeschränkter Rolle")
                print(f"🥾 {member_obj} wurde gekickt (Kicklimit überschritten).")
            except Exception as e:
                print(f"❌ Fehler beim Kick des Kickers: {e}")
    else:
        try:
            await member_obj.kick(reason="🧨 Unautorisierter Kick eines Mitglieds")
            print(f"🥾 {member_obj} wurde gekickt (nicht erlaubt zu kicken).")
        except Exception as e:
            print(f"❌ Fehler beim Kick des Kickers: {e}")

@bot.event
async def on_member_ban(guild, user):
    await asyncio.sleep(2)
    async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
        if entry.target.id == user.id:
            banner = entry.user
            break
    else:
        return
    if not banner or is_whitelisted(banner.id):
        return
    member = guild.get_member(banner.id)
    if not member:
        return
    if any(role.id == AUTHORIZED_ROLE_ID for role in member.roles):
        count = ban_violations.get(banner.id, 0) + 1
        ban_violations[banner.id] = count
        print(f"⚠ Ban #{count} von {banner}")
        if count > MAX_ALLOWED_BANS:
            try:
                await member.kick(reason="🧨 Zu viele Bans mit eingeschränkter Rolle")
                print(f"🥾 {member} wurde gekickt (Banlimit überschritten).")
            except Exception as e:
                print(f"❌ Fehler beim Kick des Banners: {e}")
    else:
        try:
            await member.kick(reason="🧨 Unautorisierter Ban eines Mitglieds")
            print(f"🥾 {member} wurde gekickt (nicht erlaubt zu bannen).")
        except Exception as e:
            print(f"❌ Fehler beim Kick des Banners: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    if member.id in AUTO_KICK_IDS:
        try:
            await member.kick(reason="🚫 Dieser Nutzer ist gesperrt (Auto-Kick bei Join)")
            print(f"🥾 Auto-Kick: {member} wurde beim Beitritt entfernt.")
        except Exception as e:
            print(f"❌ Fehler beim Auto-Kick: {e}")
        return
    if member.bot:
        guild = member.guild
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
            if entry.target.id == member.id:
                inviter = entry.user
                if not is_whitelisted(inviter.id):
                    try:
                        await member.kick(reason="🤖 Nicht autorisierter Bot")
                        print(f"🥾 Bot {member} wurde gekickt.")
                    except Exception as e:
                        print(f"❌ Fehler beim Kicken des Bots: {e}")
                    try:
                        await guild.kick(inviter, reason="🚫 Bot eingeladen ohne Erlaubnis")
                        print(f"🥾 Einladender Nutzer {inviter} wurde gekickt.")
                    except Exception as e:
                        print(f"❌ Fehler beim Kicken des Einladers: {e}")
                else:
                    print(f"✅ Bot {member} wurde von {inviter} eingeladen (whitelisted).")
                break

# -----------------------------------
# NEU: /backup & /reset server
# -----------------------------------

BACKUP_FILE = "server_backup.json"

@tree.command(name="backup", description="🔒 Erstelle ein Backup der Kanalstruktur.")
async def backup_server(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Du hast keine Berechtigung.", ephemeral=True)
        return
    guild = interaction.guild
    backup_data = []
    for category in guild.categories:
        cat_data = {
            "type": "category",
            "name": category.name,
            "channels": []
        }
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel):
                cat_data["channels"].append({
                    "type": "text",
                    "name": channel.name
                })
            elif isinstance(channel, discord.VoiceChannel):
                cat_data["channels"].append({
                    "type": "voice",
                    "name": channel.name
                })
        backup_data.append(cat_data)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)
    await interaction.response.send_message("✅ Backup gespeichert.", ephemeral=True)

@tree.command(name="reset", description="🧨 Stelle die Serverstruktur wieder her.")
@app_commands.describe(option="Tippe 'server' zur Bestätigung.")
async def reset_server(interaction: discord.Interaction, option: str):
    if option.lower() != "server":
        await interaction.response.send_message("❌ Du musst `server` eingeben zur Bestätigung.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Du hast keine Berechtigung.", ephemeral=True)
        return
    guild = interaction.guild
    await interaction.response.send_message("⚠ Wiederherstellung gestartet...", ephemeral=True)
    try:
        for channel in guild.channels:
            try:
                await channel.delete()
            except Exception as e:
                print(f"❌ Fehler beim Löschen von Kanal: {e}")
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        for category_data in backup_data:
            cat = await guild.create_category(name=category_data["name"])
            for ch in category_data["channels"]:
                if ch["type"] == "text":
                    await guild.create_text_channel(name=ch["name"], category=cat)
                elif ch["type"] == "voice":
                    await guild.create_voice_channel(name=ch["name"], category=cat)
        await interaction.followup.send("✅ Serverstruktur wiederhergestellt.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ Fehler bei der Wiederherstellung.", ephemeral=True)
        print("❌ Fehler beim Reset:", e)

bot.run(TOKEN)
