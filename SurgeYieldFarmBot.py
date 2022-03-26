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
		embed.add_field(name="**Farm LP Balance ("+surge_yield_farms[farm]['paired_asset']+")**", value=str(data[farm]['paired_asset_value']), inline=False)
		embed.add_field(name="**Farm LP Value (USD)**", value="$"+str(data[farm]['total_lp_farm_balance_usd']), inline=False)
		embed.add_field(name="**Time Until Farm Tokens Unlock**", value=str(data[farm]['time_until_unlock'])+" days", inline=False)
		embed.add_field(name="**Pending Rewards (xUSD)**", value=str(data[farm]['pending_rewards_xusd']), inline=False)
		if surge_yield_farms[farm]['split_rewards']:
			embed.add_field(name="**Pending Rewards ("+surge_yield_farms[farm]['paired_asset']+")**", value=str(data[farm]['pending_rewards_paired_asset']), inline=False)
		embed.add_field(name="**Pending Rewards (USD)**", value="$"+str(data[farm]['pending_rewards_usd']), inline=False)
		embed.add_field(name="**Total Rewards Claimed (xUSD)**", value=str(data[farm]['total_rewards_xusd']), inline=False)
		if surge_yield_farms[farm]['split_rewards']:
			embed.add_field(name="**Total Rewards Claimed ("+surge_yield_farms[farm]['paired_asset']+")**", value=str(data[farm]['total_rewards_paired_asset']), inline=False)

		embed_disclaimer_text ="Pricing data powered by Binance and Coingecko APIs"
		embed_disclaimer_text +="\nTransaction data powered by BscScan"
		embed.set_footer(text=embed_disclaimer_text)

	return embed

def createCustomHelpEmbedMessage():
	embed = discord.Embed(
		title="Available SurgeYieldFarmBot Commands",
		description="Here are all the available commands for the SurgeYieldFarmBot.", 
		color=0x22B4AB)
	embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/892852181802291215/908438175653957682/surge_farm_bot_icon.png")
	embed.add_field(name="$rewards", value="Calculates your overall Surge Yield Farm rewards.  Requires you to provide your public wallet address.", inline=False)
	embed.add_field(name="$remove_saved", value="Removes your public wallet address from the saved wallets list", inline=False)
	embed.add_field(name="$remove_daily", value="Removes your public wallet address from the daily send wallets list", inline=False)
	return embed

async def calculateYieldFarmRewards(ctx, farm, wallet_address):
	await ctx.author.send("I'm creating your report now:")
	result = surge_get_yield_farm_results.fetch_yield_farm_rewards(wallet_address, farm)
	embed = createRewardsResultEmbedMessage(farm, result)
	if embed != False:
		await ctx.author.send(embed=embed)
	else: 
		await ctx.author.send("No farm data for "+farm+" farm")
	return

async def calculateAllYieldFarmRewards(ctx, wallet_address):
	await ctx.author.send("I'm creating your reports now:")
	for farm in surge_yield_farms:
		result = surge_get_yield_farm_results.fetch_yield_farm_rewards(wallet_address, farm)
		embed = createRewardsResultEmbedMessage(farm, result)
		if embed != False:
			await ctx.author.send(embed=embed)
	
	await ctx.author.send("All your reports are complete.")
	return

bot = commands.Bot(command_prefix='$', owner_id=OWNER_DISCORD_ID, help_command=None)

@bot.event
async def on_ready():
	print('We have logged in as {0.user}'.format(bot))
	DiscordComponents(bot)

