from typing import Union
import re

import discord
import wavelink
from discord import option
from discord.ui import Button, View
from discord.ext import commands
from discord import HTTPException
from discord.commands import slash_command
from bson.objectid import ObjectId
from wavelink import exceptions


class Play(commands.Cog):
    # noinspection RegExpRedundantEscape,RegExpSimplifiable
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):

        author_name = payload.player.current.ctx.author.name

        try:
            author_pfp = payload.player.current.ctx.author.avatar.url
        except AttributeError:
            # Some users don't have pfp
            author_pfp = None

        embed = discord.Embed(color=discord.Colour.green(), title='Now playing',
                              description='[**{}**]({})'.format(payload.track.title, payload.track.uri))

        if not hasattr(payload.player.current, 'ctx'):
            embed.set_footer(text=f'Youtube Mix',
                             icon_url='https://clipartcraft.com/images/youtube-logo-transparent-circle-9.png')
        else:
            embed.set_footer(text=f'Requested by {author_name}',
                             icon_url=author_pfp)

        embed.set_thumbnail(url=payload.player.current.artwork)

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

        view = View(timeout=payload.track.length / 1000)
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
                try:
                    vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                except wavelink.exceptions.InvalidNodeException:
                    embed = discord.Embed(title="",
                                          description=f":x: No nodes are currently assigned to the bot. To fix this, go to this site: https://lavainfo.moebot.pro/ and search for online nodes with version v4, then use command `recconnect_node` and input parameters from the site.",
                                          color=discord.Color.from_rgb(r=255, g=0, b=0))
                    return await ctx.respond(embed=embed)

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

            vc.autoplay = wavelink.AutoPlayMode.partial
            # vc.auto_queue = True
            vc.text_channel = ctx.channel
        else:
            vc: wavelink.Player = ctx.voice_client

        await ctx.trigger_typing()

        tracks: wavelink.Search = await wavelink.Playable.search(search)
        if isinstance(tracks, wavelink.Playlist):
            added: int = vc.queue.put(tracks)

            for track in tracks:
                track.ctx = ctx

            track: wavelink.Playable = tracks[0]
            await ctx.respond(embed=self.return_embed_list(tracks.name, added))
        else:
            if not tracks:
                embed = discord.Embed(title="",
                                      description=f":x: Couldn't fetch any songs, are you sure your playlist is set to public?",
                                      color=discord.Color.from_rgb(r=255, g=0, b=0))
                return await ctx.respond(embed=embed)

            track: wavelink.Playable = tracks[0]
            # Append request author, need full ctx due to respond commands
            track.ctx = ctx

        if vc.playing or vc.paused:
            await ctx.respond(embed=self.return_embed(track))
            vc.queue.put(track)
        else:
            await vc.play(track)
            # Due to autoplay the first song does not remove itself after skipping
            vc.queue.remove(track)
            # Somtimes wavelink just sleeps :/
            if not vc.playing:
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

            vc.autoplay = wavelink.AutoPlayMode.partial
            # vc.auto_queue = True
            vc.text_channel = ctx.channel
        else:
            vc: wavelink.Player = ctx.voice_client

        await ctx.trigger_typing()

        tracks: wavelink.Search = await wavelink.Playable.search(search)
        if isinstance(tracks, wavelink.Playlist):
            added: int = vc.queue.put(tracks)

            for track in tracks:
                track.ctx = ctx

            track: wavelink.Playable = tracks[0]
            await ctx.respond(embed=self.return_embed_list(tracks.name, added))
        else:
            if not tracks:
                embed = discord.Embed(title="",
                                      description=f":x: Couldn't fetch any songs, are you sure your playlist is set to public?",
                                      color=discord.Color.from_rgb(r=255, g=0, b=0))
                return await ctx.respond(embed=embed)

            track: wavelink.Playable = tracks[0]
            # Append request author, need full ctx due to respond commands
            track.ctx = ctx

        if vc.playing or vc.paused:
            await ctx.respond(embed=self.return_embed(track))
            vc.queue.put_at(0, track)
        else:
            await vc.play(track)
            # Due to autoplay the first song does not remove itself after skipping
            vc.queue.remove(track)
            # Somtimes wavelink just sleeps :/
            if not vc.playing:
                await vc.play(track)

    @slash_command(name='skip', description='Skip playing song.', guild_only=True)
    async def skip_command(self, ctx):

        try:
            vc = ctx.voice_client
        except AttributeError:
            vc = ctx.guild.voice_client

        vc: wavelink.Player = vc

        if not vc or not vc.connected:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        elif not vc.playing:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song is playing',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        await vc.skip()

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

        if not vc or not vc.connected:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + "**, I'm not joined to vc**",
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        if vc.queue.is_empty:
            embed = discord.Embed(title="", description="**Queue is empty**", color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        try:
            track = vc.queue[pos - 1]
            vc.queue.put_at(0, track)
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

        if not vc or vc.paused:
            embed = discord.Embed(title="",
                                  description=str(ctx.user.mention) + ', no song is playing.',
                                  color=discord.Color.blue())
            return await ctx.response.send_message(embed=embed)

        await vc.pause(True)

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

        await vc.pause(False)

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

    @staticmethod
    def return_embed(track):
        embed = discord.Embed(title="",
                              description=f"**Added to queue:\n [{track.title}]({track.uri})**",
                              color=discord.Color.blue())
        return embed

    @staticmethod
    def return_embed_list(playlist, count):
        embed = discord.Embed(title="",
                              description=f"Added the playlist **`{playlist}`** ({count} songs) to the queue.",
                              color=discord.Color.blue())
        return embed


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Play(bot))
