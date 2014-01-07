#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import requests
import pandas
from bs4 import BeautifulSoup
import pulp
from numpy import random, ceil
import MySQLdb
from datetime import datetime, timedelta
import re

# TODO
#-- INJURIES. avoid q's? limit experts in FP to those updated most recently (on sunday)
#-- remove zeroes when assigning df to speed it up
#-- more loops?
#-- automatically submit
#-- nba adjustments
#-- better formatting
#-- backtesting with data from old games
#-- what to do when player is two positions? cory harkey
#-- add more projections (yahoo, nfl, fleaflicker?)
#-- fix dst and K scoring
#-- when do salaries update? do it earlier? auto adjust?
#-- single factor for all? up and down scenario?
#-- use player scoring stddev

current_time = datetime.now()
week = ceil((current_time - datetime.strptime('2013-10-29', '%Y-%m-%d')).days/7.0)
gamedate = current_time.date()

mydb = MySQLdb.connect(host="localhost", user='root', db="dfs")
mycursor = mydb.cursor()
mycursor.execute('delete from optimization where date = "%s" and sport = "nba"' % gamedate)

site_settings = {
        "draft-street": {
                "caps": [100000],
                "roster": {
                        "pg": 0,
                        "sg": 0,
                        "pf": 0,
                        "sf": 0,
                        "c": 1,
                        "g": 3,
                        "f": 3,
                        "u": 1
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": -0.5,
                        "mfg": -0.5,

                        "dd": 0,
                        "td": 0
                }
        },

        "draftkings": {
                "caps": [50000],
                "roster": {
                        "pg": 1,
                        "sg": 1,
                        "pf": 1,
                        "sf": 1,
                        "c": 1,
                        "g": 1,
                        "f": 1,
                        "u": 1
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0.5,

                        "to": -0.5,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 1.5,
                        "td": 3
                }
        },

        "fanthrowdown": {
                "caps": [100000], #maybe others, none listed
                "roster": {
                        "pg": 2,
                        "sg": 2,
                        "pf": 2,
                        "sf": 2,
                        "c": 1,
                        "g": 0,
                        "f": 0,
                        "u": 1
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 0,
                        "td": 0
                }
        },

        "fantasyaces": {
                "caps": [50000,55000], #unclear which. also salarypro, not sure what that is
                "roster": {
                        "pg": 0,
                        "sg": 0,
                        "pf": 0,
                        "sf": 0,
                        "c": 1,
                        "g": 3,
                        "f": 3,
                        "u": 2
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 0,
                        "td": 0
                }
        },

        "starstreet": {
                "caps": [100000],
                "roster": {
                        "pg": 1,
                        "sg": 1,
                        "pf": 1,
                        "sf": 1,
                        "c": 1,
                        "g": 1,
                        "f": 1,
                        "u": 2
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 0,
                        "td": 0
                }
        },

        "fantasy-feud": {
                "caps": [1000000],
                "roster": {
                        "pg": 0,
                        "sg": 0,
                        "pf": 0,
                        "sf": 0,
                        "c": 2,
                        "g": 3,
                        "f": 3,
                        "u": 2
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 0,
                        "td": 0
                }
        },

        "fan-duel": {
                "caps": [55000,60000,65000],
                "roster": {
                        "pg": 2,
                        "sg": 2,
                        "pf": 2,
                        "sf": 2,
                        "c": 1,
                        "g": 0,
                        "f": 0,
                        "u": 0
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.2,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": 0,
                        "mfg": 0,

                        "dd": 0,
                        "td": 0
                }
        },

        "draftday": {
                "caps": [100000],
                "roster": {
                        "pg": 2,
                        "sg": 2,
                        "pf": 2,
                        "sf": 2,
                        "c": 1,
                        "g": 0,
                        "f": 0,
                        "u": 0
                },

                "scoring": {
                        "pts": 1,
                        "reb": 1.25,
                        "ast": 1.5,
                        "stl": 2,
                        "blk": 2,
                        "bonus_3pt": 0,

                        "to": -1,
                        "mft": -0.25,
                        "mfg": -0.25,

                        "dd": 0,
                        "td": 0
                }
        }
}


