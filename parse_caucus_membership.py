import rtyaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import datetime
from collections import defaultdict
import unicodedata


headers = {
    'User-Agent': 'Mozilla',
}


class LegislatorInfo:
  def __init__(self):
    # Load current legislators.
    self.legislators_current = rtyaml.load(open("../congress-legislators/legislators-current.yaml"))

    # Make a map from bioguide ID to a summary to the legislator dict.
    self.id_map = { }
    for p in self.legislators_current:
      self.id_map[p['id']['bioguide']] = p

    # Make a map from legislator names to IDs.
    self.name_map = { }
    for p in self.legislators_current:
      name = p['name']['official_full']
      self.name_map[name] = p['id']['bioguide']
      self.name_map[u"".join(c for c in unicodedata.normalize('NFKD', name)
                             if not unicodedata.combining(c))] = p['id']['bioguide']

    # Make a map from legislator names to IDs.
    self.last_name_map = defaultdict(lambda : set())
    for p in self.legislators_current:
      self.last_name_map[p['name']['last']].add(p['id']['bioguide'])

    # Make a map from legislator website URL domains to
    # bioguide IDs.
    self.website_map = { }
    for p in self.legislators_current:
      url = p['terms'][-1]['url']
      url = urlparse(url).netloc
      self.website_map[url] = p['id']['bioguide']


def scrape_for_legislator_homepage_links(url, exclude_urls, cache):
  # Scan the New Dems website member list for links to
  # legislator pages.
  res = requests.get(url)
  soup = BeautifulSoup(res.text, 'html.parser')
  members = set()
  for node in soup.find_all('a'):
    href = node.get('href')
    if href:
      href = urlparse(href).netloc
      if "house.gov" in href.lower() and href not in exclude_urls:
        if href not in cache.website_map:
          print("Failed to map legislator from", href, "in", url)
        else:
          members.add(cache.website_map[href])
  return members


def republican_study_committee(cache):
  res = requests.get("https://rsc-hern.house.gov/about/membership")
  soup = BeautifulSoup(res.text, 'html.parser')
  members = set()
  for node in soup.select('.each-member-name'):
    name = node.string\
      .replace("Rep. ", "")\
      .replace("Chairman ", "")\
      .replace("Speaker ", "")\
      .replace("Majority Leader ", "")\
      .replace("Minority Leader ", "")\
      .replace("  ", " ")\
      .strip()
    if name in cache.name_map:
      members.add(cache.name_map[name])
      continue
    last_name = name.split(" ")[-1]
    if last_name in cache.last_name_map and len(cache.last_name_map[last_name]) == 1:
      members.add(list(cache.last_name_map[last_name])[0])
      continue
    print("Failed to map RSC legislator from", name)
  return members


def republican_governance_group(cache):
  res = requests.get("https://republicangovernance.com/", headers=headers)
  soup = BeautifulSoup(res.text, 'html.parser')
  members = set()
  for node in soup.select('.genlist li'):
    if not node.string: continue
    name = node.string\
      .replace("Congressman ", "")\
      .replace("Congresswoman ", "")\
      .strip()
    if name in cache.name_map:
      members.add(cache.name_map[name])
      continue
    last_name = name.split(" ")[-1]
    if last_name in cache.last_name_map and len(cache.last_name_map[last_name]) == 1:
      members.add(list(cache.last_name_map[last_name])[0])
      continue
    print("Failed to map RGG legislator from", name)
  return members


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
              "Republican Study Committee",
              "republicanstudy.yaml",
              republican_study_committee(cache),
              cache)
  save_caucus(
              "Republican Governance Group",
              "republicangovernance.yaml",
              republican_governance_group(cache),
              cache)
  save_caucus(
              "New Democrat Coalition",
              "newdems.yaml",
              scrape_for_legislator_homepage_links("https://newdemocratcoalition.house.gov/members",
                                                   { "newdemocratcoalition.house.gov" }, cache),
              cache)
  save_caucus(
              "Congressional Progressive Caucus",
              "congressionalprogressive.yaml",
              scrape_for_legislator_homepage_links("https://progressives.house.gov/caucus-members",
                                                   { "" }, cache),
              cache)
  save_caucus(
              "Problem Solvers Caucus",
              "problemsolvers.yaml",
              scrape_for_legislator_homepage_links("https://problemsolverscaucus.house.gov/caucus-members",
                                                   { "www.house.gov" }, cache),
              cache)
  save_caucus(
              "Blue Dog Coalition",
              "bluedog.yaml",
              scrape_for_legislator_homepage_links("https://bluedogcaucus-golden.house.gov/members",
                                                   { "www.house.gov", "bluedogcaucus-golden.house.gov" }, cache),
              cache)
save_caucus(
              "Main Street Caucus",
              "mainstreet.yaml",
              scrape_for_legislator_homepage_links("https://mainstreetcaucus.house.gov/membership",
                                                   { "www.house.gov" }, cache),
              cache)