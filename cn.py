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
WHITELIST = { 843180408152784936,662596869221908480,
             830212609961754654,1159469934989025290,
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

AUTHORIZED_ROLE_ID = 1387413152865718452,1387413152873975993
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
            await member.remove_roles(*roles_to_remove, reason="Reset nach 2x Webhook-Versto\u00df")
            print(f"🔁 Rollen von {user} entfernt.")
        except Exception as e:
            print(f"❌ Fehler bei Rollenentfernung: {e}")

# ------------------------
# BACKUP / RESET SERVER
# ------------------------

# Tempor\u00e4res Backup-Storage im RAM
backup_data = {}

def serialize_channel(channel: discord.abc.GuildChannel):
    data = {
        "name": channel.name,
        "type": channel.type,  # discord.ChannelType
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

@tree.command(name="backup", description="Erstelle ein Backup aller Kan\u00e4le im Server.")
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
    await interaction.response.send_message(f"✅ Backup f\u00fcr **{guild.name}** mit {len(channels_data)} Kan\u00e4len wurde gespeichert.")

@tree.command(name="reset", description="Starte Reset-Aktion. Optionen: 'server'")
@app_commands.describe(option="Option f\u00fcr Reset, z.B. 'server'")
async def reset(interaction: discord.Interaction, option: str):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Kein Server gefunden.", ephemeral=True)
        return

    if option.lower() != "server":
        await interaction.response.send_message("❌ Unbekannte Option. Nur 'server' ist erlaubt.", ephemeral=True)
        return

    if guild.id not in backup_data:
        await interaction.response.send_message("❌ Kein Backup f\u00fcr diesen Server gefunden. Bitte erst `/backup` ausf\u00fchren.", ephemeral=True)
        return

    await interaction.response.send_message("⚠️ Starte Server Reset: Kan\u00e4le werden gel\u00f6scht und aus Backup wiederhergestellt...", ephemeral=True)

    # Kan\u00e4le l\u00f6schen
    for ch in guild.channels:
        try:
            await ch.delete(reason="Reset Server durch Bot")
        except Exception as e:
            print(f"Fehler beim L\u00f6schen von Kanal {ch.name}: {e}")

    await asyncio.sleep(5)  # Warten bis L\u00f6schungen durch sind

    channels_backup = backup_data[guild.id]

    # Kategorien zuerst erstellen
    categories = [c for c in channels_backup if c["type"] == discord.ChannelType.category]
    category_map = {}

    for cat_data in categories:
        cat = await create_channel_from_backup(guild, cat_data)
        if cat:
            category_map[cat_data["name"]] = cat

    # Dann alle anderen Kan\u00e4le, Kategorie-ID auf neue IDs mappen
    for ch_data in channels_backup:
        if ch_data["type"] == discord.ChannelType.category:
            continue

        if ch_data["category_id"]:
            orig_cat = next((c for c in categories if c["category_id"] == ch_data["category_id"]), None)
            cat_name = None
            for cat in categories:
                if cat["name"] == guild.get_channel(ch_data["category_id"]).name if guild.get_channel(ch_data["category_id"]) else None:
                    cat_name = cat["name"]
                    break
            if cat_name in category_map:
                ch_data["category_id"] = category_map[cat_name].id
            else:
                ch_data["category_id"] = None
        else:
            ch_data["category_id"] = None

        await create_channel_from_backup(guild, ch_data)

    await interaction.followup.send("✅ Server Reset abgeschlossen. Kan\u00e4le wurden wiederhergestellt.")

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
            print(f"❌ Webhook {webhook.name} gel\u00f6scht")
            if user and not is_whitelisted(user.id):
                count = webhook_violations.get(user.id, 0) + 1
                webhook_violations[user.id] = count
                print(f"⚠ Webhook-Versto\u00df #{count} von {user}")
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
                print(f"🚫 Nachricht von getimtem User {message.author} gel\u00f6scht.")
            except:
                pass
            return
        else:
            del user_timeouts[message.author.id]
    if invite_pattern.search(message.content):
        try:
            await message.delete()
            print(f"🚫 Invite-Link gel\u00f6scht von {message.author}")
        except Exception as e:
            print(f"❌ Fehler beim Invite-L\u00f6schen: {e}")
        count = invite_violations.get(message.author.id, 0) + 1
        invite_violations[message.author.id] = count
        print(f"⚠ Invite-Versto\u00df #{count} von {message.author}")
        if count >= 3:
            try:
                await message.author.timeout(duration=DELETE_TIMEOUT, reason="🔇 3x Invite-Versto\u00df")
                user_timeouts[message.author.id] = now_ts + DELETE_TIMEOUT
                print(f"⏱ {message.author} wurde f\u00fcr 1 Stunde getimeoutet.")
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
            await member.kick(reason="🧪 Rolle gel\u00f6scht ohne Erlaubnis")
            print(f"🥾 {member} wurde gekickt (Rolle gel\u00f6scht).")
        except Exception as e:
            print(f"❌ Fehler beim Kick: {e}")

@bot.event
async def on_member_remove(member):
    # Hier kann man Kick-/Ban-Logik reinbauen
    pass

bot.run(TOKEN)
