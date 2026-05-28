import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
import logging
import sys

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Create bot instance with dynamic prefix
BOT_PREFIX = os.getenv('BOT_PREFIX', 'w!')
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    logger.info('------')
    # FIX: Removed auto-sync on ready to prevent Discord API rate limits.
    # Commands should be synced manually using the !sync command.
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{BOT_PREFIX}play | /play"))

@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, 'on_error'):
        return
        
    error = getattr(error, 'original', error)
    
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command tidak ditemukan. Coba `w!help`.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Argumen tidak lengkap. Penggunaan: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Tunggu **{error.retry_after:.1f}s** sebelum pakai command ini lagi.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Argumen tidak valid.")
    elif isinstance(error, commands.CheckFailure):
        pass # Handle in specific commands if needed
    else:
        logger.error(f"Error executing command {ctx.command}: {error}", exc_info=error)
        try:
            await ctx.send("Terjadi kesalahan internal.")
        except:
            pass

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Tunggu **{error.retry_after:.1f}s** sebelum pakai command ini lagi."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "Izin ditolak."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "Bot tidak punya izin."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
    elif isinstance(error, app_commands.CheckFailure):
        msg = "Syarat command tidak terpenuhi."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
    else:
        logger.error(f"App command error: {error}", exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("Terjadi kesalahan internal.", ephemeral=True)
            else:
                await interaction.followup.send("Terjadi kesalahan internal.", ephemeral=True)
        except:
            pass

# FIX: Added a manual sync command for the bot owner
@bot.command(name='sync', help='Sync slash commands (Owner only)')
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync commands: {e}")

class HelpSelect(discord.ui.Select):
    def __init__(self, bot_instance):
        self.bot_instance = bot_instance
        options = [
            discord.SelectOption(label="Quick Start", description="Command paling penting buat mulai"),
            discord.SelectOption(label="Music", description="Play lagu, playlist, dan now playing"),
            discord.SelectOption(label="Queue", description="Lihat dan atur antrean"),
            discord.SelectOption(label="Controls", description="Pause, resume, skip, stop"),
            discord.SelectOption(label="Tips", description="Format link dan batasan bot")
        ]
        super().__init__(placeholder="Pilih kategori bantuan...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(title=f"Bantuan: {category}", color=0x2b2d31)
        
        if category == "Quick Start":
            embed.description = (
                "`w!play <judul/link>` — Putar lagu atau playlist.\n"
                "`w!queue` — Lihat antrean.\n"
                "`w!skip` — Lewati lagu.\n"
                "`w!stop` — Stop playback."
            )
        elif category == "Music":
            embed.description = (
                "`w!play <judul/link>` — Putar lagu, video YouTube, atau playlist.\n"
                "`w!nowplaying` — Lihat lagu yang sedang diputar.\n"
                "`w!history` — Lihat riwayat lagu."
            )
        elif category == "Queue":
            embed.description = (
                "`w!queue` — Lihat antrean.\n"
                "`w!remove <nomor>` — Hapus lagu dari antrean.\n"
                "`w!clear` — Kosongkan antrean."
            )
        elif category == "Controls":
            embed.description = (
                "`w!pause` — Jeda lagu.\n"
                "`w!resume` — Lanjutkan lagu.\n"
                "`w!skip` — Lewati lagu.\n"
                "`w!stop` — Stop dan bersihkan queue.\n"
                "`w!volume <1-100>` — Atur volume, hanya jika command ini memang ada."
            )
        elif category == "Tips":
            embed.description = (
                "- Bisa pakai judul lagu langsung.\n"
                "- Bisa pakai link YouTube video.\n"
                "- Bisa pakai link YouTube playlist.\n"
                "- Link `watch?v=...&list=...` dibaca sebagai playlist.\n"
                "- Durasi maksimal lagu adalah 2 jam."
            )
            
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot_instance))

@bot.hybrid_command(name='help', help='Lihat daftar command')
@commands.cooldown(1, 3, commands.BucketType.user)
async def help_command(ctx):
    embed = discord.Embed(
        title="W2E Music", 
        description="Music bot simpel buat muter lagu, playlist, dan ngatur queue.", 
        color=0x2b2d31
    )
    
    embed.add_field(name="Prefix", value="`w!`", inline=False)
    embed.add_field(name="Mulai cepat", value="`w!play <judul/link>`", inline=False)
    
    if ctx.bot.user.display_avatar:
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        
    embed.set_footer(text="Pilih kategori di bawah untuk detail command.")
        
    view = HelpView(bot)
    await ctx.send(embed=embed, view=view)

async def load_extensions():
    await bot.load_extension('music')

async def main():
    async with bot:
        await load_extensions()
        if TOKEN and TOKEN != "your_bot_token_here":
            await bot.start(TOKEN)
        else:
            logger.error("Please set your DISCORD_TOKEN in the .env file.")

if __name__ == '__main__':
    asyncio.run(main())
