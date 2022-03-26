import os
import json
from web3 import Web3
from pycoingecko import CoinGeckoAPI
import time
import random
import mysql.connector
from dotenv import load_dotenv

#load environment variables
load_dotenv()

ROOT_PATH = os.getenv('ROOT_PATH')

with open(ROOT_PATH+"/surge_yield_farms.json", "r") as surge_yield_farms_json:
	surge_yield_farms = json.load(surge_yield_farms_json)

bsc = "https://bsc-dataseed.binance.org/"
web3 = Web3(Web3.HTTPProvider(bsc))

cg = CoinGeckoAPI()

xusd_contract_address = '0x254246331cacbC0b2ea12bEF6632E4C6075f60e2'
xusd_contract_address = web3.toChecksumAddress(xusd_contract_address)

with open(ROOT_PATH+"/contract_abis/surge_xusd_abi.json", "r") as xusd_abi_json:
	xusd_contract_abi = json.load(xusd_abi_json)

xusd_contract = web3.eth.contract(address=xusd_contract_address, abi=xusd_contract_abi)

# Fetch all transactions for all surge tokens for a specific wallet
# def fetch_all_yield_farm_rewards(wallet_address):
# 	output = {}
# 	for farm in surge_yield_farms:
# 		result = fetch_yield_farm_rewards(wallet_address, farm)
# 		result = json.loads(result)
# 		output[farm] = result[farm]
# 	#return json.dumps(output)
# 	return output

