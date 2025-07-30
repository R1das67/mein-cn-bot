import discord
from discord import app_commands
import asyncio

# ----------- WHITELIST -----------
WHITELIST = {
    843180408152784936,  # Ersetze mit echten User-IDs
    1159469934989025290,
}

# ----------- BACKUP DATEN -----------
backup_data = {}

def serialize_channel(channel: discord.abc.GuildChannel):
    return {
        "name": channel.name,
        "type": channel.type,
        "position": channel.position,
        "category_id": channel.category_id,
    }

async def create_channel_from_backup(guild: discord.Guild, data):
    category = guild.get_channel(data["category_id"]) if data["category_id"] else None
    if data["type"] == discord.ChannelType.text:
        return await guild.create_text_channel(name=data["name"], position=data["position"], category=category)
    elif data["type"] == discord.ChannelType.voice:
        return await guild.create_voice_channel(name=data["name"], position=data["position"], category=category)
    elif data["type"] == discord.ChannelType.category:
        return await guild.create_category(name=data["name"], position=data["position"])

# ----------- BEFEHLE REGISTRIEREN -----------
def setup_backup_commands(tree: app_commands.CommandTree):

    @tree.command(name="backup", description="Erstelle ein Backup der Kanäle.")
    async def backup(interaction: discord.Interaction):
        if interaction.user.id not in WHITELIST:
            await interaction.response.send_message("❌ Du bist nicht autorisiert.", ephemeral=True)
            return

        guild = interaction.guild
        backup_data[guild.id] = [serialize_channel(c) for c in sorted(guild.channels, key=lambda c: c.position)]
        await interaction.response.send_message(f"✅ Backup gespeichert für {len(backup_data[guild.id])} Kanäle.")

    @tree.command(name="reset", description="Stellt Kanäle aus Backup wieder her.")
    async def reset(interaction: discord.Interaction):
        if interaction.user.id not in WHITELIST:
            await interaction.response.send_message("❌ Du bist nicht autorisiert.", ephemeral=True)
            return

        guild = interaction.guild
        if guild.id not in backup_data:
            await interaction.response.send_message("⚠️ Kein Backup vorhanden.", ephemeral=True)
            return

        await interaction.response.send_message("🔄 Reset wird durchgeführt...", ephemeral=True)

        for channel in guild.channels:
            try:
                await channel.delete(reason="Reset durch Bot")
            except:
                pass

        await asyncio.sleep(2)

        channel_data = backup_data[guild.id]
        categories = {c["name"]: await create_channel_from_backup(guild, c) for c in channel_data if c["type"] == discord.ChannelType.category}

        for ch in channel_data:
            if ch["type"] != discord.ChannelType.category:
                if ch["category_id"]:
                    cat = discord.utils.get(guild.categories, id=ch["category_id"])
                    if cat and cat.name in categories:
                        ch["category_id"] = categories[cat.name].id
                    else:
                        ch["category_id"] = None
                await create_channel_from_backup(guild, ch)
        
        await interaction.followup.send("✅ Reset abgeschlossen.")

