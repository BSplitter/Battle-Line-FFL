from sleeper_wrapper import League
from sleeper_wrapper import Players
import copy
import csv
from more_itertools import sort_together

def check_pick_integrity(picks, managers, num_rounds):
    """Checks whether the picks assigned to each manager make sense"""
    all_picks = []
    for idx, manager in enumerate(picks):
        if len(picks[manager]) != num_rounds: raise RuntimeError("The number of picks for each manager must be {}. Check {}'s picks.".format(num_rounds, manager))
        for pick in picks[manager]:
            all_picks.append(pick)
    sorted_picks = sorted(all_picks)
    for idx, pick in enumerate(sorted_picks):
        if pick != idx+1: raise RuntimeError("Pick {} is wrong".format(pick))
    for idx, manager in enumerate(picks):
        if manager != managers[idx]: raise RuntimeError("manager name {} is not the same as listed in picks".format(manager))

def original_draft_picks(draft_pos, managers, num_rounds):
    """Determines what the original draft picks for each player should be"""
    orig_picks = {}
    for idx, manager in enumerate(draft_pos):
        if manager != managers[idx]: raise RuntimeError("manager name {} is not the same as listed in draft_pos".format(manager))
    for manager in draft_pos:
        orig_picks[manager] = [draft_pos[manager]]
        for round in range(2,num_rounds+1):
            if round <= 6: 
                orig_picks[manager].append(10*(round-1) + draft_pos[manager])
            elif round > 6 and round % 2 == 0: #Even round
                orig_picks[manager].append(10*(round-1) + draft_pos[manager])
            elif round > 6 and round % 2 == 1: #Odd round
                orig_picks[manager].append(10*(round) + 1 - draft_pos[manager])
    return orig_picks



def check_keeper_integrity(keepers, managers, rosters, player_list):
    """Checks whether the keepers chosen are legal"""
    for idx, manager in enumerate(keepers):
        if manager != managers[idx]: raise RuntimeError("manager name {} is not the same as listed in keepers".format(manager))
    for manager in keepers:
        if len(keepers[manager]) > 6: raise ValueError("Manager {} has too many keepers".format(manager))
        if len(keepers[manager]) != len(set(keepers[manager])): raise ValueError("Manager {} has a duplicate keeper".format(manager))
    
    
    for manager in keepers:
        def_players = 0 #Number of defensive players selected as keepers
        early_keepers = 0 #Number of players that have keeper round < 10
        ek_ids = [] #Early Keeper IDs
        dk_ids = [] #Defensive Keeper IDs
        roster_ids = list(rosters[manager].keys())
        for k_id in keepers[manager]: 
            if k_id not in roster_ids: raise ValueError("Keeper {} is not on {}'s roster".format(k_id, manager))
            if player_list[k_id]['position'] in ['CB', 'DE', 'ILB', 'DL', 'DB', 'FS', 'OLB', 'S', 'DT', 'NT', 'LB', 'SS']:
                def_players += 1
                dk_ids.append(k_id)
            if int(rosters[manager][k_id][1]) < 10:
                early_keepers += 1
                ek_ids.append(k_id)
        if len(ek_ids) == 6: raise ValueError("Manager {} kept too many early-round keepers".format(manager))
        elif len(ek_ids) == 5: 
            if len(set(ek_ids)-set(dk_ids)) == 5: raise ValueError("Manager {} kept too many early-round keepers".format(manager))
        if len(keepers[manager]) == 6 and len(dk_ids) == 0: raise ValueError("Manager {} kept 6 offensive players. One must be on defense.".format(manager))

def assign_keepers(keepers, picks, orig_picks, rosters):
    """This assigns each keeper to the appropriate pick"""
    unassigned_picks = copy.deepcopy(picks)
    keeper_picks = copy.deepcopy(keepers)
    for manager in keepers:
        for idx, k_id in enumerate(keepers[manager]):
            kr = int(rosters[manager][k_id][1]) #Keeper round
            if orig_picks[manager][kr-1] in unassigned_picks[manager]: #If the manager still has the original pick from that round
                keeper_picks[manager][idx] = (k_id, orig_picks[manager][kr-1])
                unassigned_picks[manager].remove(orig_picks[manager][kr-1])
            elif max(unassigned_picks[manager]) >= 10*(kr-1)+1: #If a picks exists in the keeper round or later
                pick_to_assign = min(p for p in unassigned_picks[manager] if p >= 10*(kr-1)+1)
                keeper_picks[manager][idx] = (k_id, pick_to_assign)
                unassigned_picks[manager].remove(pick_to_assign)
            else: #If there are no unassigned picks in the keeper round or later
                pick_to_assign = max(unassigned_picks[manager])
                keeper_picks[manager][idx] = (k_id, pick_to_assign)
                unassigned_picks[manager].remove(pick_to_assign)
    return keeper_picks