@bot.command(aliases=['Rewards'])
@commands.dm_only()
async def rewards(ctx):
	with open(ROOT_PATH+"/stored_wallets.json", "r") as stored_wallet_list_json:
		stored_wallet_list = json.load(stored_wallet_list_json)

	with open(ROOT_PATH+"/daily_report_list.json", "r") as daily_report_list_json:
		daily_report_list = json.load(daily_report_list_json)
	
	message = await ctx.author.send("Pick a Surge Farm to calculate", delete_after=30,
		components =
		[Select(placeholder="Select a Surge Farm",
				options=[
					SelectOption(
						label="Show All", 
						value="all"
					),
					SelectOption(
						label="BNB - xUSD", 
						value="bnb-xusd"
					),
					SelectOption(
						label="SBTC - xUSD", 
						value="sbtc-xusd"
					),
					SelectOption(
						label="SADA - xUSD", 
						value="sada-xusd"
					)
				]
			)
		]
	)

	try:
		# Wait for the user to select a token
		event = await bot.wait_for("select_option", check = None, timeout = 30) # 30 seconds to reply
		farm = event.values[0]
		if farm == "all":
			response_messsge = "You selected Show All"
		else:
			response_messsge = "You selected "+surge_yield_farms[farm]['symbol']
		await ctx.author.send(response_messsge)
		# Delete the original drop down so the user can't interact with it again
		await message.delete()

		if str(ctx.author.id) not in stored_wallet_list: 
			message = 'Please enter your public BEP-20 wallet address:\n'
			await ctx.author.send(message)

			def check_message(msg):
				return msg.author == ctx.author and len(msg.content) > 0

			try:
				wallet_address_response = await bot.wait_for("message", check=check_message, timeout = 30) # 30 seconds to reply
				wallet_address = wallet_address_response.content
			except asyncio.TimeoutError:
				await ctx.send("Sorry, you either didn't reply with your wallet address or didn't reply in time!")
				return
		else:
			wallet_address = stored_wallet_list[str(ctx.author.id)]
		
		if farm == "all":
			await calculateAllYieldFarmRewards(ctx, wallet_address)
		else:
			await calculateYieldFarmRewards(ctx, farm, wallet_address)

		if str(ctx.author.id) not in stored_wallet_list:
			try:
				message2 = 'Do you want me to save your public BEP-20 wallet address for next time [Y/N]?\n'
				await ctx.author.send(message2)

				def check_message2(msg):
					return msg.author == ctx.author and len(msg.content) > 0

				store_wallet_response = await bot.wait_for("message", check=check_message2, timeout = 30) # 30 seconds to reply
				acceptable_responses = ['y','Y','yes','Yes']
				if store_wallet_response.content.lower() in acceptable_responses:
					stored_wallet_list[ctx.author.id] = wallet_address

					with open(ROOT_PATH+"/stored_wallets.json", "w") as stored_wallet_list_json:
						json.dump(stored_wallet_list, stored_wallet_list_json)
					
					await ctx.author.send("Thank you, you've been added to the stored wallet list.")
			except asyncio.TimeoutError:
				await ctx.send("Sorry, you either didn't reply in time!")
				return

		if str(ctx.author.id) not in daily_report_list:
			try:
				daily_report_list_message = 'Would you like to receive these reports daily [Y/N]?\n'
				daily_report_list_message += 'It will require me to save your wallet address so I can automatically send them to you.'
				await ctx.author.send(daily_report_list_message)

				def check_message(msg):
					return msg.author == ctx.author and len(msg.content) > 0
				
				daily_report_list_response = await bot.wait_for("message", check=check_message, timeout = 30) # 30 seconds to reply
				acceptable_responses = ['y','Y','yes','Yes']
				if daily_report_list_response.content.lower() in acceptable_responses:
					daily_report_list[ctx.author.id] = wallet_address

					with open(ROOT_PATH+"/daily_report_list.json", "w") as daily_report_list_json:
						json.dump(daily_report_list, daily_report_list_json)
					
					await ctx.author.send("Thank you, you've been added to the daily report list.")
			except asyncio.TimeoutError:
				await ctx.send("Sorry, you either didn't reply in time!")
				return
		return

	except discord.NotFound:
		return # not sure what to do here...
	except asyncio.TimeoutError:
		await ctx.author.send("Sorry, you didn't reply in time!")
		await message.delete()
		return
	# except Exception as e:
	# 	print(e)
	# 	#addErrorToLog(e, wallet_address.content)
	# 	# err_msg = str(e)+" : "+wallet_address.content
	# 	# logging.error(err_msg)
	# 	# await ctx.author.send("Sorry, something went wrong, please try again later.")
	# 	return
	return

@bot.command(aliases=['Remove_saved'])
@commands.dm_only()
async def remove_saved(ctx):
	with open(ROOT_PATH+"/stored_wallets.json", "r") as stored_wallet_list_json:
		stored_wallet_list = json.load(stored_wallet_list_json)
	
	if str(ctx.author.id) in stored_wallet_list:
		stored_wallet_list.pop(str(ctx.author.id))
		with open(ROOT_PATH+"/stored_wallets.json", "w") as stored_wallet_list_json:
			json.dump(stored_wallet_list, stored_wallet_list_json)

		await ctx.author.send("You have been removed from the stored wallet list.")
	else:
		await ctx.author.send("You are not in the stored wallet list.")
		
	return

@bot.command(aliases=['Remove_daily'])
@commands.dm_only()
async def remove_daily(ctx):
	with open(ROOT_PATH+"/daily_report_list.json", "r") as daily_report_list_json:
		daily_report_list = json.load(daily_report_list_json)
	
	if str(ctx.author.id) in daily_report_list:
		daily_report_list.pop(str(ctx.author.id))
		with open(ROOT_PATH+"/daily_report_list.json", "w") as daily_report_list_json:
			json.dump(daily_report_list, daily_report_list_json)

		await ctx.author.send("You have been removed from the daily send list.")
	else:
		await ctx.author.send("You are not in the daily send wallet list.")
		
	return

@bot.command(aliases=['Help'])
@commands.dm_only()
async def help(ctx):
	help_embed = createCustomHelpEmbedMessage()
	await ctx.author.send(embed=help_embed)

bot.run(SURGE_YIELD_FARM_BOT_KEY)