"""
invoice.py - /invoice command for the Crypto Balance Tracker bot.

Hooked into bot.py with:
    from invoice import register_invoice
    register_invoice(bot, owner_only, get_usd_prices, COIN_META, EMBED_COLOR,
                     LTC_ADDRESSES, BSC_USDT_ADDRESSES)
"""

from datetime import datetime, timezone

import aiohttp
import discord


class InvoiceView(discord.ui.View):
    def __init__(self, address: str, coin_amount: str):
        super().__init__(timeout=None)
        self.address = address
        self.coin_amount = coin_amount

    # On press: two separate private messages - address first, then amount.
    @discord.ui.button(label="Copy Details", style=discord.ButtonStyle.primary, emoji="📋")
    async def copy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(self.address, ephemeral=True)
        await interaction.followup.send(self.coin_amount, ephemeral=True)


def register_invoice(bot, owner_only, get_usd_prices, COIN_META, EMBED_COLOR,
                     LTC_ADDRESSES, BSC_USDT_ADDRESSES):

    @bot.tree.command(name="invoice", description="Send someone an invoice with payment details")
    @discord.app_commands.describe(
        user="Who the invoice is for",
        amount="Amount to charge in USD",
        coin="Coin they should pay with",
    )
    @discord.app_commands.choices(coin=[
        discord.app_commands.Choice(name="LTC", value="LTC"),
        discord.app_commands.Choice(name="USDT (BEP20)", value="USDT"),
    ])
    @owner_only()
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def invoice_cmd(
        interaction: discord.Interaction,
        user: discord.User,
        amount: float,
        coin: discord.app_commands.Choice[str],
    ):
        unit = coin.value

        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        if unit == "LTC":
            address = LTC_ADDRESSES[0] if LTC_ADDRESSES else None
        else:
            address = BSC_USDT_ADDRESSES[0] if BSC_USDT_ADDRESSES else None
        if not address:
            await interaction.response.send_message(f"No {unit} address is configured.", ephemeral=True)
            return

        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            prices = await get_usd_prices(session)

        price = prices.get(unit, 0)
        if not price:
            await interaction.followup.send(
                "Couldn't fetch the current price. Try again in a moment.", ephemeral=True
            )
            return

        coin_amount = amount / price
        coin_amount_str = f"{coin_amount:.8f}" if unit == "LTC" else f"{coin_amount:.6f}"
        meta = COIN_META[unit]

        embed = discord.Embed(
            title=f"{meta['icon']} Invoice",
            description=f"{user.mention}, please send the payment below.",
            color=EMBED_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Network", value=meta["network"], inline=False)
        embed.add_field(
            name="Amount Due",
            value=f"**{coin_amount_str} {unit}**\n(${amount:,.2f} USD)",
            inline=False,
        )
        embed.add_field(name="Send To", value=f"`{address}`", inline=False)
        embed.set_footer(text="Tap Copy Details below to copy the address and amount.")

        await interaction.followup.send(
            content=user.mention,
            embed=embed,
            view=InvoiceView(address, coin_amount_str),
        )
