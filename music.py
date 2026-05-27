import discord
from discord.ext import commands
import yt_dlp
import asyncio

# Setup yt-dlp options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # Enable playlists
    'nocheckcertificate': True,
    'ignoreerrors': True,  # Skip unplayable videos in playlists
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options_templates = {
    'low': {'options': '-vn -b:a 64k', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'},
    'basic': {'options': '-vn -b:a 128k', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

def create_progress_bar(current, total, length=15):
    if total == 0:
        return "🔘" + "▬" * (length - 1)
    progress = int((current / total) * length)
    progress = min(max(progress, 0), length)
    bar = "▬" * progress + "🔘" + "▬" * (length - progress - 1)
    return bar

def format_duration(seconds):
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)

    @classmethod
    async def from_query(cls, query, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        if not query.startswith('http'):
            query = f'ytsearch:{query}'
            
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=not stream))

        if not data:
            raise Exception("Lagu tidak ditemukan atau tidak bisa diputar.")

        # If it's a playlist, return a list of sources
        if 'entries' in data:
            valid_entries = [e for e in data['entries'] if e]
            sources = []
            for entry in valid_entries:
                filename = entry['url'] if stream else ytdl.prepare_filename(entry)
                sources.append(cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=entry))
            return sources
        else:
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return [cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)]

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current_song = {}
        self.session_owners = {}
        self.now_playing_messages = {}
        self.skip_votes = {}
        self.history = {}
        self.audio_quality = {}

    def get_ffmpeg_options(self, guild_id):
        quality = self.audio_quality.get(guild_id, 'basic')
        return dict(ffmpeg_options_templates[quality])

    def is_owner(self, ctx):
        owner_id = self.session_owners.get(ctx.guild.id)
        if not owner_id:
            return True
        if owner_id == ctx.author.id or ctx.author.guild_permissions.administrator:
            return True
        return False

    def play_next(self, guild):
        if self.current_song.get(guild.id):
            if guild.id not in self.history:
                self.history[guild.id] = []
            self.history[guild.id].insert(0, self.current_song[guild.id])
            if len(self.history[guild.id]) > 10:
                self.history[guild.id].pop()

        if guild.id in self.queues and len(self.queues[guild.id]) > 0:
            player = self.queues[guild.id].pop(0)
            self.current_song[guild.id] = player
            
            # Reset vote skips for new song
            self.skip_votes[guild.id] = set()
            
            guild.voice_client.play(player, after=lambda e: self.play_next(guild))
            
            embed = discord.Embed(description=f"🎵 Started playing **[{player.title}]({player.url})** by **{player.uploader}**", color=0x2b2d31)
            
            asyncio.run_coroutine_threadsafe(self.update_now_playing(guild, embed=embed), self.bot.loop)
        else:
            self.current_song[guild.id] = None
            self.session_owners.pop(guild.id, None)

    async def update_now_playing(self, guild, content=None, embed=None):
        channel = None
        # Try to edit existing message to avoid spam
        if guild.id in self.now_playing_messages:
            msg, channel = self.now_playing_messages[guild.id]
            try:
                await msg.edit(content=content, embed=embed)
                return
            except:
                pass
                
        # Send new message if edit fails or no previous message
        if channel:
            new_msg = await channel.send(content=content, embed=embed)
            self.now_playing_messages[guild.id] = (new_msg, channel)

    @commands.hybrid_command(name='play', aliases=['p'], help='Memutar lagu atau playlist')
    async def play(self, ctx, *, query: str):
        if ctx.guild.id in self.session_owners and not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Saat ini sesi musik dipegang oleh <@{owner_id}>. Hanya pemilik sesi yang bisa menambahkan lagu! Minta mereka untuk mentransfer sesi dengan `/transfer` atau `{ctx.prefix}transfer @user`.")

        if not ctx.author.voice:
            return await ctx.send("Kamu tidak berada di voice channel!")

        channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            owner_id = self.session_owners.get(ctx.guild.id)
            if owner_id:
                return await ctx.send(f"❌ Bot sedang digunakan oleh <@{owner_id}> di channel **{ctx.voice_client.channel.name}**!")
            else:
                return await ctx.send(f"❌ Bot sedang digunakan di channel **{ctx.voice_client.channel.name}**!")

        # Defer if it's a slash command to prevent timeout
        if ctx.interaction:
            await ctx.defer()
        else:
            await ctx.typing()

        try:
            ff_opts = self.get_ffmpeg_options(ctx.guild.id)
            players = await YTDLSource.from_query(query, loop=self.bot.loop, stream=True, custom_ffmpeg_options=ff_opts)
            
            if ctx.guild.id not in self.session_owners:
                self.session_owners[ctx.guild.id] = ctx.author.id
                await ctx.send(f"👑 **{ctx.author.mention} sekarang memegang kendali atas bot ini!**")

            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []

            # Save the text channel to send updates
            if ctx.guild.id not in self.now_playing_messages:
                self.now_playing_messages[ctx.guild.id] = (None, ctx.channel)

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                self.queues[ctx.guild.id].extend(players)
                if len(players) > 1:
                    await ctx.send(f'**Added playlist:** {len(players)} lagu ke antrean!')
                else:
                    await ctx.send(f'**Added to queue:** {players[0].title}')
            else:
                self.current_song[ctx.guild.id] = players.pop(0)
                self.queues[ctx.guild.id].extend(players)
                self.skip_votes[ctx.guild.id] = set()
                
                ctx.voice_client.play(self.current_song[ctx.guild.id], after=lambda e: self.play_next(ctx.guild))
                
                player = self.current_song[ctx.guild.id]
                embed = discord.Embed(description=f"🎵 Started playing **[{player.title}]({player.url})** by **{player.uploader}**", color=0x2b2d31)
                
                msg = await ctx.send(embed=embed)
                self.now_playing_messages[ctx.guild.id] = (msg, ctx.channel)
                
                if len(players) > 0:
                    await ctx.send(f'(Sisa {len(players)} lagu playlist ditambahkan ke antrean)')
                    
        except Exception as e:
            await ctx.send(f"Terjadi kesalahan saat memutar lagu: {str(e)}")

    @commands.hybrid_command(name='transfer', help='Memindahkan kepemilikan sesi ke orang lain')
    async def transfer(self, ctx, member: discord.Member):
        if ctx.guild.id not in self.session_owners:
            return await ctx.send("Saat ini tidak ada sesi musik yang berjalan!")
            
        if self.is_owner(ctx):
            self.session_owners[ctx.guild.id] = member.id
            await ctx.send(f"👑 **Kendali bot telah dipindahkan kepada {member.mention}!**")
        else:
            owner_id = self.session_owners.get(ctx.guild.id)
            await ctx.send(f"❌ Hanya pemilik sesi saat ini (<@{owner_id}>) atau Admin yang bisa memindahkan kendali!")

    @commands.hybrid_command(name='pause', help='Menjeda lagu')
    async def pause(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa menjeda lagu!")

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Lagu dijeda ⏸️")
        else:
            await ctx.send("Tidak ada lagu yang sedang diputar!")

    @commands.hybrid_command(name='resume', help='Melanjutkan lagu yang dijeda')
    async def resume(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa melanjutkan lagu!")

        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Melanjutkan lagu ▶️")
        else:
            await ctx.send("Lagu sedang diputar atau tidak ada lagu!")

    @commands.hybrid_command(name='skip', aliases=['s'], help='Melewati lagu saat ini')
    async def skip(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa melewati lagu langsung. Gunakan `/voteskip`.")

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Lagu dilewati ⏭️")
        else:
            await ctx.send("Tidak ada lagu yang sedang diputar!")

    @commands.hybrid_command(name='voteskip', help='Voting untuk melewati lagu (butuh 50% user di VC)')
    async def voteskip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Tidak ada lagu yang sedang diputar!")
            
        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("Anda harus berada di VC yang sama dengan bot untuk melakukan vote!")

        if ctx.guild.id not in self.skip_votes:
            self.skip_votes[ctx.guild.id] = set()

        self.skip_votes[ctx.guild.id].add(ctx.author.id)
        
        # Hitung member di VC selain bot
        members = [m for m in ctx.voice_client.channel.members if not m.bot]
        required_votes = max(1, len(members) // 2)

        if len(self.skip_votes[ctx.guild.id]) >= required_votes:
            await ctx.send(f"Voted {len(self.skip_votes[ctx.guild.id])}/{required_votes}. Lagu dilewati! ⏭️")
            ctx.voice_client.stop()
        else:
            await ctx.send(f"Vote skip tercatat! ({len(self.skip_votes[ctx.guild.id])}/{required_votes} votes yang dibutuhkan)")

    @commands.hybrid_command(name='stop', aliases=['leave'], help='Menghentikan bot dan keluar dari VC')
    async def stop(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa menghentikan bot!")

        if ctx.voice_client:
            if ctx.guild.id in self.queues:
                self.queues[ctx.guild.id].clear()
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            self.session_owners.pop(ctx.guild.id, None)
            self.now_playing_messages.pop(ctx.guild.id, None)
            await ctx.send("Bot keluar dari voice channel 👋")
        else:
            await ctx.send("Bot tidak berada di voice channel!")

    @commands.hybrid_command(name='queue', aliases=['q'], help='Melihat antrean lagu')
    async def queue(self, ctx):
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            # Batasi tampilan antrean max 10 lagu agar pesan tidak terlalu panjang
            max_view = 10
            queue_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.queues[ctx.guild.id][:max_view])])
            if len(self.queues[ctx.guild.id]) > max_view:
                queue_list += f"\n\n*...dan {len(self.queues[ctx.guild.id]) - max_view} lagu lainnya*"
            await ctx.send(f"**Antrean Lagu:**\n{queue_list}")
        else:
            await ctx.send("Antrean kosong!")

    @commands.hybrid_command(name='remove', help='Menghapus lagu tertentu dari antrean (berdasarkan urutan /queue)')
    async def remove(self, ctx, index: int):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa menghapus lagu dari antrean!")

        if ctx.guild.id in self.queues and 0 < index <= len(self.queues[ctx.guild.id]):
            removed = self.queues[ctx.guild.id].pop(index - 1)
            await ctx.send(f"Berhasil menghapus **{removed.title}** dari antrean.")
        else:
            await ctx.send("Urutan lagu tidak valid!")

    @commands.hybrid_command(name='clear', help='Mengosongkan seluruh antrean')
    async def clear(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"❌ Hanya pemilik sesi (<@{owner_id}>) atau Admin yang bisa mengosongkan antrean!")

        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id].clear()
            await ctx.send("🗑️ Seluruh antrean berhasil dikosongkan!")
        else:
            await ctx.send("Antrean sudah kosong!")

    @commands.hybrid_command(name='history', help='Melihat 10 lagu yang terakhir diputar')
    async def history(self, ctx):
        if ctx.guild.id in self.history and len(self.history[ctx.guild.id]) > 0:
            history_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.history[ctx.guild.id])])
            embed = discord.Embed(title="📜 Riwayat Lagu", description=history_list, color=0x2b2d31)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Riwayat lagu kosong!")

    @commands.hybrid_command(name='quality', help='Mengatur kualitas audio (low/basic)')
    async def quality(self, ctx, level: str):
        level = level.lower()
        if level not in ['low', 'basic']:
            return await ctx.send("Pilihan kualitas hanya: `low` (64kbps) atau `basic` (128kbps).")
            
        self.audio_quality[ctx.guild.id] = level
        await ctx.send(f"🎚️ Kualitas audio diatur ke **{level.upper()}**! (Akan berlaku pada lagu berikutnya)")

async def setup(bot):
    await bot.add_cog(Music(bot))
