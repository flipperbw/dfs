#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import requests
import pandas
from bs4 import BeautifulSoup
import pulp
from numpy import random, ceil
import MySQLdb
from datetime import datetime, timedelta

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
week = ceil((current_time - datetime.strptime('2013-09-03', '%Y-%m-%d')).days/7.0)
gamedate = (current_time + timedelta((6 - current_time.weekday()) % 7)).date()

mydb = MySQLdb.connect(host="localhost", user='root', db="dfs")
mycursor = mydb.cursor()
mycursor.execute('delete from optimization where week = %s and sport = "nfl"' % week)

site_settings = {
	"draft-street": {
		"caps": [97159, 95569],
		"roster": {
			"qb": 2,
			"rb": 2,
			"wr": 2,
			"te": 1,
			"flex": 2,
			"dst": 0,
			"k": 0
		},
		
		"scoring": {
			"pass_tds": 4,
			"pass_yds": 0.04,
			"pass_ints": -1,
			"bonus_300": 0,
			
			"td": 6,
			"yd": 0.1,
			"rec": 0.5,
			"bonus_100": 0,
			
			"fumbles": -1,
			
			"dp": 12,
			"dpa": -0.5,
			"dint": 1,
			"fr": 1,
			"sack": 0.5,
			"sfty": 2,
			
			"xpt": 0,
			"fg": 0

		}
	}
}

#- Get projected stats
dataframes = {}
positions = ('qb','rb','wr','te','k')
for p in positions:
	ts = requests.get('http://www.fantasypros.com/nfl/projections/%s.php?export=xls&max-yes=true&min-yes=true' % p).text
	ts_split = [i.strip().split('\t') for i in ts.strip().split('\n')[4:]]
	
	headers = [r.strip() for r in ts_split[0]]
	data = ts_split[1:]

	#- Name mismatch fixes
	for d in data:
		if p == 'dst' and ' ' in d[0] and '(' not in d[0]:
			dsplit = d[0].split()
			data.append([dsplit[-1]] + d[1:])
			if len(dsplit) == 3:
				data.append(['%s (%s)' % (dsplit[-1], dsplit[0][0] + dsplit[1][0])] + d[1:])
			elif len(dsplit) == 2:
				data.append(['%s (%s)' % (dsplit[-1], dsplit[0][:3])] + d[1:])
			if d[0] == 'St. Louis Rams':
				data.append(['St Louis Rams'] + d[1:])
				data.append(['Rams (StL)'] + d[1:])
			elif d[0] == 'New York Jets':
				data.append(['Jets (NYJ)'] + d[1:])
			elif d[0] == 'New York Giants':
				data.append(['Giants (NYG)'] + d[1:])
		elif d[0] == 'Ty Hilton':
			data.append(['T.Y. Hilton'] + d[1:])
			data.append(['TY Hilton'] + d[1:])
		elif d[0] == 'Christopher Ivory':
			data.append(['Chris Ivory'] + d[1:])
		elif d[0] == 'Robert Housler':
			data.append(['Rob Housler'] + d[1:])
		elif d[0] == 'Josh Morgan':
			data.append(['Joshua Morgan'] + d[1:])
		elif d[0] == 'Ted Ginn Jr.':
			data.append(['Ted Ginn'] + d[1:])
		elif d[0] == 'C.J. Spiller':
			data.append(['CJ Spiller'] + d[1:])
		elif d[0] == 'Le\'Veon Bell':
			data.append(['LeVeon Bell'] + d[1:])
		elif d[0] == 'A.J. Green':
			data.append(['AJ Green'] + d[1:])
		elif d[0] == 'A.J. Jenkins':
			data.append(['AJ Jenkins'] + d[1:])
		elif d[0] == 'Tim Wright':
			data.append(['Timothy Wright'] + d[1:])
	
	df = pandas.DataFrame(data, columns=headers)
	
	#- Add columns for up and down scenarios
	for metr in ('pass_yds','pass_tds','pass_ints','rec_yds','rec_tds','rec_att','rush_yds','rush_tds','fumbles','def_pa','def_td','def_int','def_fr','def_sack','def_safety','xpt','fg'):
		try:
			df['%s_h' % metr] = df.apply(lambda row: float(row['%s High' % metr]) - float(row[metr]), axis=1)
			df['%s_l' % metr] = df.apply(lambda row: float(row[metr]) - float(row['%s Low' % metr]), axis=1)
		except KeyError:
			pass

	dataframes[p] = df

def get_pandas_value(metric):
	try:
		met_val = pd[metric].values[0]
	except KeyError:
		met_val = 0
	return float(met_val)

