from sleeper_wrapper import League
from sleeper_wrapper import Players
import csv

#This is run on 'base' environment (not any of the arcgis clones)

def get_undrafted_players(draft):
    drafted_list = []
    for pick in draft:
        drafted_list.append(pick['metadata']['first_name'] + ' ' + pick['metadata']['last_name'])



def main():
    league = League(918033022480596992, 918033022480596993) #League ID, #Draft ID
    players = Players()
    player_list = players.get_all_players()

    transactions_in_week_ = [None] * 18
    successful_transactions_in_week_ = [[None]] * 18
    drops = []
    drop_names = []
    sorted_drop_names2 = []
    same_roster_players = []
    daab_names = []
    draft = league.get_draft_picks()

    for i in range(18):
        transactions_in_week_[i] = league.get_transactions(week=i+1)

    #Gets all the drops and appends them to a list
    for i in range(18):
        for trans in transactions_in_week_[i]:
            if trans['status'] == 'complete' and trans['type'] != 'commissioner' and trans['type'] != 'trade':
                successful_transactions_in_week_[i].append(trans)
                if trans['drops'] != None:
                    drops.append(list(trans['drops'].keys())) 

    drops = [item for sublist in drops for item in sublist]
    drops = list(set(drops)) #Removes duplicates

    rosters = league.get_rosters()

    for pick in draft:
        player = pick['player_id']
        starting_manager = pick['roster_id']
        if player in rosters[starting_manager-1]['players']: #If the player is on the roster of starting_manager at the end of the year
            same_roster_players.append(player)

    dropped_and_added_back = list(set(drops) & set(same_roster_players))
    for player in dropped_and_added_back:
        daab_names.append(player_list[player]['full_name']) #daab = dropped and added back
    drops = list(set(drops) - set(same_roster_players))

    for drop in drops:
        drop_names.append(player_list[drop]['full_name'])
        
    sorted_drop_names = sorted(drop_names)
    for name in sorted_drop_names:
        sorted_drop_names2.append([name])

    with open('dropped_players.csv', 'w') as f:
        write = csv.writer(f)
        write.writerows(sorted_drop_names2)


    print("finished")

if __name__ == "__main__": 
    main()