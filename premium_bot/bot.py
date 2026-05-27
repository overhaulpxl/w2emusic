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
BOT_PREFIX = os.getenv('BOT_PREFIX', 'p!')
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} premium command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{BOT_PREFIX}play | /play (Premium)"))

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
