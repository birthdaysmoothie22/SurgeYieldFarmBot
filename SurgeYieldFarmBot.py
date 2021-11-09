import os
import json
import logging
import time
import datetime
from discord.client import Client
import pytz
import asyncio
import discord
from discord.ext import tasks, commands
from discord_components import *
from dotenv import load_dotenv
import surge_get_yield_farm_results

#load environment variables
load_dotenv()

ROOT_PATH = os.getenv('ROOT_PATH')
SURGE_YIELD_FARM_BOT_KEY = os.getenv('SURGE_YIELD_FARM_BOT_KEY')
OWNER_DISCORD_ID = int(os.getenv('OWNER_DISCORD_ID'))

logging.basicConfig(filename=ROOT_PATH+"/error_log.log",
	format='%(levelname)s %(asctime)s :: %(message)s',
	level=logging.INFO)

with open(ROOT_PATH+"/surge_yield_farms.json", "r") as surge_yield_farms_json:
	surge_yield_farms = json.load(surge_yield_farms_json)

def createRewardsResultEmbedMessage(farm, result):
	embed = False

	data = json.loads(result)
	if len(data[farm]) > 0:
		embed = discord.Embed(
			title="**"+surge_yield_farms[farm]['symbol']+" : Farm Details**",
			description="", 
			color=surge_yield_farms[farm]['color'])
		embed.set_thumbnail(url=surge_yield_farms[farm]['icon'])
		embed.add_field(name="**Balance (Farm Tokens)**", value=str(data[farm]['balance']), inline=False)
		embed.add_field(name="**Farm LP Balance (xUSD)**", value=str(data[farm]['xusd_value']), inline=False)
		embed.add_field(name="**Farm LP Balance (BNB)**", value=str(data[farm]['bnb_value']), inline=False)
		embed.add_field(name="**Farm LP Value (USD)**", value="$"+str(data[farm]['total_lp_farm_balance']), inline=False)
		embed.add_field(name="**Time Until Farm Tokens Unlock**", value=str(data[farm]['time_until_unlock'])+" days", inline=False)
		if data[farm]['time_until_next_claim'] > 0:
			time_until_next_claim = str(data[farm]['time_until_next_claim'])+" seconds"
		else:
			time_until_next_claim = "Now"
		embed.add_field(name="**Time Until Next Claim**", value=time_until_next_claim, inline=False)
		embed.add_field(name="**Pending Rewards (xUSD)**", value=str(data[farm]['pending_rewards']), inline=False)
		embed.add_field(name="**Total Rewards Claimed (xUSD)**", value=str(data[farm]['total_rewards']), inline=False)
		
		embed_disclaimer_text ="Pricing data powered by Binance and Coingecko APIs"
		embed_disclaimer_text +="\nTransaction data powered by BscScan"
		embed.set_footer(text=embed_disclaimer_text)

	return embed

def createCustomHelpEmbedMessage():
	embed = discord.Embed(
		title="Available SurgeYieldFarmBot Commands",
		description="Here are all the available commands for the SurgeYieldFarmBot.", 
		color=0x22B4AB)
	embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/892852181802291215/898293624528338944/Profit_Checker_3.png")
	embed.add_field(name="rewards", value="Calculates your overall Surge Token value.  Requires you to pick a token and provide your public wallet address.", inline=False)
	embed.add_field(name="rewards_manual, calc_manual", value="Calculates your overall Surge Token value.  You must provide the token you wish to caluclate and your public wallet address.  Example: !calculate_manual SurgeADA 0x00a...", inline=False)

	return embed

async def calculateYieldFarmRewards(ctx, farm, wallet_address):
	await ctx.author.send("I'm creating your report now:")
	result = surge_get_yield_farm_results.fetch_yield_farm_rewards(wallet_address, farm)
	embed = createRewardsResultEmbedMessage(farm, result)
	if embed != False:
		await ctx.author.send(embed=embed)
	else: 
		await ctx.author.send("No transaction data for "+farm+" farm")
	return

# async def calculateAllYieldFarmRewards(ctx, wallet_address):
# 	await ctx.author.send("I'm creating your reports now:")
# 	for farm in surge_yield_farms:
# 		result = surge_get_yield_farm_results.fetch_all_yield_farm_rewards(wallet_address, farm)
# 		embed = createCalcResultEmbedMessage(farm, result)
# 		if embed != False:
# 			await ctx.author.send(embed=embed)
	
# 	await ctx.author.send("All your reports are complete.")
# 	return

bot = commands.Bot(command_prefix='$', owner_id=OWNER_DISCORD_ID, help_command=None)

@bot.event
async def on_ready():
	print('We have logged in as {0.user}'.format(bot))
	DiscordComponents(bot)

@bot.command(aliases=['Rewards'])
@commands.dm_only()
async def rewards(ctx):
	message = 'Please enter your public BEP-20 wallet address:\n'
	await ctx.author.send(message)

	def check_message(msg):
		return msg.author == ctx.author and len(msg.content) > 0

	try:
		wallet_address = await bot.wait_for("message", check=check_message, timeout = 30) # 30 seconds to reply
	except asyncio.TimeoutError:
		await ctx.send("Sorry, you either didn't reply with your wallet address or didn't reply in time!")
		return
	
	await calculateYieldFarmRewards(ctx, 'bnb-xusd', wallet_address.content)
	#@todo give the user the option to pick another token without asking them for their wallet again
	return

bot.run(SURGE_YIELD_FARM_BOT_KEY)