def main():
    #Inputs
    num_rounds = 22
    managers = ['T-Money', 'tjdodson07', 'sbaker057', 'zwade', 'stoneshewmake6',\
                 'BSplitt', 'Thehunter66', 'jshumaker19', 'lunte', 'SlyTy']
    picks = {
        'T-Money': [5, 15, 22, 24, 25, 27, 32, 38, 45, 106, 107, 115, 124, 126, 135, 146, 155, 166, 172, 175, 186, 194],
        'tjdodson07': [3, 11, 13, 26, 43, 68, 71, 73, 88, 93, 108, 113, 128, 133, 148, 153, 168, 173, 188, 193, 208, 220],
        'sbaker057': [10, 18, 20, 40, 60, 70, 80, 81, 100, 101, 120, 121, 140, 141, 160, 161, 171, 177, 180, 181, 200, 201],
        'zwade': [9, 14, 19, 39, 57, 59, 62, 64, 79, 82, 102, 119, 122, 142, 159, 162, 179, 182, 199, 202, 207, 219],
        'stoneshewmake6': [2, 8, 12, 17, 69, 72, 89, 92, 95, 109, 112, 129, 132, 144, 149, 169, 189, 192, 195, 206, 209, 212],
        'BSplitt': [30, 36, 46, 50, 53, 58, 65, 76, 85, 96, 105, 116, 125, 136, 145, 156, 165, 176, 185, 196, 205, 216],
        'Thehunter66': [34, 37, 44, 47, 48, 54, 55, 66, 67, 74, 77, 86, 87, 94, 114, 127, 134, 147, 154, 167, 174, 187],
        'jshumaker19': [1, 4, 16, 28, 63, 75, 78, 83, 98, 103, 118, 123, 138, 143, 158, 163, 178, 183, 198, 203, 211, 218], 
        'lunte': [6, 7, 29, 42, 49, 52, 84, 97, 99, 104, 117, 137, 139, 152, 157, 164, 184, 197, 204, 213, 214, 217],
        'SlyTy': [21, 23, 31, 33, 35, 41, 51, 56, 61, 90, 91, 110, 111, 130, 131, 150, 151, 170, 190, 191, 210, 215]
    }
    check_pick_integrity(picks, managers, num_rounds) #Ensures that data was entered correctly
    draft_pos = {
        'T-Money': 5,
        'tjdodson07': 3,
        'sbaker057': 10,
        'zwade': 9,
        'stoneshewmake6': 2,
        'BSplitt': 6,
        'Thehunter66': 4,
        'jshumaker19': 8,
        'lunte': 7,
        'SlyTy': 1
    }
    name_disambiguation = {'4984': 'Josh Allen-QB', '5840': 'Josh Allen-LB'}
    current_year = 2024

    #Other initialization items
    kr_doc = '{} Keeper Rounds.csv'.format(current_year)
    players = Players()
    player_list = players.get_all_players()
    player_list = dict(sorted(player_list.items()))
    #Changes the player_list to account for any name disambiguation
    for player_id in name_disambiguation:
        player_list[player_id]['full_name'] = name_disambiguation[player_id]
    orig_picks = original_draft_picks(draft_pos, managers, num_rounds)

    #Establishes the rosters
    rosters = {}
    with open(kr_doc, 'r') as csvfile:
        file_reader = csv.reader(csvfile)
        for row_num, row in enumerate(file_reader):
            if row_num == 0 or row_num == 1: continue #Ignores header
            elif row[0] != '' and row[1] == '': #This is a manager line
                rosters[row[0]] = {}
                curr_manager = row[0]
                continue
            elif row[0] == '' and row[1] == '': #A blank line
                continue
            else: #A player line
                rosters[curr_manager][row[1]] = [row[0], row[10]]
    for manager in rosters: 
        for p_id in rosters[manager]:
            rosters[manager][p_id][1] = int(rosters[manager][p_id][1]) if rosters[manager][p_id][1] != '{} ADP Round + 4'.format(current_year) else 1000
        rosters[manager] = dict(sorted(rosters[manager].items(), key=lambda x:x[1][1], reverse=False)) #Sorts by keeper round
    
    keepers = {#might want to find a way to automate this
        'T-Money': ['421', '6794', '6813', '6904', '7672', '8144'],
        'tjdodson07': ['10222', '6770', '6809', '7543', '7564', '9493'],
        'sbaker057': ['4881', '6803', '6888', '8183', '8205', '9508'],
        'zwade': ['5726', '6786', '7594', '8155', '9226', '9502'],
        'stoneshewmake6': ['10229', '10891', '4981', '8150', '1166', '8130'],
        'BSplitt': ['2216', '3321', '5332', '6804', '9486', '5850'],
        'Thehunter66': ['1466', '2133', '4035', '4866', '5248', '6214'],
        'jshumaker19': ['10859', '4046', '5346', '6797', '7547', '8151'], 
        'lunte': ['9758', '4034', '4984', '8138', '8146', '5944'],
        'SlyTy': ['2617', '5849', '7569', '9221', '9509', '5859']
    }
    kp_idx = copy.deepcopy(keepers)
    for manager in keepers:
        for idx, pid in enumerate(keepers[manager]): 
            kp_idx[manager][idx] = list(rosters[manager].keys()).index(pid)
        if keepers[manager] != []:
            keepers[manager] = list(sort_together([kp_idx[manager], keepers[manager]])[1])

    check_keeper_integrity(keepers, managers, rosters, player_list)

    keeper_picks = assign_keepers(keepers, picks, orig_picks, rosters)

    col_names = ['Keeper', 'Sleeper ID', 'Designated Keeper Round', 'Keeper Pick']
    with open('{} Keeper Pick Assignments.csv'.format(current_year), 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=col_names)
        writer.writeheader()
        for manager in keeper_picks:
            writer.writerow({'Keeper': ''}) #empty line
            writer.writerow({'Keeper': manager}) #line for manager name
            for tup in keeper_picks[manager]:
                pid = tup[0]
                keeper_pick = tup[1]
                dict_of_vals = {'Keeper': rosters[manager][pid][0],
                                'Sleeper ID': pid,
                                'Designated Keeper Round': rosters[manager][pid][1],
                                'Keeper Pick': keeper_pick
                               }
                writer.writerow(dict_of_vals)




    print('finished')

if __name__ == "__main__": 
    main()