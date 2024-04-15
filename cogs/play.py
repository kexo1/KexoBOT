from typing import Union
import re

import discord
import wavelink
from wavelink import TrackEventPayload, WavelinkException
from discord import option
from discord.ui import Button, View
from discord.ext import commands
from discord import HTTPException
from discord.commands import slash_command
from wavelink.ext import spotify
from bson.objectid import ObjectId


class Play(commands.Cog):
    # noinspection RegExpRedundantEscape,RegExpSimplifiable
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.soundcloud_playlist_regex = re.compile(
            r"^(https?:\/\/)?(www\.)?soundcloud\.com\/.*\/sets\/.*$"
        )
        self.soundcloud_track_regex = re.compile(
            r"^https:\/\/soundcloud\.com\/(?:[^\/]+\/){1}[^\/]+$"
        )
        # r"(https://)(www\.)?(youtube\.com)\/(?:watch\?v=|playlist)?(?:.*)?&?(list=.*)"
        self.youtube_playlist_regex = re.compile(
            r"(https://)(www\.)?(youtube\.com)\/(?:watch\?v=|playlist)?(?:.*)?&?(list=.*)"
        )
        self.youtube_track_regex = re.compile(
            r"^https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]{11}$"
        )
        self.youtubemusic_track_regex = re.compile(
            r"(?:https?:\/\/)?(?:www\.)?(?:music\.)?youtube\.com\/(?:watch\?v=|playlist\?list=)[\w-]+"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: TrackEventPayload):

        embed = discord.Embed(color=discord.Colour.green(), title='Now playing',
                              description='[**{}**]({})'.format(payload.track.title, payload.track.uri))

        if not hasattr(payload.player.current, 'ctx'):

            embed.set_footer(text=f'Youtube Mix',
                             icon_url='https://clipartcraft.com/images/youtube-logo-transparent-circle-9.png')
        else:
            try:
                embed.set_footer(text=f'Requested by {payload.player.current.ctx.author.name}',
                                 icon_url=payload.player.current.ctx.author.avatar.url)
            except AttributeError:
                # Some users don't have pfp
                embed.set_footer(text=f'Requested by {payload.player.current.ctx.author.name}')

        try:
            embed.set_thumbnail(url=await payload.player.current.fetch_thumbnail())
        except AttributeError:
            pass

        async def button1_callback(interaction):
            await self.skip_command(interaction)

        async def button2_callback(interaction):
            if '⏸️' in str(button2.emoji):
                await self.pause_command(interaction)
                button2.emoji = '▶'
            else:
                await self.resume_command(interaction)
                button2.emoji = '⏸️'

            await interaction.message.edit(view=view)

        button1 = Button(emoji='⏭️')
        button2 = Button(emoji='⏸️')
        button1.callback = button1_callback
        button2.callback = button2_callback

        view = View(timeout=payload.track.duration / 1000)
        view.add_item(button1)
        view.add_item(button2)

        if payload.player.queue.is_empty:
            try:
                await payload.player.current.ctx.respond(embed=embed, view=view)
            except (HTTPException, AttributeError):
                # If timed out, or YouTube algorithm
                try:
                    await payload.player.text_channel.send(embed=embed, view=view)
                except discord.Forbidden:
                    # If no permissions
                    pass

        else:
            await payload.player.text_channel.send(embed=embed, view=view)

    @slash_command(name='play', description='Plays song.', guild_only=True)
    @commands.cooldown(1, 4, commands.BucketType.user)
    @option('search', description='Links and words for youtube, playlists soundcloud urls,  work too are supported.')
    async def play(self, ctx, search: str):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not in vc, type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        if ctx.voice_client:
            if ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                embed = discord.Embed(title="",
                                      description=str(
                                          ctx.author.mention) + ", bot is already playing in a voice channel.",
                                      color=discord.Color.blue())
                return await ctx.respond(embed=embed)

        if not ctx.voice_client:
            try:
                vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                await ctx.defer()
            except wavelink.InvalidChannelPermissions:
                embed = discord.Embed(title="",
                                      description=f":x: I don't have permissions to join your channel.",
                                      color=discord.Color.from_rgb(r=255, g=0, b=0))
                return await ctx.respond(embed=embed)

            embed = discord.Embed(title="",
                                  description=f'**✅ Joined to <#{ctx.voice_client.channel.id}> and set text channel to <#{ctx.channel.id}>.**',
                                  color=discord.Color.blue())
            await ctx.respond(embed=embed)

            vc.auto_queue = False
            vc.text_channel = ctx.channel
            # await vc.set_volume(await self.set_volume(ctx))
        else:
            vc: wavelink.Player = ctx.voice_client

        await ctx.trigger_typing()

        if self.youtube_playlist_regex.match(search):
            try:
                playlist = await wavelink.YouTubePlaylist.search(search)
            except WavelinkException:
                return await ctx.respond('Tracks failed to load, check if you used correct url.', ephemeral=True)

            track_count = 0
            for track in playlist.tracks:
                track.ctx = ctx
                track_count += 1
                await vc.queue.put_wait(track)

            await ctx.respond(embed=self.return_embed_list(track_count))

            if not vc.is_playing():
                await vc.play(vc.queue.get())

        elif self.soundcloud_track_regex.match(search):
            track = (await wavelink.SoundCloudTrack.search(search))[0]
            track.ctx = ctx

            if vc.is_playing() or vc.is_paused():
                await vc.queue.put_wait(track)
                await ctx.respond(embed=self.return_embed(track))
            else:
                await vc.play(track)

        elif "spotify.com" in search:
            decoded = spotify.decode_url(search)
            if decoded and decoded["type"] is not spotify.SpotifySearchType.unusable:
                try:
                    if decoded["type"] is spotify.SpotifySearchType.playlist:
                        track_count = 0
                        async for track in spotify.SpotifyTrack.iterator(query=search):
                            track_count += 1
                            track.ctx = ctx
                            track.uri = f"https://open.spotify.com/track/{track.uri.split(':')[2]}"
                            await vc.queue.put_wait(track)

                        await ctx.respond(embed=self.return_embed_list(track_count))

                        if not vc.is_playing():
                            await vc.play(vc.queue.get())

                    elif decoded["type"] is spotify.SpotifySearchType.album:
                        track_count = 0

                        async for track in spotify.SpotifyTrack.iterator(query=search):
                            track_count += 1
                            track.ctx = ctx
                            track.uri = f"https://open.spotify.com/track/{track.uri.split(':')[2]}"
                            await vc.queue.put_wait(track)

                        await ctx.respond(embed=self.return_embed_list(track_count))

                        if not vc.is_playing():
                            await vc.play(vc.queue.get())
                    else:
                        try:
                            track = (await spotify.SpotifyTrack.search(query=search))[0]
                        except IndexError:
                            return await ctx.respond('Track failed to load, check if you used correct url.', ephemeral=True)

                        track.uri = f"https://open.spotify.com/track/{track.uri.split(':')[2]}"
                        track.ctx = ctx

                        if vc.is_playing() or vc.is_paused():
                            await vc.queue.put_wait(track)
                            await ctx.respond(embed=self.return_embed(track))
                        else:
                            await vc.play(track)

                except wavelink.ext.spotify.SpotifyRequestError:
                    return await ctx.respond('Failed to load, check if playlist is not private.')

        else:
            try:
                track = await wavelink.YouTubeTrack.search(search)
            except (ValueError, WavelinkException):
                if 'https://youtube.com/shorts' in search:
                    return await ctx.respond("Shorts aren't supported.", ephemeral=True)
                else:
                    return await ctx.respond('Track failed to load, check if you used correct url.', ephemeral=True)

            # add search options
            track = track[0]
            track.ctx = ctx

            if vc.is_playing() or vc.is_paused():
                await vc.queue.put_wait(track)
                await ctx.respond(embed=self.return_embed(track))
            else:
                await vc.play(track)

    @slash_command(name='play-next', description='Put this song next in queue, bypassing others.', guild_only=True)
    @commands.cooldown(1, 4, commands.BucketType.user)
    @option('search',
            description='Links and words for youtube are supported, playlists work too.')
    async def play_next(self, ctx, search: str):
        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not in vc, type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        if ctx.voice_client:
            if ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                embed = discord.Embed(title="",
                                      description=str(
                                          ctx.author.mention) + ", bot is already playing in a voice channel.",
                                      color=discord.Color.blue())
                return await ctx.respond(embed=embed)

        if not ctx.voice_client:
            try:
                vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            except wavelink.InvalidChannelPermissions:
                embed = discord.Embed(title="",
                                      description=f":x: I don't have permissions to join your channel.",
                                      color=discord.Color.from_rgb(r=255, g=0, b=0))
                return await ctx.respond(embed=embed)

            embed = discord.Embed(title="",
                                  description=f'**✅ Joined to <#{ctx.voice_client.channel.id}> and set text channel to <#{ctx.channel.id}>**',
                                  color=discord.Color.blue())
            await ctx.respond(embed=embed)

            vc.autoplay = True
            vc.text_channel = ctx.channel
            # await vc.set_volume(await self.set_volume(ctx))
        else:
            vc: wavelink.Player = ctx.voice_client

        await ctx.trigger_typing()

        # YT Playlist
        if self.youtube_playlist_regex.match(search):
            playlist = await wavelink.YouTubePlaylist.search(search)
            track_count = 0
            for track in playlist.tracks:
                track.ctx = ctx
                track_count += 1
                vc.queue.put_at_front(track)

            await ctx.respond(embed=self.return_embed_list(track_count))

            if not vc.is_playing():
                await vc.play(vc.queue.get())

        elif "spotify.com" in search:
            decoded = spotify.decode_url(search)
            if decoded and decoded["type"] is not spotify.SpotifySearchType.unusable:
                if decoded["type"] is spotify.SpotifySearchType.playlist:
                    embed = discord.Embed(title="",
                                          description="Can't add entire Spotify playlist using **/play-next**.",
                                          color=discord.Color.blue())
                    await ctx.respond(embed=embed)

                elif decoded["type"] is spotify.SpotifySearchType.album:
                    embed = discord.Embed(title="",
                                          description="Can't add entire Spotify playlist using **/play-next**.",
                                          color=discord.Color.blue())
                    await ctx.respond(embed=embed)
                else:
                    track = (await spotify.SpotifyTrack.search(query=search))[0]
                    track.uri = f"https://open.spotify.com/track/{track.uri.split(':')[2]}"
                    track.ctx = ctx

                    if vc.is_playing():
                        vc.queue.put_at_front(track)
                        await ctx.respond(embed=self.return_embed(track))
                    else:
                        await vc.play(track)

        elif self.soundcloud_track_regex.match(search):
            track = (await wavelink.SoundCloudTrack.search(search))[0]
            track.ctx = ctx

            if vc.is_playing() or vc.is_paused():
                await vc.queue.put_wait(track)
                await ctx.respond(embed=self.return_embed(track))
            else:
                await vc.play(track)

        else:
            try:
                track = await wavelink.YouTubeTrack.search(search)
            except (ValueError, WavelinkException) as e:
                print(e)
                if 'https://youtube.com/shorts' in search:
                    return await ctx.respond("Shorts aren't supported.", ephemeral=True)
                else:
                    return await ctx.respond('Track failed to load, check if you used correct url.', ephemeral=True)

            # add search options
            track = track[0]
            track.ctx = ctx

            if vc.is_playing() or vc.is_paused():
                await vc.queue.put_wait(track)
                await ctx.respond(embed=self.return_embed(track))
            else:
                await vc.play(track)

    @slash_command(name='soundcloud', description='Plays soundcloud song, type song name just like in search bar.',
                   guild_only=True)
    @commands.cooldown(1, 4, commands.BucketType.user)
    @option('search', description='Only song names are allowed, just like in search bar.')
    async def soundcloud(self, ctx, search: str):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not in vc, type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        if ctx.voice_client:
            if ctx.voice_client.channel.id != ctx.author.voice.channel.id:
                embed = discord.Embed(title="",
                                      description=str(
                                          ctx.author.mention) + ", bot is already playing in a voice channel.",
                                      color=discord.Color.blue())
                return await ctx.respond(embed=embed)

        if not ctx.voice_client:
            try:
                vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            except wavelink.InvalidChannelPermissions:
                embed = discord.Embed(title="",
                                      description=f":x: I don't have permissions to join your channel.",
                                      color=discord.Color.from_rgb(r=255, g=0, b=0))
                return await ctx.respond(embed=embed)

            embed = discord.Embed(title="",
                                  description=f'**✅ Joined to <#{ctx.voice_client.channel.id}> and set text channel to <#{ctx.channel.id}>**',
                                  color=discord.Color.blue())
            await ctx.respond(embed=embed)

            vc.autoplay = True
            vc.text_channel = ctx.channel
            # await vc.set_volume(await self.set_volume(ctx))
        else:
            vc: wavelink.Player = ctx.voice_client

        await ctx.trigger_typing()

        if self.soundcloud_track_regex.match(search) or self.soundcloud_playlist_regex.match(search):
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", links for soundloud don't work here, use /play",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed)
        else:
            track = (await wavelink.SoundCloudTrack.search(search))[0]
            track.ctx = ctx

            if vc.is_playing():
                await vc.queue.put_wait(track)
                await ctx.respond(embed=self.return_embed(track))
            else:
                await vc.play(track)

    @slash_command(name='skip', description='Skip playing song.', guild_only=True)
    async def skip_command(self, ctx):

        try:
            vc = ctx.voice_client
        except AttributeError:
            vc = ctx.guild.voice_client

        vc: wavelink.Player = vc

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        elif not vc.is_playing():
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song is playing',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        await vc.stop()

        embed = discord.Embed(title="",
                              description="**⏭️   Skipped**",
                              color=discord.Color.blue())

        if type(ctx) is discord.interactions.Interaction:
            embed.set_footer(text=f'Requested by {ctx.user.name}',
                             icon_url=ctx.user.avatar.url if ctx.user.avatar else None)

        await ctx.response.send_message(embed=embed)

    @slash_command(name='skip-to', description='Skips to selected song in queue.', guild_only=True)
    @option('pos', description='Value 2 skips to second song in queue.', min_value=1, required=True)
    async def skip_to_command(self, ctx, pos: int):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not joined into vc. Type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + "**, I'm not joined to vc**",
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        if vc.queue.is_empty:
            embed = discord.Embed(title="", description="**Queue is empty**", color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        try:
            track = vc.queue[pos - 1]
            vc.queue.put_at_front(track)
            del vc.queue[pos - 1]
            await vc.stop()
            embed = discord.Embed(title="",
                                  description=f"**Skipped to [{track.title}]({track.uri})**",
                                  color=discord.Color.blue())
        except IndexError:
            embed = discord.Embed(title="",
                                  description=f"**:x: Song was not found on position `{pos}`, to show what's in queue, type /q.**",
                                  color=discord.Color.blue())
        await ctx.respond(embed=embed)

    @slash_command(name='pause', description='Pauses song that is currently playing.', guild_only=True)
    async def pause_command(self, ctx):

        try:
            vc = ctx.voice_client
        except AttributeError:
            vc = ctx.guild.voice_client

        vc: wavelink.Player = vc

        if not vc or vc.is_paused():
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song is playing.',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        await vc.pause()

        if type(ctx) is discord.interactions.Interaction:
            embed = discord.Embed(title="",
                                  description=f"**⏸️   Paused by {ctx.user.name}**",
                                  color=discord.Color.blue())
        else:
            embed = discord.Embed(title="",
                                  description="**⏸️   Paused**",
                                  color=discord.Color.blue())

        embed.set_footer(text=f'Deleting in 10s.')
        await ctx.response.send_message(embed=embed, delete_after=10)

    @slash_command(name='resume', description='Resumes paused song.', guild_only=True)
    async def resume_command(self, ctx):

        try:
            vc = ctx.voice_client
        except AttributeError:
            vc = ctx.guild.voice_client

        vc: wavelink.Player = vc

        if not vc:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song playing.',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        await vc.resume()

        if type(ctx) is discord.interactions.Interaction:
            embed = discord.Embed(title="",
                                  description=f"**:arrow_forward: Resumed by {ctx.user.name}**",
                                  color=discord.Color.blue())
        else:
            embed = discord.Embed(title="",
                                  description="**:arrow_forward: Resumed**",
                                  color=discord.Color.blue())

        embed.set_footer(text=f'Deleting in 10s.')
        await ctx.response.send_message(embed=embed, delete_after=10)

    @slash_command(name='play-random',
                   description='Default is True. After 5 songs youtube creates "mix", this command enables to play that mix.',
                   guild_only=True)
    async def play_random(self, ctx, option: bool = None):

        try:
            vc = ctx.voice_client
        except AttributeError:
            vc = ctx.guild.voice_client

        vc: wavelink.Player = vc

        if not vc:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song is playing.',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        if option is None:

            if vc.autoplay:
                vc.autoplay = False
            else:
                vc.autoplay = True
        else:
            vc.autoplay = option

        embed = discord.Embed(title="",
                              description=f"**:cyclone: Play Youtube Mixes set to `{vc.autoplay}`.**",
                              color=discord.Color.blue())

        await ctx.respond(embed=embed)

    @staticmethod
    def return_embed(track):
        embed = discord.Embed(title="",
                              description=f"**Added to queue:\n [{track.title}]({track.uri})**",
                              color=discord.Color.blue())
        return embed

    @staticmethod
    def return_embed_list(count):
        embed = discord.Embed(title="",
                              description=f"**Added {count} tracks to queue**",
                              color=discord.Color.blue())
        return embed

    async def set_volume(self, ctx):
        # noinspection PyUnresolvedReferences
        if str(ctx.guild.id) not in self.bot.volumes:
            return 50

        return self.bot.volumes[str(ctx.guild.id)]


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Play(bot))
