from datetime import datetime

import discord
import wavelink
from discord.ext import commands
from cogs.disconnect import Disconnect
from wavelink import TrackEventPayload


class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting.
        Args:
            node (wavelink.Node): _description_
        """
        print(f"Node: <{node.uri}> is ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEventPayload) -> None:

        if not payload.player.autoplay:
            if not payload.player.queue.is_empty:
                try:
                    next_song: wavelink.Playable = payload.player.queue.get()
                    if next_song:
                        await payload.player.play(next_song)
                except wavelink.exceptions.QueueEmpty:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(
            self,
            member: discord.member.Member,
            before: discord.VoiceState,
            after: discord.VoiceState):

        voice_state = member.guild.voice_client
        if voice_state is None:
            return

        if len(voice_state.channel.members) == 1:
            await Disconnect.disconnect_player(member.guild)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Listeners(bot))
