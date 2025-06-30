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

# ------------------------
# WHITELIST & SETTINGS
# ------------------------
WHITELIST = {
    843180408152784936, 662596869221908480,
    1159469934989025290, 830212609961754654,
    1206001825556471820, 557628352828014614,
    491769129318088714, 235148962103951360,
    1308474671796326500, 1355616888624910396
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

BACKUP_FILE = "server_backup.json"

# ------------------------
# HILFSFUNKTIONEN
# ------------------------

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

# ------------------------
# EVENTS
# ------------------------

@bot.event
async def on_ready():
    print(f'✅ {bot.user} ist online!')
    try:
        synced = await tree.sync()
        print(f"🔃 {len(synced)} Slash-Commands synchronisiert.")
    except Exception as e:
        print("❌ Fehler beim Slash-Sync:", e)

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
    await asyncio.sleep(0)
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
    await asyncio.sleep(0)
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
    await asyncio.sleep(0)
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
        return
    count = kick_violations.get(kicker.id, 0) + 1
    kick_violations[kicker.id] = count
    print(f"⚠ Kick-Verstoß #{count} von {kicker}")
    if count >= MAX_ALLOWED_KICKS:
        try:
            await member_obj.kick(reason="🚫 Kick-Limit überschritten")
            print(f"🥾 {member_obj} wurde wegen Kick-Limit gekickt.")
        except Exception as e:
            print(f"❌ Fehler beim Kick (Limit): {e}")

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
    member_obj = guild.get_member(banner.id)
    if not member_obj:
        return
    if any(role.id == AUTHORIZED_ROLE_ID for role in member_obj.roles):
        return
    count = ban_violations.get(banner.id, 0) + 1
    ban_violations[banner.id] = count
    print(f"⚠ Ban-Verstoß #{count} von {banner}")
    if count >= MAX_ALLOWED_BANS:
        try:
            await member_obj.kick(reason="🚫 Ban-Limit überschritten")
            print(f"🥾 {member_obj} wurde wegen Ban-Limit gekickt.")
        except Exception as e:
            print(f"❌ Fehler beim Kick (Ban-Limit): {e}")

@bot.event
async def on_member_join(member: discord.Member):
    if member.id in AUTO_KICK_IDS:
        try:
            await member.kick(reason="🚫 Dieser Nutzer ist gesperrt (Auto-Kick bei Join)")
            print(f"🥾 Auto-Kick: {member} wurde beim Beitritt entfernt.")
        except Exception as e:
            print(f"❌ Fehler beim Auto-Kick: {e}")
        return
    # Custom Join Message
    channel = discord.utils.get(member.guild.text_channels, name="【📢】news")
    if channel:
        try:
            await channel.send(f"👋 Herzlich Willkommen, {member.mention}!")
        except Exception as e:
            print(f"❌ Fehler bei Join-Nachricht: {e}")

# ------------------------
# BACKUP / RESET COMMANDS
# ------------------------

@tree.command(name="backup", description="Sichert alle Kanäle im Server")
async def backup(interaction: discord.Interaction):
    if interaction.user.id not in WHITELIST:
        await interaction.response.send_message("🚫 Du hast keine Berechtigung.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    backup_data = {
        "text_channels": [],
        "voice_channels": [],
        "categories": []
    }

    # Backup Kategorien
    for category in guild.categories:
        backup_data["categories"].append({
            "name": category.name,
            "position": category.position,
            "nsfw": category.nsfw
        })

    # Backup Textkanäle
    for channel in guild.text_channels:
        backup_data["text_channels"].append({
            "name": channel.name,
            "topic": channel.topic,
            "position": channel.position,
            "category": channel.category.name if channel.category else None,
            "nsfw": channel.nsfw,
            "slowmode_delay": channel.slowmode_delay,
            "permissions": [perm for perm in channel.overwrites.items()]
        })

    # Backup Voicekanäle
    for channel in guild.voice_channels:
        backup_data["voice_channels"].append({
            "name": channel.name,
            "bitrate": channel.bitrate,
            "position": channel.position,
            "category": channel.category.name if channel.category else None,
            "user_limit": channel.user_limit,
            "permissions": [perm for perm in channel.overwrites.items()]
        })

    # Speichern in JSON Datei
    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)
        # Keine Nachricht senden (auf Wunsch)
    except Exception as e:
        print(f"❌ Fehler beim Speichern des Backups: {e}")

@tree.command(name="reset", description="Löscht alle Kanäle und stellt das Backup wieder her")
async def reset(interaction: discord.Interaction):
    if interaction.user.id not in WHITELIST:
        await interaction.response.send_message("🚫 Du hast keine Berechtigung.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    # Lade Backup
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
    except Exception as e:
        await interaction.followup.send("❌ Kein Backup gefunden oder Fehler beim Laden.")
        return

    # Alle Kanäle löschen
    for channel in list(guild.channels):
        try:
            await channel.delete(reason="🔄 Server Reset")
        except Exception as e:
            print(f"❌ Fehler beim Löschen von {channel.name}: {e}")

    # Kategorien wiederherstellen
    categories_map = {}
    for cat_data in sorted(backup_data.get("categories", []), key=lambda c: c["position"]):
        try:
            category = await guild.create_category(
                name=cat_data["name"],
                position=cat_data["position"],
                nsfw=cat_data.get("nsfw", False),
                reason="🔄 Server Reset Backup"
            )
            categories_map[cat_data["name"]] = category
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Kategorie {cat_data['name']}: {e}")

    # Textkanäle wiederherstellen
    for chan_data in backup_data.get("text_channels", []):
        try:
            overwrites = {}
            for target, perms in chan_data.get("permissions", []):
                overwrites[target] = discord.PermissionOverwrite.from_pair(perms.get("allow", 0), perms.get("deny", 0))

            category = categories_map.get(chan_data.get("category"))

            channel = await guild.create_text_channel(
                name=chan_data["name"],
                topic=chan_data.get("topic"),
                position=chan_data["position"],
                category=category,
                nsfw=chan_data.get("nsfw", False),
                slowmode_delay=chan_data.get("slowmode_delay", 0),
                overwrites=overwrites,
                reason="🔄 Server Reset Backup"
            )
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Textkanals {chan_data['name']}: {e}")

    # Voicekanäle wiederherstellen
    for chan_data in backup_data.get("voice_channels", []):
        try:
            overwrites = {}
            for target, perms in chan_data.get("permissions", []):
                overwrites[target] = discord.PermissionOverwrite.from_pair(perms.get("allow", 0), perms.get("deny", 0))

            category = categories_map.get(chan_data.get("category"))

            channel = await guild.create_voice_channel(
                name=chan_data["name"],
                bitrate=chan_data.get("bitrate", 64000),
                position=chan_data["position"],
                category=category,
                user_limit=chan_data.get("user_limit", 0),
                overwrites=overwrites,
                reason="🔄 Server Reset Backup"
            )
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Voice-Kanals {chan_data['name']}: {e}")

    # Keine Erfolgsmeldung, wie gewünscht
    # await interaction.followup.send(f"✅ Alle Kanäle wurden zurückgesetzt.")

# ------------------------
# BOT STARTEN
# ------------------------

bot.run(TOKEN)
