import discord
from discord.ext import commands
import yt_dlp
import asyncio
import time
import logging
import urllib.parse

logger = logging.getLogger('Music')

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
    'extract_flat': 'in_playlist',
    'extractor_args': {
        'youtube': ['player_client=android', 'player_client=default']
    }
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

import urllib.parse

def normalize_youtube_input(query):
    """
    Normalizes a YouTube URL to ensure playlists are correctly processed.
    If the query is a watch URL with a list parameter, it converts it to a pure playlist URL.
    Returns: (normalized_query, detected_type, playlist_id)
    """
    detected_type = "search_query"
    playlist_id = None
    normalized_query = query

    if not query.startswith('http'):
        return query, detected_type, None

    try:
        parsed = urllib.parse.urlparse(query)
        if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            qs = urllib.parse.parse_qs(parsed.query)
            
            # Check for playlist ID
            if 'list' in qs:
                playlist_id = qs['list'][0]
                
            if playlist_id:
                if 'watch' in parsed.path:
                    detected_type = "youtube_watch_with_playlist"
                    # Default behavior: treat watch+list as a playlist.
                    # This can be changed later if we want to allow user to pick single video vs playlist.
                    normalized_query = f"https://www.youtube.com/playlist?list={playlist_id}"
                elif 'playlist' in parsed.path:
                    detected_type = "youtube_playlist"
                    normalized_query = query
                else:
                    detected_type = "youtube_playlist"
                    normalized_query = f"https://www.youtube.com/playlist?list={playlist_id}"
            else:
                detected_type = "youtube_video"
    except Exception:
        pass
        
    return normalized_query, detected_type, playlist_id