#- Calculate projected points for each site
for k in site_settings.keys():
	player_data = {}
	position_data = {}

	site = site_settings[k]
	caps = site['caps']
	roster = site['roster']
	
	for ps in roster.keys():
		position_data[ps] = []
	
	print '====================>  Optimizing site: ', k, ' <===================='

	dfs = requests.get('http://dfsedge.com/nba-tool/?site=%s' % k).text
	soup = BeautifulSoup(dfs)

	dfs_table = soup.find(id='UTILTab').table.tbody.find_all('tr')

	for player in dfs_table:
		tds = player.find_all('td')
		
		name = tds[1].string.strip()
		pos = tds[2].string.lower()
		sal = int(tds[3].string.strip().replace('$','').replace(',',''))
		pts = float(tds[7].string.strip())
		
		#if tds[4].span.string in ('MEM', 'DET'):
		#	continue

		positions = re.findall(r'[\w]+', pos)
		player_data[name] = (positions, sal, pts)
		for p in positions:
			position_data[p].append(name)
			if name not in position_data[p[-1]]:
				position_data[p[-1]].append(name)

			mycursor.execute('insert into players values ("%s", "%s", "%s", "nba", %s, "%s", %s, %s, %s, %s, "%s") on duplicate key update salary = %s, points = %s, points_1 = %s, points_2 = %s, updated = "%s";' % (name, p, k, week, gamedate, player_data[name][1], player_data[name][2], player_data[name][2], player_data[name][2], current_time, player_data[name][1], player_data[name][2], player_data[name][2], player_data[name][2], current_time))

	pg_names = position_data['pg']
	sg_names = position_data['sg']
	pf_names = position_data['pf']
	sf_names = position_data['sf']
	c_names = position_data['c']
	g_names = position_data['g']
	f_names = position_data['f']
	all_names = set(c_names + g_names + f_names)

	for cap in caps:
		print '----- Cap of %s -----' % cap
		prob = pulp.LpProblem("%s Optimization" % k, pulp.LpMaximize)
		
		#- Set the variables (boolean player names)
		player_vars = pulp.LpVariable.dicts("Players", all_names, cat="Binary")
		
		#- Set the objective (maximize points)
		prob += pulp.lpSum([player_data[i][2] * player_vars[i] for i in all_names]), "Total Points"
		
		#- Set the contraints (budget and then roster)
		prob += pulp.lpSum([player_data[i][1] * player_vars[i] for i in all_names]) <= cap, "Total Cost"
		
		prob += pulp.lpSum([player_vars[i] for i in pg_names]) >= roster['pg'], "Total PGs"
		prob += pulp.lpSum([player_vars[i] for i in sg_names]) >= roster['sg'], "Total SGs"
		prob += pulp.lpSum([player_vars[i] for i in pf_names]) >= roster['pf'], "Total PFs"
		prob += pulp.lpSum([player_vars[i] for i in sf_names]) >= roster['sf'], "Total SFs"
		prob += pulp.lpSum([player_vars[i] for i in c_names]) >= roster['c'], "Total Cs"
		prob += pulp.lpSum([player_vars[i] for i in g_names]) >= roster['pg'] + roster['sg'] + roster['g'], "Total Gs"
		prob += pulp.lpSum([player_vars[i] for i in f_names]) >= roster['pf'] + roster['sf'] + roster['f'], "Total Fs"
		prob += pulp.lpSum([player_vars[i] for i in all_names]) == roster['pg'] + roster['sg'] + roster['pf'] + roster['sf'] + roster['c'] + roster['g'] + roster['f'] + roster['u'], "Total Us"

		#- Solve
		prob.writeLP("%s.lp" % k)
		prob.solve()
		
		if pulp.LpStatus[prob.status] != 'Optimal':
			print 'Status not optimal -> %s' % pulp.LpStatus[prob.status]
		else:
			new_player_vars = {}
			for on,nn in player_vars.iteritems():
				new_player_vars[nn.name] = on
			
			total_salary = 0
			
			print "%-*s%-*s%-*s%s" % (25, 'Player', 10, 'Pos', 10, 'Cost', 'Points')
			for v in prob.variables():
				if v.varValue == 1:
					old_name = new_player_vars[v.name]
					po = player_data[old_name][0]
					sal = player_data[old_name][1]
					pts = player_data[old_name][2]
					
					total_salary += sal

					mycursor.execute('insert into optimization values("%s", "%s", "nba", %s, "%s", %s, "%s", "%s");' % (old_name, k, week, gamedate, cap, 'norm', current_time))
			
					print "%-*s%-*s%-*s%s" % (25, old_name, 10, '/'.join(up.upper() for up in po), 10, sal, pts)
			
			print "Total Points: ", pulp.value(prob.objective)
			print "Total Salary: %s (%s%% of %s)" % (total_salary, (total_salary*1.0/cap*1.0)*100.0, cap)

			print '====================>  Done  (', k, ') <===================='
