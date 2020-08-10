#!/usr/bin/env python
# coding: utf-8

# In[1]:

import matplotlib.pyplot as plt

from agent import RL_Agents, RBC_Agent
import numpy as np
from csv import DictWriter
import json
from pathlib import Path
import time
import os

from citylearn import  CityLearn

# Extra packages for postprocessing
import matplotlib.dates as dates
import pandas as pd

from algo_utils import graph_total, graph_building, tabulate_table
    
# In[2]:

# Load environment
climate_zone = 4
data_path = Path("data/Climate_Zone_"+str(climate_zone))
building_attributes = data_path / 'building_attributes.json'
weather_file = data_path / 'weather_data.csv'
solar_profile = data_path / 'solar_generation_1kW.csv'
building_state_actions = 'buildings_state_action_space.json'
building_ids = ["Building_1","Building_2","Building_3","Building_4","Building_5","Building_6","Building_7","Building_8","Building_9"]
objective_function = ['ramping','1-load_factor','average_daily_peak','peak_demand','net_electricity_consumption']
env = CityLearn(data_path, building_attributes, weather_file, solar_profile, building_ids, buildings_states_actions = building_state_actions, cost_function = objective_function, central_agent = True)

# Contain the lower and upper bounds of the states and actions, to be provided to the agent to normalize the variables between 0 and 1.
# Can be obtained using observations_spaces[i].low or .high
observations_spaces, actions_spaces = env.get_state_action_spaces()

# Provides information on Building type, Climate Zone, Annual DHW demand, Annual Cooling Demand, Annual Electricity Demand, Solar Capacity, and correllations among buildings
building_info = env.get_building_information()

# Store the weights and scores in a new directory
parent_dir = "alg/sac_{}/".format(time.strftime("%Y%m%d-%H%M%S")) # apprends the timedate
os.makedirs(parent_dir, exist_ok=True)

# Create the final dir
final_dir = parent_dir+"final/"
os.makedirs(final_dir, exist_ok=True)

# In[ ]:
# Simulate a year of RBC actions
RBC_env = CityLearn(data_path, building_attributes, weather_file, solar_profile, building_ids, buildings_states_actions = building_state_actions, cost_function = objective_function, central_agent = False, verbose = 0)
observations_spacesRBC, actions_spacesRBC = RBC_env.get_state_action_spaces()
agent = RBC_Agent(actions_spacesRBC)
state = RBC_env.reset()
state_list = []
action_list = []
doneRBC = False
while not doneRBC:
    action = agent.select_action([list(RBC_env.buildings.values())[0].sim_results['hour'][RBC_env.time_step]])
    action_list.append(action)
    state_list.append(state)
    next_stateRBC, rewardsRBC, doneRBC, _ = RBC_env.step(action)
    state = next_stateRBC
RBC_action_base = np.array(action_list)
RBC_state_base = np.array(state_list)
RBC_24h_peak = [day.max() for day in np.append(RBC_env.net_electric_consumption,0).reshape(-1, 24)]

# Initialise agent
#agents = SAC(env, env.observation_space.shape[0], env.action_space)
agents = RL_Agents(building_info, observations_spaces, actions_spaces, env)

# Play a saved ckpt of actor network in the environment

# Select many episodes for training. In the final run we will set this value to 1 (the buildings run for one year)
episodes = 1

k, c = 0, 0
cost, cum_reward = {}, {}

# Measure the time taken for training
start_timer = time.time()

for e in range(episodes):
    cum_reward[e] = 0
    rewards = []
    state = env.reset()
    done = False
            
    while not done:
        
        # Add batch dimension to single state input, and remove batch dimension from single action output
        action = agents.select_action(state)
        next_state, reward, done, _ = env.step(action)
        agents.add_to_buffer(state, action, reward, next_state, done)
        state = next_state
        cum_reward[e] += reward
        rewards.append(reward)
        k+=1
            
    cost[e] = env.cost()
            
    if c%1==0:
        print(cost[e])
    c+=1
                    
env.close() 

timer = time.time() - start_timer

# In[ ]:
## POSTPROCESSING

# Plot District level power consumption
# for i in range(9):
#     graph_total(env=env, RBC_env = RBC_env, agent=agents, parent_dir=final_dir, start_date = f'2017-0{i+1}-01', end_date = f'2017-0{i+1}-8')
# for i in range(10,13):
#     graph_total(env=env, RBC_env = RBC_env, agent=agents, parent_dir=final_dir, start_date = f'2017-{i}-01', end_date = f'2017-{i}-10')
graph_total(env=env, RBC_env = RBC_env, agent=agents, parent_dir=final_dir, start_date = f'2017-12-01', end_date = f'2017-12-10')

# Plotting winter operation
interval = range(5000,5200)
plt.figure(figsize=(16,5))
plt.plot(env.net_electric_consumption_no_pv_no_storage[interval])
plt.plot(env.net_electric_consumption_no_storage[interval])
plt.plot(env.net_electric_consumption[interval], '--')
plt.xlabel('time (hours)')
plt.ylabel('kW')
plt.legend(['Electricity demand without storage or generation (kW)', 'Electricity demand with PV generation and without storage(kW)', 'Electricity demand with PV generation and using SAC for storage(kW)'])
plt.savefig("test.jpg", bbox_inches='tight', dpi = 300)

tabulate_table(env=env, timer=timer, algo="SAC", agent = agents, climate_zone=climate_zone, building_ids=building_ids, 
               building_attributes=building_attributes, parent_dir=agents.load_path, num_episodes=episodes, episode_scores=rewards)

