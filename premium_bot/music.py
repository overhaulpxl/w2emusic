import yt_dlp
import asyncio
import json
import os
import aiohttp
import urllib.parse
import io
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Setup yt-dlp options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options_templates = {
    'low': {'options': '-vn -b:a 64k', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'},
    'basic': {'options': '-vn -b:a 128k', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'},
    'hq': {'options': '-vn -b:a 320k', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
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
        self.uploader = data.get('uploader', 'Unknown Artist')

    @classmethod
    async def from_query(cls, query, loop=None, stream=False, custom_ffmpeg_options=None):
        loop = loop or asyncio.get_event_loop()
        ff_opts = custom_ffmpeg_options if custom_ffmpeg_options else ffmpeg_options_templates['basic']

        if not query.startswith('http'):
            query = f'ytsearch:{query}'
            
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=not stream))

        if not data:
            raise Exception("Lagu tidak ditemukan atau tidak bisa diputar.")

        if 'entries' in data:
            valid_entries = [e for e in data['entries'] if e]
            sources = []
            for entry in valid_entries:
                filename = entry['url'] if stream else ytdl.prepare_filename(entry)
                sources.append(cls(discord.FFmpegPCMAudio(filename, **ff_opts), data=entry))
            return sources
        else:
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return [cls(discord.FFmpegPCMAudio(filename, **ff_opts), data=data)]

class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.primary, emoji="⏯️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.is_whitelisted(interaction.user.id):
            return await interaction.response.send_message("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!", ephemeral=True)
            
        voice_client = self.guild.voice_client
        if not voice_client:
            return await interaction.response.send_message("Tidak ada lagu diputar.", ephemeral=True)

        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Lagu dijeda ⏸️", ephemeral=True)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Lagu dilanjutkan ▶️", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.is_whitelisted(interaction.user.id):
            return await interaction.response.send_message("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!", ephemeral=True)
            
        voice_client = self.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("Lagu dilewati ⏭️", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.is_whitelisted(interaction.user.id):
            return await interaction.response.send_message("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!", ephemeral=True)
            
        voice_client = self.guild.voice_client
        if voice_client:
            if self.guild.id in self.cog.queues:
                self.cog.queues[self.guild.id].clear()
            voice_client.stop()
            await voice_client.disconnect()
            await interaction.response.send_message("Bot dihentikan ⏹️", ephemeral=True)

class SearchDropdown(discord.ui.Select):
    def __init__(self, cog, ctx, results):
        self.cog = cog
        self.ctx = ctx
        self.results = results
        options = []
        for i, res in enumerate(results[:5]):
            title = res.get('title', 'Unknown')[:90]
            uploader = res.get('uploader', 'Unknown')[:90]
            options.append(discord.SelectOption(label=title, description=uploader, value=str(i)))
            
        super().__init__(placeholder="Pilih lagu untuk diputar...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not self.cog.is_whitelisted(interaction.user.id):
            return await interaction.response.send_message("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!", ephemeral=True)
            
        await interaction.response.defer()
        index = int(self.values[0])
        selected = self.results[index]
        
        url = selected.get('webpage_url') or selected.get('url')
        await self.cog.play(self.ctx, query=url)

class SearchView(discord.ui.View):
    def __init__(self, cog, ctx, results):
        super().__init__()
        self.add_item(SearchDropdown(cog, ctx, results))

class MusicPremium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current_song = {}
        self.now_playing_messages = {}
        self.whitelist_file = 'whitelist.json'
        self.playlists_file = 'custom_playlists.json'
        self.autoplay = {}
        self.audio_filters = {}
        self.history = {}
        self.stay_vc = {}
        self.seek_time = {}
        self.audio_quality = {}
        self.user_stats = {}
        self.user_sfx = {}
        self.user_themes = {}
        self.stats_file = 'user_stats.json'
        self.sfx_file = 'user_sfx.json'
        self.themes_file = 'user_themes.json'
        self.load_whitelist()
        self.load_playlists()
        self.load_json_db()
        
        # Spotify setup
        self.spotify = None
        spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if spotify_client_id and spotify_client_secret and spotify_client_id != "isi_client_id_kamu":
            auth_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
            self.spotify = spotipy.Spotify(auth_manager=auth_manager)

    def load_json_db(self):
        for attr, filename in [('user_stats', self.stats_file), ('user_sfx', self.sfx_file), ('user_themes', self.themes_file)]:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    setattr(self, attr, json.load(f))

    def save_json_db(self, attr, filename):
        with open(filename, 'w') as f:
            json.dump(getattr(self, attr), f)

    def load_whitelist(self):
        if os.path.exists(self.whitelist_file):
            with open(self.whitelist_file, 'r') as f:
                self.whitelist = json.load(f)
        else:
            self.whitelist = []

    def save_whitelist(self):
        with open(self.whitelist_file, 'w') as f:
            json.dump(self.whitelist, f)

    def load_playlists(self):
        if os.path.exists(self.playlists_file):
            with open(self.playlists_file, 'r') as f:
                self.custom_playlists = json.load(f)
        else:
            self.custom_playlists = {}

    def save_playlists(self):
        with open(self.playlists_file, 'w') as f:
            json.dump(self.custom_playlists, f)

    def is_whitelisted(self, user_id):
        return user_id in self.whitelist

    def check_premium(self, ctx):
        if not self.is_whitelisted(ctx.author.id):
            return False
        return True

    def get_ffmpeg_options(self, guild_id):
        quality = self.audio_quality.get(guild_id, 'basic')
        opts = dict(ffmpeg_options_templates[quality])
        filter_str = self.audio_filters.get(guild_id)
        if filter_str:
            opts['options'] += f' -af "{filter_str}"'
        return opts

    async def update_now_playing(self, guild, content, view=None):
        channel = None
        if guild.id in self.now_playing_messages:
            msg, channel = self.now_playing_messages[guild.id]
            try:
                if view:
                    await msg.edit(content=content, view=view)
                else:
                    await msg.edit(content=content)
                return
            except:
                pass
                
        if channel:
            if view:
                new_msg = await channel.send(content, view=view)
            else:
                new_msg = await channel.send(content)
            self.now_playing_messages[guild.id] = (new_msg, channel)

    def play_next(self, guild):
        seek_secs = self.seek_time.pop(guild.id, None)
        
        if not seek_secs and self.current_song.get(guild.id):
            player = self.current_song[guild.id]
            if guild.id not in self.history:
                self.history[guild.id] = []
            self.history[guild.id].insert(0, player)
            if len(self.history[guild.id]) > 10:
                self.history[guild.id].pop()
                
            # Track stats for wrapped
            req_id = str(player.data.get('requester_id', 'unknown'))
            if req_id != 'unknown':
                if req_id not in self.user_stats:
                    self.user_stats[req_id] = {'total_duration': 0, 'artists': {}, 'songs': {}}
                
                self.user_stats[req_id]['total_duration'] += player.duration
                artist = player.uploader
                title = player.title
                self.user_stats[req_id]['artists'][artist] = self.user_stats[req_id]['artists'].get(artist, 0) + 1
                self.user_stats[req_id]['songs'][title] = self.user_stats[req_id]['songs'].get(title, 0) + 1
                self.save_json_db('user_stats', self.stats_file)

        if guild.id in self.queues and len(self.queues[guild.id]) > 0:
            player = self.queues[guild.id].pop(0)
            self.current_song[guild.id] = player
            
            if seek_secs:
                ff_opts = self.get_ffmpeg_options(guild.id)
                ff_opts['before_options'] = ff_opts.get('before_options', '') + f" -ss {seek_secs}"
                new_source = discord.FFmpegPCMAudio(player.url, **ff_opts)
                player = YTDLSource(new_source, data=player.data)
                self.current_song[guild.id] = player
            
            guild.voice_client.play(player, after=lambda e: self.play_next(guild))
            
            embed = discord.Embed(title=f"💎 {player.title[:250]}", url=player.data.get('webpage_url', player.url), color=discord.Color.purple())
            if player.data.get('thumbnail'):
                embed.set_image(url=player.data.get('thumbnail'))
            embed.add_field(name="🎤 Artis", value=player.uploader[:100], inline=True)
            embed.add_field(name="⏱️ Durasi", value=format_duration(player.duration), inline=True)
            
            view = MusicControlView(self, guild)
            asyncio.run_coroutine_threadsafe(self.update_now_playing(guild, content=None, view=view, embed=embed), self.bot.loop)
        else:
            # Autoplay logic
            if self.autoplay.get(guild.id) and self.current_song.get(guild.id):
                last_song = self.current_song[guild.id]
                asyncio.run_coroutine_threadsafe(self.trigger_autoplay(guild, last_song), self.bot.loop)
            else:
                self.current_song[guild.id] = None

    async def trigger_autoplay(self, guild, last_song):
        # Search for mix based on uploader/title
        query = f"{last_song.uploader} {last_song.title} mix audio"
        try:
            players = await YTDLSource.from_query(query, loop=self.bot.loop, stream=True, custom_ffmpeg_options=self.get_ffmpeg_options(guild.id))
            if players:
                player = players[0]
                self.current_song[guild.id] = player
                guild.voice_client.play(player, after=lambda e: self.play_next(guild))
                
                embed = discord.Embed(title=f"🤖 [Autoplay] {player.title[:240]}", url=player.data.get('webpage_url', player.url), color=discord.Color.teal())
                if player.data.get('thumbnail'):
                    embed.set_image(url=player.data.get('thumbnail'))
                embed.add_field(name="🎤 Artis", value=player.uploader[:100], inline=True)
                embed.add_field(name="⏱️ Durasi", value=format_duration(player.duration), inline=True)
                
                view = MusicControlView(self, guild)
                await self.update_now_playing(guild, content=None, view=view, embed=embed)
        except Exception as e:
            pass

    @commands.hybrid_command(name='whitelist', help='[ADMIN] Menambahkan/menghapus user dari premium')
    @commands.has_permissions(administrator=True)
    async def whitelist_cmd(self, ctx, action: str, member: discord.Member):
        action = action.lower()
        if action == 'add':
            if member.id not in self.whitelist:
                self.whitelist.append(member.id)
                self.save_whitelist()
                await ctx.send(f"✅ {member.mention} berhasil ditambahkan ke Whitelist Premium!")
            else:
                await ctx.send(f"⚠️ {member.mention} sudah ada di Whitelist.")
        elif action == 'remove':
            if member.id in self.whitelist:
                self.whitelist.remove(member.id)
                self.save_whitelist()
                await ctx.send(f"✅ {member.mention} dihapus dari Whitelist Premium.")
            else:
                await ctx.send(f"⚠️ {member.mention} tidak ada di Whitelist.")

    @commands.hybrid_command(name='play', aliases=['p'], help='Memutar lagu (Premium Only)')
    async def play(self, ctx, *, query: str):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")

        if not ctx.author.voice:
            return await ctx.send("Kamu tidak berada di voice channel!")

        channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            return await ctx.send("Bot sedang digunakan di voice channel lain!")

        if ctx.interaction:
            await ctx.defer()
        else:
            await ctx.typing()

        try:
            ff_opts = self.get_ffmpeg_options(ctx.guild.id)
            players = []
            
            # Spotify URL handling
            if 'spotify.com' in query:
                if not self.spotify:
                    return await ctx.send("⚠️ Bot belum dikonfigurasi untuk Spotify. Silakan tambahkan Client ID dan Secret di `.env`.")
                
                try:
                    queries = []
                    if 'track' in query:
                        track_info = self.spotify.track(query)
                        queries.append(f"{track_info['name']} {track_info['artists'][0]['name']} audio")
                    elif 'playlist' in query:
                        playlist_info = self.spotify.playlist(query)
                        tracks = playlist_info['tracks']['items']
                        if not tracks:
                            return await ctx.send("Playlist Spotify kosong atau tidak ditemukan.")
                        await ctx.send(f"🔄 Sedang memproses {min(len(tracks), 15)} lagu dari Playlist Spotify...")
                        for item in tracks[:15]:
                            if not item.get('track'): continue
                            track = item['track']
                            queries.append(f"{track['name']} {track['artists'][0]['name']} audio")
                    elif 'album' in query:
                        album_info = self.spotify.album(query)
                        tracks = album_info['tracks']['items']
                        if not tracks:
                            return await ctx.send("Album Spotify kosong atau tidak ditemukan.")
                        await ctx.send(f"🔄 Sedang memproses {min(len(tracks), 15)} lagu dari Album Spotify...")
                        for track in tracks[:15]:
                            queries.append(f"{track['name']} {track['artists'][0]['name']} audio")
                    else:
                        return await ctx.send("Link Spotify tidak didukung. Harap gunakan link Track, Playlist, atau Album.")
                    
                    if queries:
                        # Fetch the first track first so it starts playing immediately
                        first_players = await YTDLSource.from_query(queries[0], loop=self.bot.loop, stream=True, custom_ffmpeg_options=ff_opts)
                        if first_players:
                            players.extend(first_players)
                        
                        # Process the rest if any
                        if len(queries) > 1:
                            for q in queries[1:]:
                                try:
                                    extra = await YTDLSource.from_query(q, loop=self.bot.loop, stream=True, custom_ffmpeg_options=ff_opts)
                                    if extra:
                                        players.extend(extra)
                                except Exception:
                                    pass
                except Exception as e:
                    return await ctx.send(f"Gagal mengambil data dari Spotify: {e}")
            else:
                players = await YTDLSource.from_query(query, loop=self.bot.loop, stream=True, custom_ffmpeg_options=ff_opts)

            
            for p in players:
                p.data['requester_id'] = ctx.author.id
            
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []

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
                
                ctx.voice_client.play(self.current_song[ctx.guild.id], after=lambda e: self.play_next(ctx.guild))
                
                player = self.current_song[ctx.guild.id]
                embed = discord.Embed(title=f"💎 {player.title[:250]}", url=player.data.get('webpage_url', player.url), color=discord.Color.purple())
                if player.data.get('thumbnail'):
                    embed.set_image(url=player.data.get('thumbnail'))
                embed.add_field(name="🎤 Artis", value=player.uploader[:100], inline=True)
                embed.add_field(name="⏱️ Durasi", value=format_duration(player.duration), inline=True)
                
                view = MusicControlView(self, ctx.guild)
                msg = await ctx.send(embed=embed, view=view)
                self.now_playing_messages[ctx.guild.id] = (msg, ctx.channel)
                
                if len(players) > 0:
                    await ctx.send(f'(Sisa {len(players)} lagu playlist ditambahkan ke antrean)')
                    
        except Exception as e:
            await ctx.send(f"Terjadi kesalahan saat memutar lagu: {str(e)}")

    @commands.hybrid_command(name='search', help='Pencarian YouTube interaktif')
    async def search(self, ctx, *, query: str):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")

        if ctx.interaction:
            await ctx.defer()
        
        try:
            # Menggunakan yt-dlp untuk ekstrak top 5
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{query}", download=False))
            
            if 'entries' in data and data['entries']:
                view = SearchView(self, ctx, data['entries'])
                await ctx.send(f"🔍 **Hasil Pencarian untuk:** `{query}`", view=view)
            else:
                await ctx.send("Tidak menemukan hasil.")
        except Exception as e:
            await ctx.send("Gagal melakukan pencarian.")

    @commands.hybrid_command(name='filter', help='Memberikan efek audio (bassboost, nightcore, vaporwave, clear)')
    async def filter(self, ctx, effect: str):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
            
        effect = effect.lower()
        if effect == 'bassboost':
            self.audio_filters[ctx.guild.id] = "bass=g=20"
            await ctx.send("🔊 Filter **Bassboost** diaktifkan! (Berlaku untuk lagu berikutnya)")
        elif effect == 'nightcore':
            self.audio_filters[ctx.guild.id] = "asetrate=44100*1.25,aresample=44100,atempo=1.25"
            await ctx.send("🚀 Filter **Nightcore** diaktifkan! (Berlaku untuk lagu berikutnya)")
        elif effect == 'vaporwave':
            self.audio_filters[ctx.guild.id] = "asetrate=44100*0.8,aresample=44100,atempo=0.8"
            await ctx.send("🌊 Filter **Vaporwave** diaktifkan! (Berlaku untuk lagu berikutnya)")
        elif effect == 'clear':
            self.audio_filters[ctx.guild.id] = None
            await ctx.send("🧹 Semua filter dihapus! (Berlaku untuk lagu berikutnya)")
        else:
            await ctx.send("Filter tidak valid. Gunakan: `bassboost`, `nightcore`, `vaporwave`, `clear`")

    @commands.hybrid_command(name='volume', help='Mengatur volume suara bot (1-200)')
    async def volume(self, ctx, vol: int):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")

        if ctx.voice_client and ctx.voice_client.source:
            vol = max(1, min(200, vol))
            ctx.voice_client.source.volume = vol / 100
            await ctx.send(f"🔈 Volume diubah menjadi **{vol}%**")
        else:
            await ctx.send("Bot tidak memutar apapun saat ini.")

    @commands.hybrid_command(name='autoplay', help='Menyalakan/mematikan Radio 24/7 otomatis')
    async def autoplay_cmd(self, ctx):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")

        current = self.autoplay.get(ctx.guild.id, False)
        self.autoplay[ctx.guild.id] = not current
        
        status = "Menyala (On) 🟢" if self.autoplay[ctx.guild.id] else "Mati (Off) 🔴"
        await ctx.send(f"🤖 **Autoplay (Radio)** sekarang {status}")

    @commands.hybrid_command(name='lyrics', help='Mencari lirik lagu yang sedang diputar (Atau tulis judulnya)')
    async def lyrics(self, ctx, *, judul: str = None):
        if not self.check_premium(ctx):
            return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")

        if not judul:
            if ctx.guild.id in self.current_song and self.current_song[ctx.guild.id]:
                judul = self.current_song[ctx.guild.id].title
            else:
                return await ctx.send("Tidak ada lagu diputar. Mohon berikan judul lagu!")

        if ctx.interaction:
            await ctx.defer()
        else:
            await ctx.typing()

        try:
            # Menggunakan API gratis some-random-api
            url = f"https://some-random-api.com/lyrics?title={urllib.parse.quote(judul)}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        lyrics = data.get('lyrics')
                        if lyrics:
                            # Batasi lirik agar tidak melebihi limit 2000 karakter Discord
                            embed = discord.Embed(title=f"📝 Lirik: {data.get('title')}", description=lyrics[:4096], color=discord.Color.blue())
                            embed.set_footer(text=f"Artist: {data.get('author')}")
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send("Lirik tidak ditemukan di database.")
                    else:
                        await ctx.send("Maaf, API Lirik sedang tidak dapat diakses atau lagu tidak ditemukan.")
        except Exception as e:
            await ctx.send("Terjadi kesalahan saat mencari lirik.")

    @commands.hybrid_group(name='playlist', help='Manajemen Custom Playlist Premium', invoke_without_command=True)
    async def playlist(self, ctx):
        await ctx.send("Gunakan `/playlist save <nama>` atau `/playlist load <nama>`")

    @playlist.command(name='save', help='Menyimpan antrean lagu saat ini menjadi Playlist')
    async def save_playlist(self, ctx, name: str):
        if not self.check_premium(ctx): return
        
        if ctx.guild.id not in self.queues or not self.queues[ctx.guild.id]:
            return await ctx.send("Antrean sedang kosong!")
            
        urls = [song.url for song in self.queues[ctx.guild.id]]
        if self.current_song.get(ctx.guild.id):
            urls.insert(0, self.current_song[ctx.guild.id].url)

        user_id = str(ctx.author.id)
        if user_id not in self.custom_playlists:
            self.custom_playlists[user_id] = {}
            
        self.custom_playlists[user_id][name] = urls
        self.save_playlists()
        
        await ctx.send(f"💾 Playlist **{name}** berhasil disimpan dengan {len(urls)} lagu!")

    @playlist.command(name='load', help='Memutar Playlist yang sudah disimpan')
    async def load_playlist(self, ctx, name: str):
        if not self.check_premium(ctx): return
        
        user_id = str(ctx.author.id)
        if user_id not in self.custom_playlists or name not in self.custom_playlists[user_id]:
            return await ctx.send(f"❌ Playlist **{name}** tidak ditemukan.")

        urls = self.custom_playlists[user_id][name]
        await ctx.send(f"📥 Memuat **{len(urls)}** lagu dari playlist **{name}**...")
        
        for url in urls:
            await self.play(ctx, query=url)

    @commands.hybrid_command(name='history', help='Melihat 10 lagu yang terakhir diputar')
    async def history(self, ctx):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        if ctx.guild.id in self.history and len(self.history[ctx.guild.id]) > 0:
            history_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.history[ctx.guild.id])])
            embed = discord.Embed(title="📜 Riwayat Lagu", description=history_list, color=discord.Color.gold())
            await ctx.send(embed=embed)
        else:
            await ctx.send("Riwayat lagu kosong!")

    @commands.hybrid_command(name='stay', help='Memaksa bot tetap di VC walau kosong')
    async def stay(self, ctx):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        current = self.stay_vc.get(ctx.guild.id, False)
        self.stay_vc[ctx.guild.id] = not current
        status = "Menyala (On) 🟢" if self.stay_vc[ctx.guild.id] else "Mati (Off) 🔴"
        await ctx.send(f"🛡️ **Stay 24/7** sekarang {status}")

    @commands.hybrid_command(name='seek', help='Melompat ke detik tertentu (contoh: 1:30 atau 90)')
    async def seek(self, ctx, time: str):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Bot tidak memutar apapun saat ini.")
            
        player = self.current_song.get(ctx.guild.id)
        if not player: return
        
        parts = time.split(':')
        seconds = 0
        try:
            if len(parts) == 2: seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3: seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else: seconds = int(parts[0])
        except ValueError:
            return await ctx.send("Format waktu tidak valid! Gunakan detik (90) atau MM:SS (1:30).")
            
        self.queues[ctx.guild.id].insert(0, player)
        self.seek_time[ctx.guild.id] = seconds
        ctx.voice_client.stop()
        await ctx.send(f"⏩ Melompat ke **{time}**...")

    @commands.hybrid_command(name='queue_export', help='Ekspor antrean ke file .txt')
    async def queue_export(self, ctx):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        if ctx.guild.id not in self.queues or not self.queues[ctx.guild.id]:
            return await ctx.send("Antrean sedang kosong!")
        
        urls = [song.url for song in self.queues[ctx.guild.id]]
        if self.current_song.get(ctx.guild.id):
            urls.insert(0, self.current_song[ctx.guild.id].url)
            
        content = "\n".join(urls)
        file = discord.File(io.StringIO(content), filename="queue_export.txt")
        await ctx.send("📥 Ini file ekspor antrean Anda:", file=file)

    @commands.hybrid_command(name='queue_import', help='Impor antrean dari lampiran file .txt')
    async def queue_import(self, ctx, attachment: discord.Attachment = None):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        
        if not attachment:
            if not ctx.message.attachments:
                return await ctx.send("❌ Tolong lampirkan file .txt bersama dengan command ini!")
            attachment = ctx.message.attachments[0]
            
        if not attachment.filename.endswith('.txt'):
            return await ctx.send("❌ File harus berupa .txt!")
            
        content = await attachment.read()
        urls = content.decode('utf-8').splitlines()
        
        await ctx.send(f"🔄 Sedang memproses {len(urls)} lagu dari file...")
        for url in urls:
            if url.strip():
                await self.play(ctx, query=url.strip())

    @commands.hybrid_command(name='quality', help='Mengatur kualitas audio (low/basic/hq)')
    async def quality(self, ctx, level: str):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        level = level.lower()
        if level not in ['low', 'basic', 'hq']:
            return await ctx.send("Pilihan kualitas: `low` (64k), `basic` (128k), `hq` (320k Studio Quality).")
            
        self.audio_quality[ctx.guild.id] = level
        await ctx.send(f"🎚️ Kualitas audio Premium diatur ke **{level.upper()}**! (Berlaku pada lagu berikutnya)")

    @commands.hybrid_command(name='sfx_add', help='Menambah efek suara pribadi (Max 15 detik)')
    async def sfx_add(self, ctx, nama: str, url: str = None, attachment: discord.Attachment = None):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        
        final_url = url
        if attachment:
            final_url = attachment.url
            
        if not final_url:
            return await ctx.send("❌ Mohon lampirkan file audio (.mp3/.wav) atau berikan link audio langsung!")
            
        user_id = str(ctx.author.id)
        if user_id not in self.user_sfx:
            self.user_sfx[user_id] = {}
        self.user_sfx[user_id][nama.lower()] = final_url
        self.save_json_db('user_sfx', self.sfx_file)
        await ctx.send(f"🎉 SFX **{nama}** berhasil disimpan ke Soundboard pribadi Anda!")

    @commands.hybrid_command(name='sfx', help='Memutar efek suara pribadi')
    async def sfx(self, ctx, nama: str):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        
        if ctx.voice_client and ctx.voice_client.is_playing():
             return await ctx.send("❌ Bot sedang sibuk memutar lagu utama. Jeda (Pause) lagu terlebih dahulu!")
             
        user_id = str(ctx.author.id)
        nama = nama.lower()
        if user_id not in self.user_sfx or nama not in self.user_sfx[user_id]:
            return await ctx.send(f"❌ SFX `{nama}` tidak ditemukan di Soundboard Anda.")
            
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("Kamu tidak berada di voice channel!")

        try:
            ff_opts = dict(ffmpeg_options_templates['basic'])
            ff_opts['before_options'] = ff_opts.get('before_options', '') + " -t 15"
            source = discord.FFmpegPCMAudio(self.user_sfx[user_id][nama], **ff_opts)
            ctx.voice_client.play(discord.PCMVolumeTransformer(source, volume=0.8))
            await ctx.send(f"🔊 Memutar SFX: **{nama}**")
        except Exception as e:
            await ctx.send("Gagal memutar SFX.")

    @commands.hybrid_command(name='set_theme', help='Mengatur lagu tema kedatangan Anda (Auto-play saat masuk VC)')
    async def set_theme(self, ctx, url: str = None, attachment: discord.Attachment = None):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        
        final_url = url
        if attachment:
            final_url = attachment.url
            
        if not final_url:
            return await ctx.send("❌ Mohon lampirkan file audio (.mp3/.wav) atau berikan link audio langsung!")
            
        self.user_themes[str(ctx.author.id)] = final_url
        self.save_json_db('user_themes', self.themes_file)
        await ctx.send("👑 Lagu Tema Kedatangan Anda berhasil dipasang!")

    @commands.hybrid_command(name='wrapped', help='Melihat statistik musik Anda')
    async def wrapped(self, ctx):
        if not self.check_premium(ctx): return await ctx.send("❌ Anda tidak memiliki hak untuk memakai fitur Bot Premium. Tertarik? Silakan *chat* Administrator!")
        user_id = str(ctx.author.id)
        if user_id not in self.user_stats:
            return await ctx.send("📊 Anda belum memutar lagu apapun. Statistik masih kosong.")
            
        stats = self.user_stats[user_id]
        dur_mins = stats['total_duration'] // 60
        
        top_artists = sorted(stats['artists'].items(), key=lambda item: item[1], reverse=True)[:3]
        top_songs = sorted(stats['songs'].items(), key=lambda item: item[1], reverse=True)[:3]
        
        embed = discord.Embed(title=f"🎧 Spotify Wrapped: {ctx.author.name}", color=discord.Color.green())
        embed.add_field(name="Total Mendengarkan", value=f"**{dur_mins} Menit**", inline=False)
        
        artists_str = "\n".join([f"**{i+1}.** {a[0]} ({a[1]} kali)" for i, a in enumerate(top_artists)])
        if artists_str: embed.add_field(name="Top Artis", value=artists_str, inline=True)
        
        songs_str = "\n".join([f"**{i+1}.** {s[0][:40]} ({s[1]} kali)" for i, s in enumerate(top_songs)])
        if songs_str: embed.add_field(name="Top Lagu", value=songs_str, inline=False)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        if before.channel == after.channel: return
        if not after.channel: return
        
        if str(member.id) in self.user_themes:
            voice_client = member.guild.voice_client
            if voice_client and voice_client.channel == after.channel and not voice_client.is_playing():
                theme_url = self.user_themes[str(member.id)]
                try:
                    ff_opts = dict(ffmpeg_options_templates['basic'])
                    ff_opts['before_options'] = ff_opts.get('before_options', '') + " -t 5"
                    source = discord.FFmpegPCMAudio(theme_url, **ff_opts)
                    voice_client.play(discord.PCMVolumeTransformer(source, volume=0.8))
                except:
                    pass

async def setup(bot):
    await bot.add_cog(MusicPremium(bot))