#- Calculate projected points for each site
for k in site_settings.keys():
	player_data = {}
	player_data_1 = {}
	player_data_2 = {}
	site = site_settings[k]
	roster = site['roster']
	caps = site['caps']
	scoring = site['scoring']
	
	print '====================>  Optimizing site: ', k, ' <===================='

	dfs = requests.get('http://dfsedge.com/tools/?site=%s' % k).text
	soup = BeautifulSoup(dfs)

	dfs_table = soup.find(id='ALLTab').table.tbody.find_all('tr')

	factor_1 = -0.8
	factor_2 = 0.8
				
	for player in dfs_table:
		tds = player.find_all('td')
		
		name = tds[1].string.strip()
		pos = tds[2].string.lower()
		sal = int(tds[3].string.strip().replace('$','').replace(',',''))
		
		if pos != 'dst':
			pd = dataframes[pos].get(dataframes[pos]["Player Name"] == '%s' % name)
			if not pd:
				print 'Could not match name for dfsedge/fantasypros: %s' % name
			else:
				player_data[name] = [pos, sal]
				
				for fac in (0,factor_1,factor_2):
					if fac > 0:
						modifier = '_h'
					elif fac < 0:
						modifier = '_l'
					else:
						modifier = ''
					
					payd = ((get_pandas_value('pass_yds%s' % modifier) * fac) + get_pandas_value('pass_yds')) * scoring['pass_yds']
					patd = ((get_pandas_value('pass_tds%s' % modifier) * fac) + get_pandas_value('pass_tds')) * scoring['pass_tds']
					paint = ((get_pandas_value('pass_ints%s' % modifier) * fac) + get_pandas_value('pass_ints')) * scoring['pass_ints']
					pabonus = (payd > 300) * scoring['bonus_300']
					
					td = (((get_pandas_value('rec_tds%s' % modifier) * fac) + get_pandas_value('rec_tds')) + ((get_pandas_value('rush_tds%s' % modifier) * fac) + get_pandas_value('rush_tds')) + ((get_pandas_value('def_td%s' % modifier) * fac) + get_pandas_value('def_td'))) * scoring['td']
					yd = (((get_pandas_value('rec_yds%s' % modifier) * fac) + get_pandas_value('rec_yds')) + ((get_pandas_value('rush_yds%s' % modifier) * fac) + get_pandas_value('rush_yds'))) * scoring['yd']
					rec = ((get_pandas_value('rec_att%s' % modifier) * fac) + get_pandas_value('rec_att')) * scoring['rec']
					bonus = (yd > 100) * scoring['bonus_100']
					
					fumble = ((get_pandas_value('fumbles%s' % modifier) * fac) + get_pandas_value('fumbles')) * scoring['fumbles']
					
					ddp = (pos == 'dst') * scoring['dp']
					dpa = ((get_pandas_value('def_pa%s' % modifier) * fac) + get_pandas_value('def_pa')) * scoring['dpa']
					dint = ((get_pandas_value('def_int%s' % modifier) * fac) + get_pandas_value('def_int')) * scoring['dint']
					fr = ((get_pandas_value('def_fr%s' % modifier) * fac) + get_pandas_value('def_fr')) * scoring['fr']
					sack = ((get_pandas_value('def_sack%s' % modifier) * fac) + get_pandas_value('def_sack')) * scoring['sack']
					sfty = ((get_pandas_value('def_safety%s' % modifier) * fac) + get_pandas_value('def_safety')) * scoring['sfty']
					
					xpt = ((get_pandas_value('xpt%s' % modifier) * fac) + get_pandas_value('xpt')) * scoring['xpt']
					fg = ((get_pandas_value('fg%s' % modifier) * fac) + get_pandas_value('fg')) * scoring['fg']
					
					#- Now calculate the sum of points
					points = payd + patd + paint + pabonus + td + yd + rec + bonus + fumble + ddp + dpa + dint + fr + sack + sfty + xpt + fg
					
					player_data[name].append(points)

				mycursor.execute('insert into players values ("%s", "%s", "%s", "nfl", %s, "%s, %s, %s, %s, %s, "%s") on duplicate key update salary = %s, points = %s, points_1 = %s, points_2 = %s, updated = "%s";' % (name, player_data[name][0], k, week, gamedate, player_data[name][1], player_data[name][2], player_data[name][3], player_data[name][4], current_time, player_data[name][1], player_data[name][2], player_data[name][3], player_data[name][4], current_time))

	player_names = {"qb":[], "rb":[], "wr": [], "te": [], "k":[]}
	for pl in player_data.keys():
		player_names[player_data[pl][0]].append(pl)
		
	qb_names = player_names['qb']
	rb_names = player_names['rb']
	wr_names = player_names['wr']
	te_names = player_names['te']
	flex_names = rb_names + wr_names + te_names
	k_names = player_names['k']
	all_names = qb_names + rb_names + wr_names + te_names + k_names

	for cap in caps:
		print '----- Cap of %s -----' % cap
		for points_type in (2,3,4):
			if points_type == 2:
				print '-> Normal Run <-'
				pt = 'norm'
			elif points_type == 3:
				print '-> Random Run #1 <-'
				pt = 'rand1'
			else:
				print '-> Random Run #2 <-'
				pt = 'rand2'

			prob = pulp.LpProblem("%s Optimization" % k, pulp.LpMaximize)
			
			#- Set the variables (boolean player names)
			player_vars = pulp.LpVariable.dicts("Players", all_names, cat="Binary")
			
			#- Set the objective (maximize points)
			prob += pulp.lpSum([player_data[i][points_type] * player_vars[i] for i in all_names]), "Total Points"
			
			#- Set the contraints (budget and then roster)
			prob += pulp.lpSum([player_data[i][1] * player_vars[i] for i in all_names]) <= cap, "Total Cost"
			
			prob += pulp.lpSum([player_vars[i] for i in qb_names]) == roster['qb'], "Total QBs"
			prob += pulp.lpSum([player_vars[i] for i in rb_names]) >= roster['rb'], "Total RBs"
			prob += pulp.lpSum([player_vars[i] for i in wr_names]) >= roster['wr'], "Total WRs"
			prob += pulp.lpSum([player_vars[i] for i in te_names]) >= roster['te'], "Total TEs"
			prob += pulp.lpSum([player_vars[i] for i in flex_names]) == roster['rb'] + roster['wr'] + roster['te'] + roster['flex'], "Total Flexs"
			prob += pulp.lpSum([player_vars[i] for i in k_names]) == roster['k'], "Total Ks"

			#- Solve
			prob.writeLP("%s.lp" % k)
			prob.solve()
			#prob.solve(pulp.GLPK())
			
			if pulp.LpStatus[prob.status] != 'Optimal':
				print 'Status not optimal -> %s' % pulp.LpStatus[prob.status]
			else:
				new_player_vars = {}
				for on,nn in player_vars.iteritems():
					new_player_vars[nn.name] = on
				
				solution = {"qb": [], "rb": [], "wr": [], "te": [], "flex": [], "k": []}
				total_salary = 0
				rb_count = wr_count = te_count = 0
				for v in prob.variables():
					if v.varValue == 1:
						old_name = new_player_vars[v.name]
						
						if player_data[old_name][0] == 'rb':
							if rb_count < roster['rb']:
								solution[player_data[old_name][0]].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
								rb_count += 1
							else:
								solution["flex"].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
						elif player_data[old_name][0] == 'wr':
							if wr_count < roster['wr']:
								solution[player_data[old_name][0]].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
								wr_count += 1
							else:
								solution["flex"].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
						elif player_data[old_name][0] == 'te':
							if te_count < roster['te']:
								solution[player_data[old_name][0]].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
								te_count += 1
							else:
								solution["flex"].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
						else:
							solution[player_data[old_name][0]].append((old_name, player_data[old_name][1], player_data[old_name][points_type]))
						
						total_salary += player_data[old_name][1]
			
						mycursor.execute('insert into optimization values("%s", "%s", "nfl", %s, "%s", %s, "%s", "%s");' % (old_name, k, week, gamedate, cap, pt, current_time))

				print "%-*s: %-*s%-*s%s" % (5, 'Pos', 25, 'Player', 10, 'Cost', 'Points')
				for pp in solution['qb']:
					print "%-*s: %-*s%-*s%s" % (5, 'QB', 25, pp[0], 10, pp[1], pp[2])
				for pp in solution['rb']:
					print "%-*s: %-*s%-*s%s" % (5, 'RB', 25, pp[0], 10, pp[1], pp[2])
				for pp in solution['wr']:
					print "%-*s: %-*s%-*s%s" % (5, 'WR', 25, pp[0], 10, pp[1], pp[2])
				for pp in solution['te']:
					print "%-*s: %-*s%-*s%s" % (5, 'TE', 25, pp[0], 10, pp[1], pp[2])
				for pp in solution['flex']:
					print "%-*s: %-*s%-*s%s" % (5, 'Flex', 25, pp[0], 10, pp[1], pp[2])
				for pp in solution['k']:
					print "%-*s: %-*s%-*s%s" % (5, 'K', 25, pp[0], 10, pp[1], pp[2])
				
				print "Total Points: ", pulp.value(prob.objective)
				print "Total Salary: %s (%s%% of %s)" % (total_salary, (total_salary*1.0/cap*1.0)*100.0, cap)

				print '====================>  Done  (', k, ') <===================='
