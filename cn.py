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
WHITELIST = {843180408152784936, 662596869221908480,
             830212609961754654, 1159469934989025290,
             235148962103951360,
}

AUTO_KICK_IDS = {
    1169714843784335504,
    1325204584829947914,
}

DELETE_TIMEOUT = 3600

invite_violations = {}
user_timeouts = {}
webhook_violations = {}
kick_violations = {}
ban_violations = {}

AUTHORIZED_ROLE_ID = 1387413152865718452, 1387413152873975993
MAX_ALLOWED_KICKS = 3
MAX_ALLOWED_BANS = 3

invite_pattern = re.compile(
    r"(https?:\/\/)?(www\.)?(discord\.gg|discord(app)?\.com\/(invite|oauth2\/authorize))\/\w+|(?:discord(app)?\.com.*invite)", re.I
)

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
# BACKUP / RESET SERVER
# ------------------------

backup_data = {}

def serialize_channel(channel: discord.abc.GuildChannel):
    data = {
        "name": channel.name,
        "type": channel.type,
        "position": channel.position,
        "category_id": channel.category_id,
    }
    if isinstance(channel, discord.TextChannel):
        data.update({
            "topic": channel.topic,
            "nsfw": channel.nsfw,
            "slowmode_delay": channel.slowmode_delay,
            "bitrate": None,
            "user_limit": None,
        })
    elif isinstance(channel, discord.VoiceChannel):
        data.update({
            "bitrate": channel.bitrate,
            "user_limit": channel.user_limit,
            "topic": None,
            "nsfw": None,
            "slowmode_delay": None,
        })
    else:
        data.update({
            "topic": None,
            "nsfw": None,
            "slowmode_delay": None,
            "bitrate": None,
            "user_limit": None,
        })
    return data

async def create_channel_from_backup(guild: discord.Guild, data):
    category = guild.get_channel(data["category_id"]) if data["category_id"] else None

    if data["type"] == discord.ChannelType.text:
        return await guild.create_text_channel(
            name=data["name"],
            topic=data["topic"],
            nsfw=data["nsfw"],
            slowmode_delay=data["slowmode_delay"],
            category=category,
            position=data["position"]
        )
    elif data["type"] == discord.ChannelType.voice:
        return await guild.create_voice_channel(
            name=data["name"],
            bitrate=data["bitrate"],
            user_limit=data["user_limit"],
            category=category,
            position=data["position"]
        )
    elif data["type"] == discord.ChannelType.category:
        return await guild.create_category(
            name=data["name"],
            position=data["position"]
        )
    else:
        return None

@tree.command(name="backup", description="Erstelle ein Backup aller Kanäle im Server.")
async def backup(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Kein Server gefunden.", ephemeral=True)
        return

    channels_data = []
    channels_sorted = sorted(guild.channels, key=lambda c: c.position)

    for ch in channels_sorted:
        channels_data.append(serialize_channel(ch))

    backup_data[guild.id] = channels_data
    await interaction.response.send_message(f"✅ Backup für **{guild.name}** mit {len(channels_data)} Kanälen wurde gespeichert.")

@tree.command(name="reset", description="Starte Reset-Aktion. Optionen: 'server'")
@app_commands.describe(option="Option für Reset, z.B. 'server'")
async def reset(interaction: discord.Interaction, option: str):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Kein Server gefunden.", ephemeral=True)
        return

    if option.lower() != "server":
        await interaction.response.send_message("❌ Unbekannte Option. Nur 'server' ist erlaubt.", ephemeral=True)
        return

    if guild.id not in backup_data:
        await interaction.response.send_message("❌ Kein Backup für diesen Server gefunden. Bitte erst `/backup` ausführen.", ephemeral=True)
        return

    await interaction.response.send_message("⚠️ Starte Server Reset: Kanäle werden gelöscht und aus Backup wiederhergestellt...", ephemeral=True)

    for ch in guild.channels:
        try:
            await ch.delete(reason="Reset Server durch Bot")
        except Exception as e:
            print(f"Fehler beim Löschen von Kanal {ch.name}: {e}")

    await asyncio.sleep(3)

    channels_backup = backup_data[guild.id]

    categories = [c for c in channels_backup if c["type"] == discord.ChannelType.category]
    category_map = {}

    for cat_data in categories:
        cat = await create_channel_from_backup(guild, cat_data)
        if cat:
            category_map[cat_data["name"]] = cat

    for ch_data in channels_backup:
        if ch_data["type"] == discord.ChannelType.category:
            continue

        if ch_data["category_id"]:
            orig_cat = guild.get_channel(ch_data["category_id"])
            cat_name = orig_cat.name if orig_cat else None
            if cat_name in category_map:
                ch_data["category_id"] = category_map[cat_name].id
            else:
                ch_data["category_id"] = None
        else:
            ch_data["category_id"] = None

        await create_channel_from_backup(guild, ch_data)

    await interaction.followup.send("✅ Server Reset abgeschlossen. Kanäle wurden wiederhergestellt.")

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
async def on_member_join(member):
    if member.id in AUTO_KICK_IDS:
        try:
            await member.kick(reason="Auto-Kick: Gelistete ID")
            print(f"🥾 {member} wurde automatisch gekickt (gelistete ID).")
        except Exception as e:
            print(f"❌ Fehler beim Auto-Kick: {e}")
        return

    account_age = (datetime.now(timezone.utc) - member.created_at).total_seconds()
    if account_age < 86400:
        try:
            await member.kick(reason="Anti-Join-Bot: Neuer Account zu jung")
            print(f"🥾 {member} wurde wegen jungem Account gekickt.")
        except Exception as e:
            print(f"❌ Fehler beim Kick (Anti-Join-Bot): {e}")

@bot.event
async def on_webhooks_update(channel):
    print(f"🔄 Webhook Update erkannt in {channel.name}")
    await asyncio.sleep(0)
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
            await member.kick(reason="🧪 Rolle gelöscht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Rolle gelöscht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_member_remove(member):
    pass

# ------------------------
# TIMEOUT-ABUSE-SCHUTZ
# ------------------------

timeout_actions = {}  # {user_id: [timestamps]}
TIMEOUT_WINDOW = 15  # Sekunden
TIMEOUT_THRESHOLD = 5  # Timeouts

@bot.event
async def on_audit_log_entry_create(entry: discord.AuditLogEntry):
    if entry.action != discord.AuditLogAction.member_update:
        return

    if not entry.user or is_whitelisted(entry.user.id):
        return

    changes = entry.changes.after if hasattr(entry, "changes") else {}
    if "communication_disabled_until" not in str(changes):
        return

    now = datetime.now(timezone.utc).timestamp()
    user_id = entry.user.id

    timestamps = timeout_actions.get(user_id, [])
    timestamps = [t for t in timestamps if now - t <= TIMEOUT_WINDOW]
    timestamps.append(now)
    timeout_actions[user_id] = timestamps

    if len(timestamps) >= TIMEOUT_THRESHOLD:
        guild = entry.guild
        member = guild.get_member(user_id)
        if member:
            try:
                await member.kick(reason="🛡️ Timeout-Spam: 5 Nutzer in 15 Sekunden")
                print(f"🥾 {member} wurde wegen Timeout-Spam gekickt.")
            except Exception as e:
                print(f"❌ Fehler beim Kick wegen Timeout-Spam: {e}")

bot.run(TOKEN)