class TrackInfo:
    def __init__(self, data, is_lazy=False, requester=None):
        self.data = data
        self.title = data.get('title', 'Unknown Title')
        self.uploader = data.get('uploader', 'Unknown Uploader')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.requester = requester
        self.is_lazy = is_lazy
        
        if is_lazy:
            self.url = data.get('url') or data.get('webpage_url')
            if self.url and not self.url.startswith('http') and data.get('id'):
                self.url = f"https://www.youtube.com/watch?v={data['id']}"
            self.stream_url = None
        else:
            self.url = data.get('webpage_url') or data.get('url')
            self.stream_url = data.get('url')
            
        self.volume = 1.0
        self.start_time = 0

    async def resolve(self, loop):
        if not self.is_lazy:
            return
            
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(self.url, download=False))
        if not data:
            raise Exception("Lagu tidak tersedia atau private.")
            
        duration = data.get('duration', 0)
        if duration and duration > 7200:
            raise Exception("Lagu ini terlalu panjang. Maksimal durasi 2 jam.")
            
        self.stream_url = data.get('url')
        self.data = data
        self.duration = duration
        self.is_lazy = False

    def create_source(self, ff_opts):
        if not self.stream_url:
            raise Exception("Stream URL belum di-resolve")
        source = discord.FFmpegPCMAudio(self.stream_url, **ff_opts)
        return discord.PCMVolumeTransformer(source, self.volume)

    @classmethod
    async def from_query(cls, query, loop=None, requester=None):
        loop = loop or asyncio.get_event_loop()
        
        normalized_query, detected_type, playlist_id = normalize_youtube_input(query)
        
        # Log safe query info
        safe_query = query.split('&')[0] if '&' in query else query
        logger.info(f"Query parsed | Original: {safe_query} | Normalized: {normalized_query} | Type: {detected_type} | Playlist ID: {playlist_id}")
        
        is_playlist = (playlist_id is not None)

        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(normalized_query, download=False))
        except Exception as e:
            if is_playlist and playlist_id:
                logger.warning(f"yt-dlp extract_info failed for {normalized_query}, trying fallback with playlist_id {playlist_id}")
                fallback_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                try:
                    fallback_opts = dict(ytdl_format_options)
                    fallback_opts.pop('extractor_args', None)
                    fallback_ytdl = yt_dlp.YoutubeDL(fallback_opts)
                    data = await loop.run_in_executor(None, lambda: fallback_ytdl.extract_info(fallback_url, download=False))
                except Exception as fallback_e:
                    logger.exception(f"Fallback extraction also failed for playlist {playlist_id}: {fallback_e}")
                    raise Exception("Gagal memproses playlist. Coba playlist lain atau pastikan playlist bersifat publik.")
            else:
                logger.exception(f"yt-dlp extract_info failed for {normalized_query}: {e}")
                raise Exception("Gagal mengambil lagu. Coba judul atau link lain.")

        if not data:
            if is_playlist:
                raise Exception("Gagal memproses playlist. Coba playlist lain atau pastikan playlist bersifat publik.")
            raise Exception("Gagal mengambil lagu. Coba judul atau link lain.")

        if 'entries' in data:
            valid_entries = [e for e in data['entries'] if e]
            sources = []
            skipped = 0
            
            logger.info(f"Playlist detected. URL: {normalized_query} | ID: {playlist_id} | yt-dlp version: {yt_dlp.version.__version__}")
            
            for entry in valid_entries:
                duration = entry.get('duration', 0)
                if duration and duration > 7200:
                    skipped += 1
                    continue
                track = cls(entry, is_lazy=True, requester=requester)
                sources.append(track)
            
            logger.info(f"Playlist resolved: {len(data['entries'])} total, {len(sources)} valid, {skipped} skipped.")
            if not sources:
                raise Exception("Semua lagu dalam playlist melebihi batas durasi 2 jam atau invalid.")
            return sources
        else:
            duration = data.get('duration', 0)
            if duration and duration > 7200:
                raise Exception("Lagu ini terlalu panjang. Maksimal durasi 2 jam.")
            track = cls(data, is_lazy=False, requester=requester)
            return [track]

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
        # FIX: Track idle timers and persistent volumes per guild
        self.idle_timers = {}
        self.volumes = {}
        self.play_locks = {}

    def get_nowplaying_embed(self, guild):
        player = self.current_song.get(guild.id)
        if not player:
            embed = discord.Embed(title="Now Playing", description="Tidak ada lagu yang sedang diputar.", color=0x2b2d31)
            return embed

        duration = player.duration
        elapsed = 0
        if hasattr(player, 'start_time') and player.start_time > 0:
            elapsed = int(time.time() - player.start_time)
            if duration and elapsed > duration:
                elapsed = duration

        progress_bar = create_progress_bar(elapsed, duration)
        time_text = f"{format_duration(elapsed)} / {format_duration(duration) if duration else '??:??'}"

        voice_client = guild.voice_client
        status = "Paused ⏸️" if voice_client and voice_client.is_paused() else "Playing ▶️"
        
        queues = self.queues.get(guild.id, [])
        next_song = queues[0].title if queues else "Tidak ada lagu berikutnya"

        embed = discord.Embed(
            title="Now Playing",
            description=f"**[{player.title}]({player.url})**",
            color=0x2b2d31
        )
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
            
        req = player.requester.mention if player.requester else "Unknown"
        
        embed.add_field(name="Requester", value=req, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Progress", value=f"`{time_text}`\n{progress_bar}", inline=False)
        embed.add_field(name="Next", value=next_song, inline=False)
        embed.set_footer(text="W2E Music")
        return embed

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
        # FIX: Schedule task safely and attach error handler to prevent silent crashes
        self.bot.loop.call_soon_threadsafe(self._schedule_play_next, guild)

    def _schedule_play_next(self, guild):
        task = asyncio.create_task(self.play_next_async(guild))
        task.add_done_callback(lambda t: t.exception() and logger.error(f"play_next_async error: {t.exception()}", exc_info=t.exception()))

    async def play_next_async(self, guild):
        # FIX: Abort playback logic if the bot has left or is leaving the VC
        if not guild.voice_client or not guild.voice_client.is_connected():
            return
            
        # FIX: Cancel any existing idle timer for this guild
        if guild.id in self.idle_timers:
            self.idle_timers[guild.id].cancel()
            self.idle_timers.pop(guild.id, None)
        if self.current_song.get(guild.id):
            if guild.id not in self.history:
                self.history[guild.id] = []
            self.history[guild.id].insert(0, self.current_song[guild.id])
            if len(self.history[guild.id]) > 10:
                self.history[guild.id].pop()

        if guild.id in self.queues and len(self.queues[guild.id]) > 0:
            track = self.queues[guild.id].pop(0)
            self.current_song[guild.id] = track
            self.skip_votes[guild.id] = set()
            
            try:
                if track.is_lazy:
                    await track.resolve(self.bot.loop)
                    
                track.volume = self.volumes.get(guild.id, 100) / 100.0
                ff_opts = self.get_ffmpeg_options(guild.id)
                source = track.create_source(ff_opts)
                
                track.start_time = time.time()
                guild.voice_client.play(source, after=lambda e: self.play_next(guild))
                
                # Check for idle timer and cancel it
                if guild.id in self.idle_timers:
                    self.idle_timers[guild.id].cancel()
                    self.idle_timers.pop(guild.id, None)
                    
                # Update now playing message
                channel = self.now_playing_messages[guild.id][1]
                if channel:
                    embed = self.get_nowplaying_embed(guild)
                    view = NowPlayingView(self, guild)
                    new_msg = await channel.send(embed=embed, view=view)
                    view.message = new_msg

                    
                    old_msg = self.now_playing_messages[guild.id][0]
                    if old_msg:
                        try:
                            await old_msg.delete()
                        except:
                            pass
                    self.now_playing_messages[guild.id] = (new_msg, channel)
            except Exception as e:
                logger.error(f"Failed to play track {track.url}: {e}", exc_info=True)
                channel = self.now_playing_messages[guild.id][1]
                if channel:
                    await channel.send(f"Gagal memutar **{track.title}**. Melanjutkan ke lagu berikutnya...")
                self._schedule_play_next(guild)
        else:
            self.current_song[guild.id] = None
            self.session_owners.pop(guild.id, None)
            
            # FIX: Idle Timeout - Disconnect if nothing is played for 3 minutes without race conditions
            embed = discord.Embed(title="Queue", description="Queue masih kosong.", color=0x2b2d31)
            embed.add_field(name="Tambah lagu", value=f"`{self.bot.command_prefix}play <judul/link>`")
            await self.update_now_playing(guild, embed=embed)
            
            async def idle_timer():
                try:
                    await asyncio.sleep(180)
                    if guild.voice_client and not guild.voice_client.is_playing() and (guild.id not in self.queues or len(self.queues[guild.id]) == 0):
                        await guild.voice_client.disconnect()
                except asyncio.CancelledError:
                    pass # Cancelled because a new song was played
            
            self.idle_timers[guild.id] = asyncio.create_task(idle_timer())

    async def update_now_playing(self, guild, content=None, embed=None, view=None):
        channel = None
        # Try to edit existing message to avoid spam
        if guild.id in self.now_playing_messages:
            msg, channel = self.now_playing_messages[guild.id]
            try:
                if msg:
                    await msg.edit(content=content, embed=embed, view=view)
                    return
            except:
                pass
                
        # Send new message if edit fails or no previous message
        if channel:
            new_msg = await channel.send(content=content, embed=embed, view=view)
            self.now_playing_messages[guild.id] = (new_msg, channel)

    @commands.hybrid_command(name='play', aliases=['p'], help='Memutar lagu atau playlist')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def play(self, ctx, *, query: str):
        if ctx.guild.id in self.session_owners and not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if not ctx.author.voice:
            return await ctx.send("Masuk voice channel dulu.")

        channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            return await ctx.send("Bot sedang digunakan di voice channel lain.")

        if ctx.interaction:
            await ctx.defer()
        else:
            await ctx.typing()

        try:
            players = await TrackInfo.from_query(query, loop=self.bot.loop, requester=ctx.author)
        except Exception as e:
            msg = str(e)
            if not msg.startswith("Gagal") and not msg.startswith("Lagu") and not msg.startswith("Semua"):
                 msg = "Gagal mengambil lagu. Coba judul atau link lain."
            return await ctx.send(msg)

        if ctx.guild.id not in self.play_locks:
            self.play_locks[ctx.guild.id] = asyncio.Lock()
            
        async with self.play_locks[ctx.guild.id]:
            if ctx.guild.id not in self.session_owners:
                self.session_owners[ctx.guild.id] = ctx.author.id

            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []

            if ctx.guild.id not in self.now_playing_messages:
                self.now_playing_messages[ctx.guild.id] = (None, ctx.channel)

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                self.queues[ctx.guild.id].extend(players)
                if len(players) > 1:
                    await ctx.send(f"📜 Playlist terdeteksi. Menambahkan **{len(players)} lagu** ke antrean.\nLagu akan dimuat saat giliran diputar.")
                else:
                    await ctx.send(f"Masuk queue: **{players[0].title}**")
            else:
                self.current_song[ctx.guild.id] = players.pop(0)
                track = self.current_song[ctx.guild.id]
                self.queues[ctx.guild.id].extend(players)
                self.skip_votes[ctx.guild.id] = set()
                
                try:
                    if track.is_lazy:
                        await track.resolve(self.bot.loop)
                    
                    track.volume = self.volumes.get(ctx.guild.id, 100) / 100.0
                    ff_opts = self.get_ffmpeg_options(ctx.guild.id)
                    source = track.create_source(ff_opts)
                    
                    if ctx.guild.id in self.idle_timers:
                        self.idle_timers[ctx.guild.id].cancel()
                        self.idle_timers.pop(ctx.guild.id, None)
                    
                    track.start_time = time.time()
                    ctx.voice_client.play(source, after=lambda e: self.play_next(ctx.guild))
                    
                    embed = self.get_nowplaying_embed(ctx.guild)
                    view = NowPlayingView(self, ctx.guild)
                    msg = await ctx.send(embed=embed, view=view)
                    view.message = msg
                    self.now_playing_messages[ctx.guild.id] = (msg, ctx.channel)
                except Exception as e:
                    logger.error(f"Failed to play initial track {track.url}: {e}", exc_info=True)
                    await ctx.send(f"Gagal memutar **{track.title}**. Melanjutkan antrean...")
                    self._schedule_play_next(ctx.guild)
                
                if len(players) > 0:
                    await ctx.send(f"📜 Playlist terdeteksi. Menambahkan **{len(players)} lagu** ke antrean.\nLagu akan dimuat saat giliran diputar.")

    @commands.hybrid_command(name='transfer', help='Memindahkan kepemilikan sesi')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def transfer(self, ctx, member: discord.Member):
        if ctx.guild.id not in self.session_owners:
            return await ctx.send("Tidak ada sesi yang berjalan.")
            
        if self.is_owner(ctx):
            self.session_owners[ctx.guild.id] = member.id
            await ctx.send(f"Kepemilikan dipindah ke {member.mention}.")
        else:
            owner_id = self.session_owners.get(ctx.guild.id)
            await ctx.send(f"Hanya <@{owner_id}> yang bisa transfer sesi.")

    @commands.hybrid_command(name='pause', help='Menjeda lagu')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pause(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Playback dijeda.")
        else:
            await ctx.send("Tidak ada lagu yang diputar.")

    @commands.hybrid_command(name='resume', help='Melanjutkan lagu yang dijeda')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def resume(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Playback dilanjutkan.")
        else:
            await ctx.send("Tidak ada lagu yang sedang dijeda.")

    @commands.hybrid_command(name='skip', aliases=['s'], help='Melewati lagu saat ini')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def skip(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Lagu dilewati.")
        else:
            await ctx.send("Tidak ada lagu yang diputar.")

    @commands.hybrid_command(name='voteskip', help='Voting untuk melewati lagu (butuh 50% user di VC)')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def voteskip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Tidak ada lagu yang diputar.")
            
        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("Masuk voice channel bot dulu.")

        if ctx.guild.id not in self.skip_votes:
            self.skip_votes[ctx.guild.id] = set()

        self.skip_votes[ctx.guild.id].add(ctx.author.id)
        
        members = [m for m in ctx.voice_client.channel.members if not m.bot]
        required_votes = max(1, (len(members) + 1) // 2)

        if len(self.skip_votes[ctx.guild.id]) >= required_votes:
            await ctx.send(f"⏭️ Lagu dilewati. ({len(self.skip_votes[ctx.guild.id])}/{required_votes} votes)")
            ctx.voice_client.stop()
        else:
            await ctx.send(f"Vote skip dicatat: {len(self.skip_votes[ctx.guild.id])}/{required_votes} votes.")

    @commands.hybrid_command(name='stop', aliases=['leave'], help='Menghentikan bot dan keluar dari VC')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def stop(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.voice_client:
            if ctx.guild.id in self.queues:
                self.queues[ctx.guild.id].clear()
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            self.session_owners.pop(ctx.guild.id, None)
            self.now_playing_messages.pop(ctx.guild.id, None)
            await ctx.send("⏹️ Playback dihentikan dan queue dibersihkan.")
        else:
            await ctx.send("Bot tidak di voice channel.")

    @commands.hybrid_command(name='queue', aliases=['q'], help='Melihat antrean lagu')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def queue(self, ctx):
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            max_view = 10
            q = self.queues[ctx.guild.id]
            queue_list = "\n".join([f"**{i+1}.** {song.title}" for i, song in enumerate(q[:max_view])])
            if len(q) > max_view:
                queue_list += f"\n\n*+{len(q) - max_view} lagu lainnya*"
            embed = discord.Embed(title="Queue", description=queue_list, color=0x2b2d31)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Queue", description="Queue masih kosong.", color=0x2b2d31)
            embed.add_field(name="Tambah lagu", value=f"`{self.bot.command_prefix}play <judul/link>`")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name='remove', help='Menghapus lagu dari antrean')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def remove(self, ctx, index: int):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.guild.id in self.queues and 0 < index <= len(self.queues[ctx.guild.id]):
            removed = self.queues[ctx.guild.id].pop(index - 1)
            await ctx.send(f"Dihapus dari queue: **{removed.title}**")
        else:
            await ctx.send("Nomor antrean tidak valid.")

    @commands.hybrid_command(name='clear', help='Mengosongkan seluruh antrean')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def clear(self, ctx):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")

        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id].clear()
            await ctx.send("Queue dibersihkan.")
        else:
            embed = discord.Embed(title="Queue", description="Queue sudah kosong.", color=0x2b2d31)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name='history', help='Lihat riwayat lagu')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def history(self, ctx):
        if ctx.guild.id in self.history and len(self.history[ctx.guild.id]) > 0:
            history_list = "\n".join([f"**{i+1}.** {song.title}" for i, song in enumerate(self.history[ctx.guild.id])])
            embed = discord.Embed(title="History", description="10 lagu terakhir yang diputar.", color=0x2b2d31)
            embed.add_field(name="Daftar Lagu", value=history_list, inline=False)
            embed.set_footer(text="W2E Music")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="History", description="Belum ada lagu yang diputar.", color=0x2b2d31)
            embed.add_field(name="Mulai dengar lagu", value=f"`{self.bot.command_prefix}play <judul/link>`")
            embed.set_footer(text="W2E Music")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name='quality', help='Mengatur kualitas audio (low/basic)')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def quality(self, ctx, level: str):
        level = level.lower()
        if level not in ['low', 'basic']:
            return await ctx.send("Pilihan: `low` atau `basic`.")
            
        self.audio_quality[ctx.guild.id] = level
        await ctx.send(f"Kualitas audio diatur ke **{level}**.")

    # FIX: Added state cleanup when bot is disconnected to prevent memory leaks and zombie sessions
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            guild_id = member.guild.id
            if guild_id in self.queues:
                self.queues[guild_id].clear()
            self.current_song.pop(guild_id, None)
            self.session_owners.pop(guild_id, None)
            self.now_playing_messages.pop(guild_id, None)
            self.skip_votes.pop(guild_id, None)
            self.volumes.pop(guild_id, None)
            self.audio_quality.pop(guild_id, None)
            self.history.pop(guild_id, None)
            
            # FIX: Clean up any dangling idle timers when forcefully disconnected
            if guild_id in self.idle_timers:
                self.idle_timers[guild_id].cancel()
                self.idle_timers.pop(guild_id, None)

    # FIX: Added volume control functionality
    @commands.hybrid_command(name='volume', aliases=['vol'], help='Mengatur volume (0-100)')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def volume(self, ctx, volume: int):
        if not self.is_owner(ctx):
            owner_id = self.session_owners.get(ctx.guild.id)
            return await ctx.send(f"Sesi ini dimiliki oleh <@{owner_id}>.")
            
        if not ctx.voice_client:
            return await ctx.send("Bot tidak di voice channel.")
            
        if not 0 <= volume <= 100:
            return await ctx.send("Volume harus 0-100.")
            
        if ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100.0
            self.volumes[ctx.guild.id] = volume
            await ctx.send(f"Volume diatur ke **{volume}%**")
        else:
            await ctx.send("Tidak ada lagu yang diputar.")

    @commands.hybrid_command(name='nowplaying', aliases=['np'], help='Info lagu saat ini')
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def nowplaying(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            embed = discord.Embed(title="Now Playing", description="Tidak ada lagu yang sedang diputar.", color=0x2b2d31)
            embed.add_field(name="Mulai lagu", value=f"`{self.bot.command_prefix}play <judul/link>`")
            embed.set_footer(text="W2E Music")
            return await ctx.send(embed=embed)

        embed = self.get_nowplaying_embed(ctx.guild)
        view = NowPlayingView(self, ctx.guild)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        self.now_playing_messages[ctx.guild.id] = (msg, ctx.channel)

class NowPlayingView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild = guild
        self.message = None

    def check_owner(self, interaction):
        owner_id = self.cog.session_owners.get(self.guild.id)
        if not owner_id:
            return True
        if owner_id == interaction.user.id or interaction.user.guild_permissions.administrator:
            return True
        return False

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.primary, emoji="⏯️")
    async def pause_resume_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            owner_id = self.cog.session_owners.get(self.guild.id)
            return await interaction.response.send_message(f"Sesi ini dimiliki oleh <@{owner_id}>.", ephemeral=True)
            
        vc = self.guild.voice_client
        if not vc:
            return await interaction.response.send_message("Bot tidak di voice channel.", ephemeral=True)
            
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Playback dijeda.", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Playback dilanjutkan.", ephemeral=True)
        else:
            await interaction.response.send_message("Tidak ada lagu yang aktif.", ephemeral=True)
            
        embed = self.cog.get_nowplaying_embed(self.guild)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            owner_id = self.cog.session_owners.get(self.guild.id)
            return await interaction.response.send_message(f"Sesi ini dimiliki oleh <@{owner_id}>. Gunakan `/voteskip`.", ephemeral=True)
            
        vc = self.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Lagu dilewati.", ephemeral=True)
        else:
            await interaction.response.send_message("Tidak ada lagu yang diputar.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_owner(interaction):
            owner_id = self.cog.session_owners.get(self.guild.id)
            return await interaction.response.send_message(f"Sesi ini dimiliki oleh <@{owner_id}>.", ephemeral=True)
            
        vc = self.guild.voice_client
        if vc:
            if self.guild.id in self.cog.queues:
                self.cog.queues[self.guild.id].clear()
            vc.stop()
            await vc.disconnect()
            self.cog.session_owners.pop(self.guild.id, None)
            self.cog.now_playing_messages.pop(self.guild.id, None)
            await interaction.response.send_message("⏹️ Playback dihentikan dan queue dibersihkan.", ephemeral=True)
        else:
            await interaction.response.send_message("Bot tidak di voice channel.", ephemeral=True)
            
    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📋")
    async def queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        queues = self.cog.queues.get(self.guild.id, [])
        if queues:
            max_view = 10
            queue_list = "\n".join([f"**{i+1}.** {song.title}" for i, song in enumerate(queues[:max_view])])
            if len(queues) > max_view:
                queue_list += f"\n\n*+{len(queues) - max_view} lagu lainnya*"
            embed = discord.Embed(title="Queue", description=queue_list, color=0x2b2d31)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Queue", description="Queue masih kosong.", color=0x2b2d31)
            embed.add_field(name="Tambah lagu", value=f"`{self.cog.bot.command_prefix}play <judul/link>`")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except:
            pass

async def setup(bot):
    await bot.add_cog(Music(bot))
