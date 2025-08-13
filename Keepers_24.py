from sleeper_wrapper import League
from sleeper_wrapper import Players
import csv
import math

def main():
    #Inputs
    current_year = 2025 #The current year is the one for which we are trying to find the keeper rounds for. The last played year is current_year-1.
    past_kr_csv = f'{current_year-1}_Keeper_Rounds.csv'
    manual_player_ids = {'Michael Carter': '7607', 
                         'C.J. Mosley': '1875',
                         'Mike Williams': '4068',
                         'Elijah Mitchell': '7561',
                         'Damar Hamlin': '7787',
                         'DJ Moore': '4983',
                         #'Josh Allen-QB': '4984',
                         #'Josh Allen-LB': '5840',
                         'Kenneth Walker': '8151',
                         'Lamar Jackson': '4881'}
    #name_disambiguation = {'4984': 'Josh Allen-QB', '5840': 'Josh Allen-LB'}
    name_disambiguation = {}
    #league_id = 1048428546022117376 #2024 League ID
    league_id = 1180581794923024384 #2025 League ID
    draft_id = league_id+1
    league = League(league_id) #League ID
    prev_league = League(int(league._league['previous_league_id']))


    players = Players()
    player_list = players.get_all_players()
    player_list = dict(sorted(player_list.items()))
    managers = league.get_users()
    #draft = league.get_draft(1180581794923024385) #draft for UPCOMING YEAR (not league_id+1)
    draft_picks = prev_league.get_draft_picks()
    if draft_picks == []:
        raise ValueError("draft_picks should not be empty")
    prev_rosters = prev_league.get_rosters()
    transactions = [prev_league.get_transactions(i) for i in range(20) if prev_league.get_transactions(i) != []] #Each 'i' is a week. range(20) since there are at most 20 weeks
    commish_trans = [None]*len(transactions) #Will record all commissioner transactions
    rosters = league.get_rosters()

    #This associates a full name with each player drafted
    for i, _ in enumerate(draft_picks): #Each 'i' is a pick
        player_id = draft_picks[i]['player_id']
        draft_picks[i]['player_name'] = player_list[player_id]['full_name']
    
    #Associates each manager with their roster
    for i, manager in enumerate(managers):
        for idx, rost in enumerate(rosters):
            if manager['user_id'] == rost['owner_id']: 
                manager['roster_num'] = idx
                rost['manager_num'] = i
                rost['manager_name'] = manager['display_name']


    #Changes the player_list to account for any name disambiguation
    for player_id in name_disambiguation:
        player_list[player_id]['full_name'] = name_disambiguation[player_id]
    
    #Finds all commissioner transactions for each week
    for week in range(len(transactions)):
        commish_trans[week] = [transactions[week][i] for i in range(len(transactions[week])) if transactions[week][i]['type'] == 'commissioner']
    
    #Will create a list of all keepers (assumes that all commissioner drops prior to week 1 are keepers)
    keeper_list = []
    for commish_drops in commish_trans[0]: #'0' for week 0
        keeper_list.append(list(commish_drops['drops'].keys())[0])
    
    #This turns that list of id's into a dictionary that includes names
    for i, _ in enumerate(keeper_list):
        player_id = keeper_list[i]
        keeper_list[i] = {player_id: player_list[player_id]['full_name']}
    if keeper_list == []:
        raise ValueError("Seriously? No one was kept from last season?")

    #This section creates the rosters for each manager immediately after the (current_year-1) draft
    draft_rosters = [None]*league._league['total_rosters']
    for i in range(len(draft_picks)):
        rost = draft_picks[i]['roster_id']
        try: 
            draft_rosters[rost-1].append({draft_picks[i]['player_id']: draft_picks[i]['player_name']})
        except AttributeError:
            draft_rosters[rost-1] = [{draft_picks[i]['player_id']: draft_picks[i]['player_name']}]

    #This section gets a list of all player names on each roster
    for i, _ in enumerate(rosters): #Each 'i' is a roster
        rosters[i]['player_names'] = []
        rosters[i]['player_last_names'] = []
        for player in rosters[i]['players']:
            rosters[i]['player_names'].append(player_list[player]['full_name'])
            rosters[i]['player_last_names'].append(player_list[player]['last_name'])
    
    #This section creates a list of all players that were dropped at some point
    dropped_players = []
    for week in transactions:
        for trans in week:
            status = trans['status']
            drops = list(trans['drops']) if trans['drops'] != None else None
            type_ = trans['type']
            if status == 'complete' and type_ != 'commissioner' and type_ != 'trade' and drops != None: #If this was a real drop
                for drop in drops:
                    dropped_players.append(drop)
    dropped_players = list(set(dropped_players)) #Eliminates duplicates
    if dropped_players == []:
        raise ValueError("Seriously? No one was dropped this season? That seems unlikely.")
    for i, _ in enumerate(dropped_players):
        drop_id = dropped_players[i]
        dropped_players[i] = {drop_id: player_list[drop_id]['full_name']}

    #This section associate each player name with an ID. (A reverse dictionary)
    name_id_dict = {} #Name : ID
    count_dict = {} #Name : Count (count is the number of times this name is in the database)
    try: 
        for pl in player_list.keys(): 
            name_id_dict[player_list[pl]['full_name']] = pl
            try: 
                count_dict[player_list[pl]['full_name']] += 1
            except KeyError:
                count_dict[player_list[pl]['full_name']] = 1
    except KeyError: pass #NFL Defenses won't have the 'full_name' key 
    for k,v in name_id_dict.items(): 
        name_id_dict[k] = (v,count_dict[k])
    for name in manual_player_ids:  
        name_id_dict[name] = (manual_player_ids[name], count_dict[name])


    #This section extracts the previous keeper rounds for players
    no_id_found = [] #This will contain the list of players for which an ID could not be identified
    duplicate_names = []
    with open(past_kr_csv, 'r') as csvfile:
        file_reader = csv.reader(csvfile)
        header = next(file_reader)  # Read the header row
        # Clean BOM from the first column if present
        if "ï»¿" in header[0]: 
            header[0] = header[0].replace('ï»¿', '')
        
        # Find the index of the "{current_year-1} keeper round" column
        try:
            keeper_round_index = header.index(f"{current_year-1} keeper round")
        except ValueError:
            raise ValueError(f'"{current_year-1} keeper round" column not found in the CSV file')
        
        # Find the index of the Sleeper ID column
        try:
            Sleeper_ID_index = header.index(f"Sleeper ID")
        except ValueError:
            raise ValueError(f'"Sleeper ID" column not found in the CSV file')

        # Process the remaining rows
        for _, row in enumerate(file_reader, start=1):
            if row[Sleeper_ID_index] != '': #only select rows where a Sleeper ID is present
                player_id = row[Sleeper_ID_index]
                keeper_round = row[keeper_round_index]
                # try: 
                #     if name_id_dict[player_name][1] > 1:  # If there are multiple people with this name
                #         duplicate_names.append(player_name)
                #         # continue
                #     player_id = name_id_dict[player_name][0]
                player_list[player_id]['prev_keeper_round'] = keeper_round
                # except KeyError: 
                #     no_id_found.append(player_name)

    
    if no_id_found != []: raise ValueError("We should be able to find the id's for all players")
    if len(set(duplicate_names)-set(manual_player_ids)) > 1: raise ValueError("There are duplicate names that haven't been accounted for")
    

    #This section establishes the keeper round table
    kr_table = {}
    for i in range(22):
        rd = i+1
        kr_table[rd] = math.ceil((rd-0.5)*.75)
    kr_table[2] = 1 #Forces previous rd 2 keepers to become rd 1 keepers

    #This section creates attributes for each player on a roster
    krstr = f"{current_year}_keeper_round"
    for rost in rosters:
        rost['player_attr'] = {}
        for player in rost['players']:
            try: draft_pick = [draft_picks[i]['player_id'] for i in range(len(draft_picks))].index(player)
            except ValueError: draft_pick = None
            starting_roster = draft_picks[draft_pick]['picked_by'] if draft_pick != None else None
            ending_roster = rost['owner_id']
            rost['player_attr'][player] = {}
            rost['player_attr'][player]['full_name'] = player_list[player]['full_name']
            rost['player_attr'][player]['was_keeper'] = True if {player: player_list[player]['full_name']} in keeper_list else False
            rost['player_attr'][player]['was_drafted'] = True if player in [draft_picks[i]['player_id'] for i in range(len(draft_picks))] else False
            rost['player_attr'][player]['was_dropped'] = True if {player: player_list[player]['full_name']} in dropped_players else False
            rost['player_attr'][player]['on_same_roster'] = True if starting_roster == ending_roster else False
            rost['player_attr'][player]['draft_round'] = draft_picks[draft_pick]['round'] if draft_pick != None else None
            rost['player_attr'][player]['was_undrafted'] = True if rost['player_attr'][player]['was_keeper'] == False and rost['player_attr'][player]['was_drafted'] == False else False
            try: 
                rost['player_attr'][player]['prev_keeper_round'] = int(player_list[player]['prev_keeper_round'])
            except KeyError:
                rost['player_attr'][player]['prev_keeper_round'] = None

            #This is the logic section that determines what category each player falls in
            if    (rost['player_attr'][player]['was_dropped'] == True and rost['player_attr'][player]['on_same_roster'] == False)\
                or rost['player_attr'][player]['was_undrafted'] == True:
                rost['player_attr'][player][krstr] = f'{current_year} ADP Round + 4'
                rost['player_attr'][player]['designation'] = 'undrafted or dropped'
            elif rost['player_attr'][player]['was_keeper'] == True: #and rost['player_attr'][player]['was_dropped'] == False: 
                prev_kr = rost['player_attr'][player]['prev_keeper_round']
                rost['player_attr'][player][krstr] = kr_table[prev_kr]
                rost['player_attr'][player]['designation'] = 'keeper'
            elif rost['player_attr'][player]['was_drafted'] == True: #and rost['player_attr'][player]['was_dropped'] == False: 
                prev_dr = rost['player_attr'][player]['draft_round']
                rost['player_attr'][player][krstr] = kr_table[prev_dr]
                rost['player_attr'][player]['designation'] = 'drafted'
            else: raise ValueError("Player should have fallen into one of these categories")
    

    #This section writes the results to an excel file
    col_names = ['Player Name', 'Sleeper ID', 'was keeper', \
                 f'{current_year-1} keeper round',\
                 'was drafted', 'draft round', 'was dropped', \
                 'on same roster',  'was undrafted', 'designation', \
                 f'{current_year} keeper round']
    with open(f'{current_year}_Keeper_Rounds.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=col_names)
        writer.writeheader()
        for rost in rosters:
            writer.writerow({"Player Name": ''}) #empty line
            writer.writerow({'Player Name': rost['manager_name']}) #line for manager name
            for pid in rost['player_attr']: 
                dict_of_vals = {'Player Name': rost['player_attr'][pid]['full_name'],
                                'Sleeper ID': pid,
                                'was keeper': rost['player_attr'][pid]['was_keeper'],
                                f'{current_year-1} keeper round': rost['player_attr'][pid]['prev_keeper_round'],
                                'was drafted': rost['player_attr'][pid]['was_drafted'],
                                'draft round': rost['player_attr'][pid]['draft_round'],
                                'was dropped': rost['player_attr'][pid]['was_dropped'],
                                'on same roster': rost['player_attr'][pid]['on_same_roster'],
                                'was undrafted': rost['player_attr'][pid]['was_undrafted'],
                                'designation': rost['player_attr'][pid]['designation'],
                                f'{current_year} keeper round': rost['player_attr'][pid][krstr],
                                }
                writer.writerow(dict_of_vals)
        

    print("finished")





if __name__ == "__main__": 
    main()