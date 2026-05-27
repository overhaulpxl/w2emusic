import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

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
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    # FIX: Removed auto-sync on ready to prevent Discord API rate limits.
    # Commands should be synced manually using the !sync command.
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{BOT_PREFIX}play | /play"))

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
        options = []
        for cmd in sorted(bot_instance.commands, key=lambda c: c.name):
            if cmd.name in ['sync', 'help'] or cmd.hidden:
                continue
            
            desc = (cmd.help[:97] + '...') if cmd.help and len(cmd.help) > 100 else (cmd.help or "Tidak ada deskripsi")
            options.append(discord.SelectOption(
                label=f"/{cmd.name}", 
                description=desc,
                emoji="🎵"
            ))
            
        super().__init__(placeholder="Pilih perintah untuk melihat detail...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cmd_name = self.values[0].replace('/', '')
        cmd = self.bot_instance.get_command(cmd_name)
        
        if not cmd:
            return await interaction.response.send_message("Perintah tidak ditemukan!", ephemeral=True)
            
        embed = discord.Embed(
            title=f"Detail Perintah: /{cmd.name}", 
            description=cmd.help or "Tidak ada deskripsi", 
            color=0x2b2d31
        )
        if cmd.aliases:
            embed.add_field(name="Bisa juga diketik dengan alias:", value=", ".join([f"`{a}`" for a in cmd.aliases]), inline=False)
            
        embed.set_footer(text="Gunakan Slash Command (/) atau Prefix untuk memanggilnya")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot_instance))

@bot.hybrid_command(name='help', help='Menampilkan daftar semua perintah bot')
async def help_command(ctx):
    embed = discord.Embed(
        title="🎵 W2E Music Bot - Help Menu", 
        description="Gunakan menu dropdown di bawah ini untuk melihat detail lengkap dari setiap perintah musik yang tersedia!\n\n**Sistem Kepemilikan (Ownership):**\nOrang pertama yang memutar lagu akan menjadi `Pemilik Sesi`. Hanya pemilik sesi (dan Admin) yang bisa menggunakan perintah `/skip`, `/stop`, `/volume`, dll.", 
        color=0x2b2d31
    )
    if ctx.bot.user.display_avatar:
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        
    # FIX: Tampilkan status ownership saat ini
    if ctx.guild:
        music_cog = ctx.bot.get_cog('Music')
        if music_cog:
            owner_id = music_cog.session_owners.get(ctx.guild.id)
            if owner_id:
                embed.add_field(name="👑 Sesi Saat Ini", value=f"Sesi musik sedang dipegang oleh <@{owner_id}>.", inline=False)
            else:
                embed.add_field(name="👑 Sesi Saat Ini", value="Belum ada sesi musik yang berjalan. Ketik `/play` untuk memulai!", inline=False)
        
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
            print("ERROR: Please set your DISCORD_TOKEN in the .env file.")

if __name__ == '__main__':
    asyncio.run(main())
