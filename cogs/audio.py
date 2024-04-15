from datetime import datetime

import discord
import wavelink
from discord.ext import commands
from discord import option
from discord.commands import slash_command
from bson.objectid import ObjectId


class Audio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(name='volume', description='Sets volume.', guild_only=True)
    @option(
        'vol',
        description='Max is 100.',
        min_value=1,
        max_value=200
    )
    async def change_volume(self, ctx, vol: float = None):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not joined into vc. Type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.author.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        if not vol:
            embed = discord.Embed(title="",
                                  description=f"🔊 **{int(vc.volume)}%**",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed)

        await vc.set_volume(value=vol)

        embed = discord.Embed(title="", description=f'**🔊 Volume set to `{int(vol)}%`**',
                              color=discord.Color.blue())
        await ctx.respond(embed=embed)

        self.bot.database.update_one({'_id': ObjectId('617abc9d2255f6aa3a1324ca')},
                                {"$set": {str(ctx.guild.id): int(vol)}})

    @slash_command(name='bass-boost', description='Bass boosts your player, might take 3-5 seconds to start the effect.', guild_only=True)
    async def bass_boost(self, ctx):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not joined into vc. Type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.author.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)
        else:
            await vc.set_filter(wavelink.Filter(equalizer=wavelink.Equalizer.boost()))
            embed = discord.Embed(title="", description="**🔊 Bass boosted!**", color=discord.Color.blue())
            embed.set_footer(text="takes 3 seconds to apply")
            await ctx.respond(embed=embed)

    @slash_command(name='speed', description='Speeds up music.', guild_only=True)
    @option(
        'multiplier',
        description='It might take 3-5 seconds to start speeding up, no value sets it to normal speed',
        min_value=1,
        max_value=8
    )
    async def speed(self, ctx, multiplier: float = None):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not joined into vc. Type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.author.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        elif multiplier:
            await vc.set_filter(wavelink.Filter(timescale=wavelink.Timescale(speed=multiplier)))
            embed = discord.Embed(title="", description=f"**⏩ Sped up by `{int(multiplier)}x`.**", color=discord.Color.blue())
            await ctx.respond(embed=embed)
        else:
            await vc.set_filter(wavelink.Filter(timescale=wavelink.Timescale(speed=1)))
            embed = discord.Embed(title="", description=f"**✅ Normal speed set.**",
                                  color=discord.Color.blue())
            await ctx.respond(embed=embed)

    @slash_command(name='clear-effects', description='Clears all effects on player.', guild_only=True)
    async def clear_effects(self, ctx):

        if not ctx.author.voice:
            embed = discord.Embed(title="",
                                  description=str(
                                      ctx.author.mention) + ", you're not joined into vc. Type `/p` from vc.",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)

        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="",
                                  description=str(ctx.author.mention) + ", I'm not joined to vc",
                                  color=discord.Color.blue())
            return await ctx.respond(embed=embed, ephemeral=True)
        else:
            await vc.set_filter(wavelink.Filter())
            embed = discord.Embed(title="", description=f"**✅ Effects were cleared.**",
                                  color=discord.Color.blue())
            embed.set_footer(text="takes 3 seconds to apply")
            await ctx.respond(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Audio(bot))
