import gurobipy as gp
from gurobipy import GRB
import pandas as pd
from collections import defaultdict
import argparse
from datetime import datetime
import csv

# Default Data
data = pd.read_csv('minutes.csv')

#scale the minutes
_max = data['MPG'].max()
_min = data['MPG'].min()
data['MPG'] = (data['MPG'] - _min) / (_max - _min) + 1

minutes = dict(zip(data['NAME'], data['MPG']))

# Read in the data
argparser = argparse.ArgumentParser()
argparser.add_argument('path', type=str, help='path to csv file')
argparser.add_argument('min', type=int, help='path to minutes csv file')
args = argparser.parse_args()
df = pd.read_csv(args.path)

# Drop datapoint where 0 points are scored
df = df[df['AvgPointsPerGame'] != 0]

df.drop(['Position', 'Name + ID', 'ID'], axis=1, inplace=True)

# Create binary columns for Roster Position
positions = df['Roster Position'].str.get_dummies(sep='/')

# Create binary columns for TeamAbbrev
teams = pd.get_dummies(df['TeamAbbrev'], prefix='Team').astype(int)

# Combine the original DataFrame with the new binary columns
df = pd.concat([df, positions, teams], axis=1)

df.drop(['Roster Position', 'TeamAbbrev'], axis=1, inplace=True)

indices = df['Name']
points = dict(zip(indices, df['AvgPointsPerGame']))
salaries = dict(zip(indices, df['Salary']))

position_dict = {}
for i in indices:
    row = df.loc[df['Name'] == i]
    position_dict[i] = {'PG' : row['PG'].values[0], 'SG' : row['SG'].values[0], 'SF' : row['SF'].values[0], 'PF' : row['PF'].values[0], 'C' : row['C'].values[0], 'G' : row['G'].values[0], 'F' : row['F'].values[0], 'UTIL' : row['UTIL'].values[0]}

pos = ['PG', 'SG', 'SF', 'PF', 'C','F','G','UTIL']

m = gp.Model("Fantasy_Optimizer")

y = m.addVars(indices, pos, vtype=gp.GRB.BINARY, name="y")

# Maximize pts + minute play time
if args.min == 1:
    m.setObjective(gp.quicksum((points[i]/minutes[i])*y[i,j] for i in indices for j in pos), gp.GRB.MAXIMIZE)
else:
    # since we are maximizing points the last argument here is GRB.MAXIMIZE
    m.setObjective(gp.quicksum(points[i]*y[i,j] for i in indices for j in pos), gp.GRB.MAXIMIZE)

# Salary cap is 50,000
m.addConstr(gp.quicksum(salaries[i]*y[i,j] for i in indices for j in pos) <= 50000, name='salary')

# Roster Constraint
for p in pos:
    m.addConstr(gp.quicksum(y[i,p] for i in indices) == 1)
    
# Player Constraint
for i in indices:
    m.addConstr(gp.quicksum(y[i,p] for p in pos) <= 1)

# Position Constraint
for i in indices:
    for p in pos:
        m.addConstr(y[i,p] <= position_dict[i][p])
        
m.optimize()

vars = m.getVars()

chosen = []
for i in vars:
    if i.x == 1:
        print(i.varName)
        chosen.append(i.varName.split('[')[1].split(',')[0])

pts = 0
salary = 0
for player in chosen:
    pts += points[player]
    salary += salaries[player]
    
print("Expected Points: ", pts)

print("Salary: ", salary)

with open('output.csv', 'a') as f:
    writer = csv.writer(f)
    writer.writerow([datetime.today().strftime('%Y-%m-%d'), pts, chosen, args.min])

