import os
import json
from web3 import Web3
from pycoingecko import CoinGeckoAPI
import time
import random
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
def fetch_all_yield_farm_rewards(wallet_address):
	output = {}
	for farm in surge_yield_farms:
		result = fetch_yield_farm_rewards(wallet_address, farm)
		result = json.loads(result)
		output[farm] = result[farm]
	#return json.dumps(output)
	return output

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

		with open(ROOT_PATH+"/farm_abis/"+farm+"-farm-abi.json", "r") as farm_abi:
			contract_abi = json.load(farm_abi)

		contract = web3.eth.contract(address=contract_address, abi=contract_abi)

		farm_balance = float(web3.fromWei(contract.functions.balanceOf(wallet_address).call(), 'ether'))

		if (farm_balance > 0):
			current_xusd_price = float(web3.fromWei(xusd_contract.functions.calculatePrice().call(), 'ether'))

			output[farm]['balance'] = farm_balance

			redeemable_value_result = contract.functions.getRedeemableValue(wallet_address).call()
			xusd_value = float(web3.fromWei(redeemable_value_result[0], 'ether'))
			bnb_value = float(web3.fromWei(redeemable_value_result[1], 'ether'))

			output[farm]['xusd_value'] = xusd_value
			output[farm]['bnb_value'] = bnb_value

			lp_farm_xusd = xusd_value * current_xusd_price

			response = cg.get_price(ids='binancecoin', vs_currencies='usd')
			lp_farm_bnb = bnb_value * response['binancecoin']['usd']

			total_lp_farm_balance = lp_farm_xusd + lp_farm_bnb
			
			output[farm]['total_lp_farm_balance'] = f'{total_lp_farm_balance:.2f}'

			time_until_next_claim = contract.functions.getTimeUntilNextClaim(wallet_address).call()
			time_until_next_claim = time_until_next_claim*3

			output[farm]['time_until_next_claim'] = time_until_next_claim

			time_until_unlock = contract.functions.getTimeUntilUnlock(wallet_address).call()
			time_until_unlock = (time_until_unlock*3)/60/60/24
			time_until_unlock = f'{time_until_unlock:.0f}'

			output[farm]['time_until_unlock'] = time_until_unlock

			pending_rewards = float(web3.fromWei(contract.functions.pendingRewards(wallet_address).call(), 'ether'))

			output[farm]['pending_rewards'] = pending_rewards
			prending_rewards_usd = pending_rewards * current_xusd_price
			output[farm]['pending_rewards_in_usd'] = f'{prending_rewards_usd:.2f}'

			total_rewards = float(web3.fromWei(contract.functions.totalRewardsClaimedForUser(wallet_address).call(), 'ether'))

			output[farm]['total_rewards'] = total_rewards

			return json.dumps(output)
		else:
			return json.dumps(output)
	else:
		raise ValueError("Invalid farm supplied: "+farm)