# Fetch transactions for a specific surge token from a specific wallet
def fetch_yield_farm_rewards(wallet_address, farm):
	output = {
		farm: {}
	}

	if farm in surge_yield_farms:
		wallet_address = wallet_address.lower()
		wallet_address = web3.toChecksumAddress(wallet_address)

		contract_address = surge_yield_farms[farm]['address']
		contract_address = web3.toChecksumAddress(contract_address)

		farm_lp_address = surge_yield_farms[farm]['lp_address']
		farm_lp_address = web3.toChecksumAddress(farm_lp_address)

		with open(ROOT_PATH+"/farm_abis/"+farm+"_farm_abi.json", "r") as farm_abi:
			contract_abi = json.load(farm_abi)

		with open(ROOT_PATH+"/farm_lp_abis/"+farm+"_farm_lp_abi.json", "r") as farm_lp_abi_json:
			farm_lp_abi = json.load(farm_lp_abi_json)

		contract = web3.eth.contract(address=contract_address, abi=contract_abi)
		farm_lp_contract = web3.eth.contract(address=farm_lp_address, abi=farm_lp_abi)

		farm_balance = float(web3.fromWei(contract.functions.balanceOf(wallet_address).call(), 'ether'))

		if (farm_balance > 0):
			#setup DB connection
			mydb = mysql.connector.connect(
				host = os.getenv('DB_HOST'),
				user = os.getenv('DB_USERNAME'),
				password = os.getenv('DB_PASSWORD'),
				database = os.getenv('DB_DATABASE'), 
			)

			mycursor = mydb.cursor()

			current_xusd_price = float(web3.fromWei(xusd_contract.functions.calculatePrice().call(), 'ether'))

			output[farm]['balance'] = farm_balance

			farm_total_supply = float(web3.fromWei(contract.functions.totalSupply().call(), 'ether'))
			lp_total_supply = float(web3.fromWei(farm_lp_contract.functions.totalSupply().call(), 'ether'))

			redeemable_value_result = contract.functions.getRedeemableValue(wallet_address).call()
			xusd_value = float(web3.fromWei(redeemable_value_result[0], 'ether'))
			output[farm]['xusd_value'] = xusd_value * (lp_total_supply/farm_total_supply)

			if surge_yield_farms[farm]["is_paired_asset_surge_token"]:
				paired_asset_value = redeemable_value_result[1]
				paired_asset_value = paired_asset_value * (lp_total_supply/farm_total_supply)
				output[farm]['paired_asset_value'] = f'{paired_asset_value:,.0f}'
			else:
				paired_asset_value = float(web3.fromWei(redeemable_value_result[1], 'ether'))
				paired_asset_value = paired_asset_value * (lp_total_supply/farm_total_supply)
				output[farm]['paired_asset_value'] = paired_asset_value

			lp_farm_xusd_usd_value = xusd_value * current_xusd_price

			sql = "SELECT * FROM `"+surge_yield_farms[farm]['values_table']+"_values` WHERE 1 ORDER BY `id` DESC LIMIT 1"
			mycursor.execute(sql)
			myresult = mycursor.fetchall()

			current_token_value_data = json.loads(myresult[0][3])
			current_token_value_data['token_value'] = float(current_token_value_data['token_value'])
			current_token_value_data['underlying_asset_value'] = float(current_token_value_data['underlying_asset_value'])

			if surge_yield_farms[farm]['split_rewards']:
				lp_farm_paired_asset_usd_value = paired_asset_value * current_token_value_data['token_value'] * current_token_value_data['underlying_asset_value']
			else:
				lp_farm_paired_asset_usd_value = paired_asset_value * current_token_value_data['underlying_asset_value']

			total_lp_farm_balance = lp_farm_xusd_usd_value + lp_farm_paired_asset_usd_value
			
			output[farm]['total_lp_farm_balance_usd'] = f'{total_lp_farm_balance:,.2f}'

			time_until_unlock = contract.functions.getTimeUntilUnlock(wallet_address).call()
			time_until_unlock = (time_until_unlock*3)/60/60/24
			time_until_unlock = f'{time_until_unlock:.0f}'

			output[farm]['time_until_unlock'] = time_until_unlock

			pending_rewards = contract.functions.pendingRewards(wallet_address).call()

			if surge_yield_farms[farm]['split_rewards']:
				output[farm]['pending_rewards_xusd'] = float(web3.fromWei(pending_rewards[0], 'ether'))
				prending_rewards_xusd_usd = output[farm]['pending_rewards_xusd'] * current_xusd_price
				output[farm]['pending_rewards_xusd_in_usd'] = f'{prending_rewards_xusd_usd:,.2f}'

				if surge_yield_farms[farm]["is_paired_asset_surge_token"]: 
					output[farm]['pending_rewards_paired_asset'] = f'{pending_rewards[1]:,.0f}'
				else:
					output[farm]['pending_rewards_paired_asset'] = pending_rewards[1]
				prending_rewards_paired_asset_usd = pending_rewards[1] * current_token_value_data['token_value'] * current_token_value_data['underlying_asset_value']
				output[farm]['pending_rewards_paired_asset_in_usd'] = f'{prending_rewards_paired_asset_usd:.2f}'

				output[farm]['pending_rewards_usd'] = f'{prending_rewards_xusd_usd + prending_rewards_paired_asset_usd:,.2f}'
			else:
				output[farm]['pending_rewards_xusd'] = float(web3.fromWei(pending_rewards, 'ether'))
				prending_rewards_xusd_usd = output[farm]['pending_rewards_xusd'] * current_xusd_price
				output[farm]['pending_rewards_xusd_in_usd'] = f'{prending_rewards_xusd_usd:,.2f}'

				output[farm]['pending_rewards_usd'] = f'{prending_rewards_xusd_usd:,.2f}'
				
			total_rewards = contract.functions.totalRewardsClaimedForUser(wallet_address).call()
			
			if surge_yield_farms[farm]['split_rewards']:
				output[farm]['total_rewards_xusd'] = float(web3.fromWei(total_rewards[0], 'ether'))
				output[farm]['total_rewards_paired_asset'] = total_rewards[1]

				if surge_yield_farms[farm]["is_paired_asset_surge_token"]: 
					output[farm]['total_rewards_paired_asset'] =  f'{total_rewards[1]:,.0f}'
				else:
					output[farm]['total_rewards_paired_asset'] = total_rewards[1]

			else:
				output[farm]['total_rewards_xusd'] = float(web3.fromWei(total_rewards, 'ether'))

			mycursor.close()
			mydb.close()

			return json.dumps(output)
		else:
			return json.dumps(output)
	else:
		raise ValueError("Invalid farm supplied: "+farm)