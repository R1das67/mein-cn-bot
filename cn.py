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
            print(f"🥾 Auto-Kick für {member} ausgeführt.")
        except Exception as e:
            print(f"❌ Fehler beim Auto-Kick: {e}")

# ------------------------
# BACKUP UND RESTORE
# ------------------------

@tree.command(name="backup", description="Erstellt ein Backup aller Kanäle")
async def backup(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Befehl zu verwenden.", ephemeral=True)
        return
    await interaction.response.send_message("⏳ Backup wird erstellt...")
    guild = interaction.guild
    channels_data = []
    for channel in guild.channels:
        ch_type = None
        if isinstance(channel, discord.TextChannel):
            ch_type = "text"
        elif isinstance(channel, discord.VoiceChannel):
            ch_type = "voice"
        elif isinstance(channel, discord.CategoryChannel):
            ch_type = "category"
        else:
            ch_type = "other"
        channel_info = {
            "id": channel.id,
            "name": channel.name,
            "type": ch_type,
            "position": channel.position,
            "category_id": channel.category.id if channel.category else None
        }
        if ch_type == "text":
            channel_info.update({
                "topic": channel.topic,
                "nsfw": channel.nsfw,
                "slowmode_delay": channel.slowmode_delay,
                "rate_limit_per_user": channel.slowmode_delay
            })
        elif ch_type == "voice":
            channel_info.update({
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit
            })
        channels_data.append(channel_info)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": channels_data}, f, indent=4, ensure_ascii=False)
    await interaction.followup.send(f"✅ Backup gespeichert in `{BACKUP_FILE}`.")

async def restore_channels(guild, backup_file=BACKUP_FILE):
    try:
        with open(backup_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Backup-Datei konnte nicht geladen werden: {e}")
        return 0

    created_channels = 0
    category_cache = {}

    # Erst Kategorien anlegen, damit sie für andere Kanäle vorhanden sind
    for ch_data in data.get("channels", []):
        if ch_data["type"] == "category":
            try:
                cat = await guild.create_category(ch_data["name"], position=ch_data.get("position", 0), reason="Restore Backup Kategorie")
                category_cache[ch_data["id"]] = cat
                created_channels += 1
            except Exception as e:
                print(f"❌ Fehler beim Erstellen Kategorie {ch_data['name']}: {e}")

    # Danach andere Kanäle anlegen
    for ch_data in data.get("channels", []):
        if ch_data["type"] == "text":
            category = category_cache.get(ch_data.get("category_id"))
            try:
                await guild.create_text_channel(
                    name=ch_data["name"],
                    topic=ch_data.get("topic"),
                    nsfw=ch_data.get("nsfw", False),
                    slowmode_delay=ch_data.get("slowmode_delay", 0),
                    position=ch_data.get("position", 0),
                    category=category,
                    reason="Restore Backup"
                )
                created_channels += 1
            except Exception as e:
                print(f"❌ Fehler beim Erstellen Text-Kanal {ch_data['name']}: {e}")
        elif ch_data["type"] == "voice":
            category = category_cache.get(ch_data.get("category_id"))
            try:
                await guild.create_voice_channel(
                    name=ch_data["name"],
                    bitrate=ch_data.get("bitrate", 64000),
                    user_limit=ch_data.get("user_limit", 0),
                    position=ch_data.get("position", 0),
                    category=category,
                    reason="Restore Backup"
                )
                created_channels += 1
            except Exception as e:
                print(f"❌ Fehler beim Erstellen Voice-Kanal {ch_data['name']}: {e}")

    return created_channels

@tree.command(name="reset", description="Setzt den Server zurück (löscht alle Kanäle und stellt sie wieder her).")
async def reset(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("❌ Du bist nicht berechtigt, diesen Befehl zu nutzen.", ephemeral=True)
        return
    
    guild = interaction.guild
    await interaction.response.send_message("⏳ Lösche alle Kanäle...")

    deleted_channels = 0
    for channel in guild.channels:
        try:
            await channel.delete(reason="Reset durch /reset Befehl")
            deleted_channels += 1
        except Exception as e:
            print(f"❌ Fehler beim Löschen Kanal {channel.name}: {e}")

    await interaction.followup.send(f"✅ {deleted_channels} Kanäle wurden gelöscht.")
    await asyncio.sleep(5)  # Kleine Pause, um sicherzugehen, dass alles gelöscht ist

    await interaction.followup.send("⏳ Stelle Kanäle aus Backup wieder her...")

    created_channels = await restore_channels(guild)
    await interaction.followup.send(f"✅ {created_channels} Kanäle wurden wiederhergestellt.")

# ------------------------
# BOT STARTEN
# ------------------------

bot.run(TOKEN)
