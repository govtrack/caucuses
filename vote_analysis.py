import csv
import rtyaml
import glob
from collections import defaultdict

# Load ideology scores and party
ideology = { }
party = { }
for line in csv.DictReader(open("sponsorshipanalysis_h.txt")):
  ideology[int(line["ID"])] = float(line["ideology"])
  party[int(line["ID"])] = line["party"]

# Load bioguide ID to govtrack ID mapping.
legislators_current = rtyaml.load(open("../congress-legislators/legislators-current.yaml"))
id_map = { }
for p in legislators_current:
  id_map[p['id']['bioguide']] = p['id']['govtrack']

# Load caucus memberships.
caucus_membership = set()
for caucus in glob.glob("*.yaml"):
  caucusdata = rtyaml.load(open(caucus))
  caucus = caucus.replace(".yaml", "")
  for p in caucusdata["members"]:
    caucus_membership.add((caucus, id_map[p["id"]]))
all_caucuses = set(x[0] for x in caucus_membership)


# Make a map from legislator to Census region.
census_regions = {
  "Northeast": { "CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA" },
  "Midwest": { "IN", "IL", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD" },
  "South": { "DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX "},
  "West": { "AZ", "CO", "ID", "NM", "MT", "UT", "NV", "WY", "AK", "CA", "HI", "OR", "WA" },
}
census_region_map = { }
for p in legislators_current:
  state = p["terms"][-1]["state"]
  for region, states in census_regions.items():
    if state in states:
      break
  else:
    region = None
  census_region_map[p['id']['govtrack']] = region


# Run regressions

def regression(title, X, Y, exclude_features = set()):
  # Transform X from a list of dicts of factors to
  # a matrix with a defined order. Also transform
  # True to 1, False to -1, and None to 0. (We don't
  # do the same for Y because Logit requires Y in
  # [0, 1].)
  def to_number(value):
    if value is True: return 1
    if value is False: return -1
    if value is None: return 0
    return value
  from itertools import chain
  features = set(chain.from_iterable(set(x.keys()) for x in X))
  features -= exclude_features
  if len(features) == 0:
    return None
  features = sorted(features)
  X = [
    [to_number(x[key]) for key in features]
    for x in X
  ]

  # Run regression.

  #from statsmodels.api import OLS
  #model = OLS(Y, X)

  from statsmodels.discrete.discrete_model import Logit
  import numpy.linalg
  model = Logit(Y, X)
  import warnings
  with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Perfect separation")
    warnings.filterwarnings("ignore", message="divide by zero encountered")
    warnings.filterwarnings("ignore", message="overflow encountered in exp")
    try:
      fit = model.fit(maxiter=100, disp=False, warn_convergence=False) # disp silences stdout
    except numpy.linalg.LinAlgError:
      return None
  if not fit.converged: return None

  # Transform results back into a dictionary.
  fit = {
    "title": title,
    "rsquared": float(fit.prsquared), # .rsquared for OLS
    "features": {
      feature: {
        "value": float(fit.params[i]),
        "pvalue": float(fit.pvalues[i])
      }
      for i, feature in enumerate(features)
    }
  }

  return fit


def fit_best_model(title, X, Y):
  # Remove features iteratively from the model
  # that are non-significant 
  exclude_features = set()
  repeat = True
  last_fit_model = None
  while repeat:
    repeat = False
    model = regression(title, X, Y, exclude_features=exclude_features)
    if model is None:
      break
    last_fit_model = model
    for feature, params in model["features"].items():
      if feature == "intercept": continue # don't remove this one
      if params["pvalue"] > .01:
        exclude_features.add(feature)
        repeat = True
        break # only remove one feature at a time
  return last_fit_model

def predict_ideology():
  Y = [ ]
  X = [ ]
  for id in ideology:
    Y.append(ideology[id])
    X.append({
             "intercept": 1,
             "party_Republican": party[id] == "Republican",
             }
             |
             {
              "caucus_" + caucus: (caucus, id) in caucus_membership
              for caucus in all_caucuses
             })
  regression("ideology", X, Y)


def predict_all_votes():
  # Predict across all vote data (which is weird because
  # in some votes left will go toward Aye and in others
  # toward No, but since Rs have the majority probably it'll
  # mostly be No.).
  Y = [ ]
  X = [ ]
  for row in csv.DictReader(open("votes_118_house.csv")):
    vote = row["vote"]
    if vote not in ("Aye", "Yea", "No", "Nay"): continue
    vote = vote in ("Aye", "Yea")

    id = int(row["person"])

    Y.append(vote)
    X.append({
             "intercept": 1,
             "ideology": ideology[id],
             "party_Republican": party[id] == "Republican",
             }
             |
             {
              "caucus_" + caucus: (caucus, id) in caucus_membership
              for caucus in all_caucuses
             })
  regression("vote", X, Y)


# Fit individual votes
def load_all_votes():
  all_votes = defaultdict(lambda : [])
  for row in csv.DictReader(open("votes_118_house.csv")):
    vote = row["vote"]
    if vote not in ("Aye", "Yea", "No", "Nay"): continue
    vote = vote in ("Aye", "Yea")
    id = int(row["person"])
    vote_id = ":".join(row[key] for key in ("congress", "session", "chamber", "number"))
    all_votes[vote_id].append((id, vote))
  return all_votes.items()
def predict_vote(vote_id, votes):
  X = [ ]
  Y = [ ]
  for id, vote in votes:
    Y.append(vote)
    X.append({
             "intercept": 1,
             #"ideology": ideology[id],
             "party_Republican": party[id] == "Republican",
             }
             |
             {
              "censusregion_" + region: census_region_map.get(id) == region
              for region in census_regions
             }
             |
             {
              "caucus_" + caucus: (caucus, id) in caucus_membership
              for caucus in all_caucuses
             }
             )
  return fit_best_model(vote_id, X, Y)
for vote_id, votes in load_all_votes():
  model = predict_vote(vote_id, votes)
  if model:
    print(rtyaml.dump(model))
    print()


