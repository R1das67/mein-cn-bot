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
    await asyncio.sleep(0)
    if is_whitelisted(member.id):
        return
    guild = member.guild
    print(f"➕ Neuer Nutzer: {member}")
    try:
        # Default Rolle vergeben
        role = discord.utils.get(guild.roles, id=1077726012875114098)
        if role:
            await member.add_roles(role, reason="👋 Standardrolle bei Join")
        # Benutzername anpassen
        new_name = f"{member.name} | 👾"
        await member.edit(nick=new_name, reason="✏ Nick beim Join angepasst")
    except Exception as e:
        print(f"❌ Fehler bei Join-Aktionen: {e}")

# ------------------------
# BACKUP UND RESET
# ------------------------

@tree.command(name="backup", description="Sichere alle Server-Kanäle und Kategorien.")
@commands.has_permissions(administrator=True)
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    backup_data = {
        "categories": [],
        "text_channels": [],
        "voice_channels": [],
    }

    # Kategorien sichern
    for category in guild.categories:
        backup_data["categories"].append({
            "name": category.name,
            "position": category.position,
            "nsfw": category.nsfw,
            "id": category.id,
        })

    # Text-Kanäle sichern
    for text_channel in guild.text_channels:
        backup_data["text_channels"].append({
            "name": text_channel.name,
            "topic": text_channel.topic,
            "position": text_channel.position,
            "category": text_channel.category.name if text_channel.category else None,
            "nsfw": text_channel.nsfw,
            "slowmode_delay": text_channel.slowmode_delay,
            "permissions": [
                (perm.target.id if hasattr(perm.target, "id") else perm.target.name, {
                    "allow": perm.overwrites.pair()[0],
                    "deny": perm.overwrites.pair()[1]
                }) for perm in text_channel.overwrites.items()
            ],
            "id": text_channel.id,
        })

    # Voice-Kanäle sichern
    for voice_channel in guild.voice_channels:
        backup_data["voice_channels"].append({
            "name": voice_channel.name,
            "position": voice_channel.position,
            "category": voice_channel.category.name if voice_channel.category else None,
            "bitrate": voice_channel.bitrate,
            "user_limit": voice_channel.user_limit,
            "permissions": [
                (perm.target.id if hasattr(perm.target, "id") else perm.target.name, {
                    "allow": perm.overwrites.pair()[0],
                    "deny": perm.overwrites.pair()[1]
                }) for perm in voice_channel.overwrites.items()
            ],
            "id": voice_channel.id,
        })

    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=4, ensure_ascii=False)
        await interaction.followup.send("✅ Backup wurde erfolgreich erstellt!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Backup fehlgeschlagen: {e}", ephemeral=True)


@tree.command(name="reset", description="Löscht alle Kanäle und erstellt sie aus dem Backup neu.")
@commands.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    if not os.path.exists(BACKUP_FILE):
        await interaction.followup.send("❌ Kein Backup gefunden. Bitte erstelle ein Backup.", ephemeral=True)
        return

    with open(BACKUP_FILE, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    # Kanäle löschen parallel
    delete_tasks = [channel.delete(reason="🔄 Server Reset") for channel in list(guild.channels)]
    results = await asyncio.gather(*delete_tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            print(f"❌ Fehler beim Löschen eines Kanals: {res}")

    # Kategorien parallel erstellen
    create_category_tasks = [
        guild.create_category(
            name=cat_data["name"],
            position=cat_data["position"],
            nsfw=cat_data.get("nsfw", False),
            reason="🔄 Server Reset Backup"
        )
        for cat_data in sorted(backup_data.get("categories", []), key=lambda c: c["position"])
    ]
    created_categories = await asyncio.gather(*create_category_tasks, return_exceptions=True)

    # Kategorie-Name -> Kategorie Objekt Mapping
    categories_map = {}
    for idx, cat_result in enumerate(created_categories):
        if isinstance(cat_result, discord.CategoryChannel):
            categories_map[backup_data["categories"][idx]["name"]] = cat_result
        else:
            print(f"❌ Fehler beim Erstellen der Kategorie: {cat_result}")

    # Text-Kanäle parallel erstellen
    create_text_tasks = []
    for chan_data in backup_data.get("text_channels", []):
        overwrites = {}
        for target_id, perm in chan_data.get("permissions", []):
            # Zielobjekt (Role/User) finden
            target = guild.get_role(target_id) or guild.get_member(target_id) or None
            if not target:
                continue
            allow = discord.Permissions(perm.get("allow", 0))
            deny = discord.Permissions(perm.get("deny", 0))
            overwrites[target] = discord.PermissionOverwrite.from_pair(allow.value, deny.value)

        category = categories_map.get(chan_data.get("category"))
        create_text_tasks.append(
            guild.create_text_channel(
                name=chan_data["name"],
                topic=chan_data.get("topic"),
                position=chan_data["position"],
                category=category,
                nsfw=chan_data.get("nsfw", False),
                slowmode_delay=chan_data.get("slowmode_delay", 0),
                overwrites=overwrites,
                reason="🔄 Server Reset Backup"
            )
        )
    text_results = await asyncio.gather(*create_text_tasks, return_exceptions=True)
    for res in text_results:
        if isinstance(res, Exception):
            print(f"❌ Fehler beim Erstellen eines Text-Kanals: {res}")

    # Voice-Kanäle parallel erstellen
    create_voice_tasks = []
    for chan_data in backup_data.get("voice_channels", []):
        overwrites = {}
        for target_id, perm in chan_data.get("permissions", []):
            target = guild.get_role(target_id) or guild.get_member(target_id) or None
            if not target:
                continue
            allow = discord.Permissions(perm.get("allow", 0))
            deny = discord.Permissions(perm.get("deny", 0))
            overwrites[target] = discord.PermissionOverwrite.from_pair(allow.value, deny.value)

        category = categories_map.get(chan_data.get("category"))
        create_voice_tasks.append(
            guild.create_voice_channel(
                name=chan_data["name"],
                position=chan_data["position"],
                category=category,
                bitrate=chan_data.get("bitrate", 64000),
                user_limit=chan_data.get("user_limit", 0),
                overwrites=overwrites,
                reason="🔄 Server Reset Backup"
            )
        )
    voice_results = await asyncio.gather(*create_voice_tasks, return_exceptions=True)
    for res in voice_results:
        if isinstance(res, Exception):
            print(f"❌ Fehler beim Erstellen eines Voice-Kanals: {res}")

    await interaction.followup.send("✅ Server Reset abgeschlossen!", ephemeral=True)

# ------------------------
# BOT STARTEN
# ------------------------

bot.run(TOKEN)
