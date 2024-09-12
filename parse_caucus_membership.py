import rtyaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import datetime

class LegislatorInfo:
	def __init__(self):
		# Load current legislators.
		self.legislators_current = rtyaml.load(open("../congress-legislators/legislators-current.yaml"))

		# Make a map from bioguide ID to a summary to the legislator dict.
		self.id_map = { }
		for p in self.legislators_current:
			self.id_map[p['id']['bioguide']] = p

		# Make a map from legislator website URL domains to
		# bioguide IDs.
		self.website_map = { }
		for p in self.legislators_current:
			url = p['terms'][-1]['url']
			url = urlparse(url).netloc
			self.website_map[url] = p['id']['bioguide']

def new_democrat_coalition(cache):
	# Scan the New Dems website member list for links to
	# legislator pages.
	res = requests.get("https://newdemocratcoalition.house.gov/members")
	soup = BeautifulSoup(res.text, 'html.parser')
	newdems = set()
	for node in soup.find_all('a'):
		href = node.get('href')
		if href:
			href = urlparse(href).netloc
			if "house.gov" in href.lower() and href != "newdemocratcoalition.house.gov":
				if href not in cache.website_map:
					print("Failed to map legislator from", href)
				else:
					newdems.add(cache.website_map[href])
	return newdems


def save_caucus(caucus_name, filename, members, cache):
	# Sort members.
	members = list(members)
	members.sort()

	# Reformat.
	members = [
		{
			"id": key,
			"name": cache.id_map[key]["name"]["official_full"]
		}
	 	for key in members ]

	with open(filename, "w") as f:
		rtyaml.dump({
		            "name": caucus_name,
		            "updated": datetime.datetime.now().isoformat(),
		            "members": members }, f)


if __name__ == "__main__":
	# Pre-load some legislator info.
	cache = LegislatorInfo()
	save_caucus(
	            "New Democrat Coalition",
	            "newdemocratcoalition.yaml",
				new_democrat_coalition(cache),
				cache)
