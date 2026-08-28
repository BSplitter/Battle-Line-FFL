from sleeper_wrapper import League
from sleeper_wrapper import Players
import copy
import csv
from more_itertools import sort_together
import pandas as pd
import requests
import math

def check_pick_integrity(picks, managers, num_rounds):
    """Checks whether the picks assigned to each manager make sense"""
    all_picks = []
    for idx, manager in enumerate(picks):
        if len(picks[manager]) != num_rounds: raise RuntimeError(f"The number of picks for each manager must be {num_rounds}. Check {manager}'s picks.")
        for pick in picks[manager]:
            all_picks.append(pick)
    sorted_picks = sorted(all_picks)
    for idx, pick in enumerate(sorted_picks):
        if pick != idx+1: raise RuntimeError(f"Pick {pick} is wrong")
    for idx, manager in enumerate(picks):
        if manager != managers[idx]: raise RuntimeError(f"manager name {manager} is not the same as listed in picks")

def original_draft_picks(draft_pos, managers, num_rounds):
    """Determines what the original draft picks for each player should be"""
    orig_picks = {}
    for idx, manager in enumerate(draft_pos):
        if manager != managers[idx]: raise RuntimeError(f"manager name {manager} is not the same as listed in draft_pos")
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

def sleeper_current_picks(league_id, season=None):
    base = "https://api.sleeper.app/v1"

    drafts = requests.get(f"{base}/league/{league_id}/drafts").json() or []
    if not drafts: return {}

    if season is None:
        dmeta = max(drafts, key=lambda d: int(d["season"]))
    else:
        season = str(season)
        dmeta = next((d for d in drafts if str(d["season"]) == season),
                     max(drafts, key=lambda d: int(d["season"])))
    draft_id   = dmeta["draft_id"]
    season_str = str(dmeta["season"])

    draft   = requests.get(f"{base}/draft/{draft_id}").json()
    rosters = requests.get(f"{base}/league/{league_id}/rosters").json()
    trades  = requests.get(f"{base}/league/{league_id}/traded_picks").json() or []

    # slot (draft position) -> origin roster_id
    slot_to_roster = {int(k): int(v) for k, v in draft.get("slot_to_roster_id", {}).items()}
    # roster_id -> user_id (manager)
    roster_to_user = {int(r["roster_id"]): str(r["owner_id"]) for r in rosters}

    rounds = int(draft.get("settings", {}).get("rounds", 22))
    L = len(slot_to_roster)
    draft_type = draft.get("type", "linear")  # 'linear' or 'snake'

    # Final owner per (round, origin_roster_id) as a roster_id
    final_owner_rid = {}
    for t in trades:
        if str(t.get("season")) == season_str:
            final_owner_rid[(int(t["round"]), int(t["roster_id"]))] = int(t["owner_id"])

    def overall(slot, rnd):
        if draft_type == "snake" and rnd % 2 == 0:
            return L*rnd + 1 - slot
        return L*(rnd - 1) + slot  # linear (and odd snake rounds)

    # Build: user_id -> list of overall picks
    picks_by_user = {}
    for slot, origin_rid in slot_to_roster.items():
        for rnd in range(1, rounds + 1):
            current_rid = final_owner_rid.get((rnd, origin_rid), origin_rid)
            user = roster_to_user.get(current_rid) or f"roster:{current_rid}"
            picks_by_user.setdefault(user, []).append(overall(slot, rnd))

    for u in picks_by_user:
        picks_by_user[u].sort()
    return picks_by_user

# def check_keeper_integrity(keepers, managers, rosters, player_list):
#     """Checks whether the keepers chosen are legal"""
#     for idx, manager in enumerate(keepers):
#         if manager != managers[idx]: raise RuntimeError("manager name {} is not the same as listed in keepers".format(manager))
#     for manager in keepers:
#         if len(keepers[manager]) > 6: raise ValueError("Manager {} has too many keepers".format(manager))
#         if len(keepers[manager]) != len(set(keepers[manager])): raise ValueError("Manager {} has a duplicate keeper".format(manager))
    
    
#     for manager in keepers:
#         def_players = 0 #Number of defensive players selected as keepers
#         early_keepers = 0 #Number of players that have keeper round < 10
#         ek_ids = [] #Early Keeper IDs
#         dk_ids = [] #Defensive Keeper IDs
#         roster_ids = list(rosters[manager].keys())
#         for k_id in keepers[manager]: 
#             if k_id not in roster_ids: raise ValueError("Keeper {} is not on {}'s roster".format(k_id, manager))
#             if player_list[k_id]['position'] in ['CB', 'DE', 'ILB', 'DL', 'DB', 'FS', 'OLB', 'S', 'DT', 'NT', 'LB', 'SS']:
#                 def_players += 1
#                 dk_ids.append(k_id)
#             if int(rosters[manager][k_id][1]) < 10:
#                 early_keepers += 1
#                 ek_ids.append(k_id)
#         if len(ek_ids) == 6: raise ValueError("Manager {} kept too many early-round keepers".format(manager))
#         elif len(ek_ids) == 5: 
#             if len(set(ek_ids)-set(dk_ids)) == 5: raise ValueError("Manager {} kept too many early-round keepers".format(manager))
#         if len(keepers[manager]) == 6 and len(dk_ids) == 0: raise ValueError("Manager {} kept 6 offensive players. One must be on defense.".format(manager))

def check_keeper_integrity_df(managers_df, rosters, player_list, early_round_threshold=10, max_keepers=6):
    """
    Validate keeper selections per league rules using managers_df rows.
      - managers_df must have: User_id, display_name, Keepers (list[str]), Keeper_rounds_2025 (list[Int/None])
      - rosters: Sleeper /league/{league_id}/rosters result (list[dict])
      - player_list: Sleeper players dict keyed by Sleeper ID (as strings) -> {'position': ...}
    Raises ValueError/RuntimeError on violations; returns True if all good.
    """

    # Build membership map: owner_id -> set of player IDs actually on that roster
    owner_to_roster = {}
    for r in rosters:
        owner = str(r.get("owner_id"))
        # union of players + reserve + keepers (some may be None)
        pool = set(map(str, (r.get("players") or [])))
        pool |= set(map(str, (r.get("reserve") or [])))
        pool |= set(map(str, (r.get("keepers") or [])))
        owner_to_roster[owner] = pool

    # IDP defensive positions to count as "defensive keepers"
    DEF_POS = {"CB","DE","ILB","DL","DB","FS","OLB","S","DT","NT","LB","SS"}

    # Walk each manager’s row
    for row in managers_df.itertuples(index=False):
        user_id   = str(row.User_id)
        mname     = str(row.display_name)
        keepers   = row.Keepers if isinstance(row.Keepers, list) else []
        k_rounds  = row.Keeper_rounds_2025 if isinstance(row.Keeper_rounds_2025, list) else []

        # Basic checks
        if len(keepers) > max_keepers:
            raise ValueError(f"{mname}: has {len(keepers)} keepers (max {max_keepers}).")

        if len(keepers) != len(set(map(str, keepers))):
            raise ValueError(f"{mname}: duplicate keeper detected.")

        # Roster membership check
        roster_ids = owner_to_roster.get(user_id, set())
        for pid in map(str, keepers):
            if pid not in roster_ids:
                raise ValueError(f"{mname}: keeper {pid} is not on their roster.")

        # Build aligned pairs (pid, round); tolerate missing rounds
        pairs = list(zip(map(str, keepers), k_rounds)) if k_rounds else [(str(pid), None) for pid in keepers]

        # Classify early keepers and defensive keepers
        early_ids = []
        defensive_ids = []
        for pid, rnd in pairs:
            # Defensive?
            pos = (player_list.get(pid, {}) or {}).get("position")
            if pos in DEF_POS:
                defensive_ids.append(pid)
            # Early?
            try:
                if rnd is not None and int(rnd) < early_round_threshold:
                    early_ids.append(pid)
            except Exception:
                # If round is non-numeric/missing, ignore for "early" purposes
                pass

        # League-specific rules
        if len(early_ids) == 6:
            raise ValueError(f"{mname}: kept too many early-round keepers (6).")

        if len(early_ids) == 5:
            # If all 5 early keepers are offensive (none defensive), it's illegal
            if len(set(early_ids) - set(defensive_ids)) == 5:
                raise ValueError(f"{mname}: 5 early-round keepers are all offensive (needs at least one defensive).")

        if len(keepers) == 6 and len(defensive_ids) == 0:
            raise ValueError(f"{mname}: kept 6 offensive players. One must be on defense.")

    return True

# def assign_keepers(keepers, picks, orig_picks, rosters):
#     """This assigns each keeper to the appropriate pick"""
#     unassigned_picks = copy.deepcopy(picks)
#     keeper_picks = copy.deepcopy(keepers)
#     for manager in keepers:
#         for idx, k_id in enumerate(keepers[manager]):
#             kr = int(rosters[manager][k_id][1]) #Keeper round
#             if orig_picks[manager][kr-1] in unassigned_picks[manager]: #If the manager still has the original pick from that round
#                 keeper_picks[manager][idx] = (k_id, orig_picks[manager][kr-1])
#                 unassigned_picks[manager].remove(orig_picks[manager][kr-1])
#             elif max(unassigned_picks[manager]) >= 10*(kr-1)+1: #If a picks exists in the keeper round or later
#                 pick_to_assign = min(p for p in unassigned_picks[manager] if p >= 10*(kr-1)+1)
#                 keeper_picks[manager][idx] = (k_id, pick_to_assign)
#                 unassigned_picks[manager].remove(pick_to_assign)
#             else: #If there are no unassigned picks in the keeper round or later
#                 pick_to_assign = max(unassigned_picks[manager])
#                 keeper_picks[manager][idx] = (k_id, pick_to_assign)
#                 unassigned_picks[manager].remove(pick_to_assign)
#     return keeper_picks

def assign_keepers_from_df(managers_df, rounds_col="Keeper_rounds_2025"):
    """
    Assign keepers to draft picks, processing earliest keeper rounds first.
    Requires columns:
      - display_name
      - Draft_order
      - Current_picks      (list[int])
      - Original_picks     (list[int], index r-1 -> original overall pick for round r)
      - Keepers            (list[str] Sleeper IDs)
      - rounds_col         (list[int] aligned to Keepers), default 'Keeper_rounds_2025'

    Returns:
      dict[display_name] -> list[(keeper_id, assigned_overall_pick)]
      (list is aligned to the original Keepers order for that manager)
    """

    # Infer league size (number of draft slots)
    L = int(managers_df["Draft_order"].dropna().nunique())
    if L <= 0:
        raise ValueError("Draft_order missing; cannot infer league size.")

    assignments = {}

    for row in managers_df.itertuples(index=False):
        name    = row.display_name
        picks   = sorted(row.Current_picks if isinstance(row.Current_picks, list) else [])
        orig    = list(row.Original_picks if isinstance(row.Original_picks, list) else [])
        keepers = list(row.Keepers if isinstance(row.Keepers, list) else [])
        rounds  = getattr(row, rounds_col, None)
        rounds  = list(rounds) if isinstance(rounds, list) else [None] * len(keepers)

        if len(keepers) != len(rounds):
            raise ValueError(f"{name}: Keepers and {rounds_col} lengths differ.")

        # Validate rounds and prep sortable tuples: (pid, round, orig_pick_for_round)
        pairs = []
        for pid, kr in zip(keepers, rounds):
            if kr is None or (isinstance(kr, float) and math.isnan(kr)):
                raise ValueError(f"{name}: Missing keeper round for keeper {pid}.")
            kr = int(kr)
            orig_pick = orig[kr - 1] if 1 <= kr <= len(orig) else None
            pairs.append((str(pid), kr, orig_pick))

        # Assign in order of earliest keeper round first; tiebreaker = smaller original pick
        pairs.sort(key=lambda t: (t[1], t[2] if t[2] is not None else float("inf")))

        unassigned = picks[:]
        if len(unassigned) < len(pairs):
            raise ValueError(f"{name}: fewer available picks ({len(unassigned)}) than keepers ({len(pairs)}).")

        pick_by_pid = {}

        for pid, kr, orig_pick in pairs:
            round_start = L * (kr - 1) + 1

            if (orig_pick is not None) and (orig_pick in unassigned):
                chosen = orig_pick
            else:
                candidates = [p for p in unassigned if p >= round_start]  # earliest in round kr or later
                chosen = min(candidates) if candidates else max(unassigned)

            pick_by_pid[pid] = int(chosen)
            unassigned.remove(chosen)

        # Return list aligned to the ORIGINAL keepers order for this manager
        out = [(str(pid), pick_by_pid[str(pid)]) for pid in keepers]
        assignments[name] = out

    return assignments


def export_keeper_sheet(
    managers_df,
    keeper_rounds_csv="2025_Keeper_rounds.csv",
    out_xlsx="Keeper_Assignments_2025.xlsx",
    player_list=None,
    league_size=None,   # optional; if None we'll infer from Draft_order
):
    # --- helper: overall -> "round.pick" (no zero-padding) ---
    def to_round_pick(p, L):
        if p is None or pd.isna(p): 
            return None
        p = int(p)
        r = (p - 1) // L + 1
        k = (p - 1) % L + 1
        return f"{r}.{k}"

    # infer league size if not provided
    if league_size is None:
        L = int(managers_df["Draft_order"].dropna().nunique())
        if L <= 0:
            raise ValueError("Cannot infer league size from Draft_order; pass league_size=")
    else:
        L = int(league_size)

    # --- name / round lookup from CSV ---
    k = pd.read_csv(keeper_rounds_csv, dtype={"Sleeper ID": "string"}).rename(
        columns={"Sleeper ID": "Sleeper_ID",
                 "Player Name": "Player_name",
                 "2025 keeper round": "Keeper_round_2025"}
    )
    k["Sleeper_ID"] = k["Sleeper_ID"].str.strip()
    name_map  = dict(zip(k["Sleeper_ID"], k["Player_name"]))
    round_map = dict(zip(k["Sleeper_ID"], pd.to_numeric(k["Keeper_round_2025"], errors="coerce")))

    def get_name(pid):
        pid = str(pid)
        if pid in name_map:
            return name_map[pid]
        if player_list and pid in player_list:
            pl = player_list[pid]
            return pl.get("full_name") or f"{pl.get('first_name','').strip()} {pl.get('last_name','').strip()}".strip()
        return pid

    rows = []
    df = managers_df.sort_values("Draft_order") if "Draft_order" in managers_df.columns else managers_df

    for row in df.itertuples(index=False):
        mname   = row.display_name
        keepers = list(row.Keepers) if isinstance(row.Keepers, list) else []
        krounds = list(getattr(row, "Keeper_rounds_2025", [])) if isinstance(getattr(row, "Keeper_rounds_2025", []), list) else [None]*len(keepers)

        # Prefer precomputed assignments (list of (id, pick))
        assignments = getattr(row, "Keeper_assignments", None)
        pick_by_id = {str(pid): int(pick) for (pid, pick) in assignments} if isinstance(assignments, list) and assignments else {}

        # spacer + manager header
        rows.append({"Keeper": "", "Sleeper ID": "", "Designated Keeper Round": "", "Keeper Pick": "", "Draftboard Pick": ""})
        rows.append({"Keeper": mname, "Sleeper ID": "", "Designated Keeper Round": "", "Keeper Pick": "", "Draftboard Pick": ""})

        for pid, kr in zip(keepers, krounds):
            sid = str(pid)
            pname = get_name(sid)
            try:
                kr_int = int(kr) if kr is not None and not (isinstance(kr, float) and math.isnan(kr)) else round_map.get(sid)
            except Exception:
                kr_int = round_map.get(sid)
            assigned_pick = pick_by_id.get(sid, None)
            rows.append({
                "Keeper": pname,
                "Sleeper ID": sid,
                "Designated Keeper Round": kr_int,
                "Keeper Pick": assigned_pick,
                "Draftboard Pick": to_round_pick(assigned_pick, L),
            })

    out_df = pd.DataFrame(rows, columns=["Keeper", "Sleeper ID", "Designated Keeper Round", "Keeper Pick", "Draftboard Pick"])

    # --- Write & light formatting ---
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        out_df.to_excel(writer, index=False, sheet_name="Keepers")
        ws = writer.sheets["Keepers"]
        wb = writer.book

        header_fmt  = wb.add_format({"bold": True, "bg_color": "#EEEEEE", "bottom": 1})
        manager_fmt = wb.add_format({"bold": True})

        ws.set_row(0, None, header_fmt)

        # bold manager rows (Keeper has text AND Sleeper ID is blank)
        for r_idx, row in out_df.iterrows():
            excel_row = r_idx + 1
            keeper = row["Keeper"]; sid = row["Sleeper ID"]
            if isinstance(keeper, str) and keeper and (pd.isna(sid) or str(sid) == ""):
                ws.set_row(excel_row, None, manager_fmt)

        # column widths
        ws.set_column("A:A", 26)  # Keeper / manager header
        ws.set_column("B:B", 14)  # Sleeper ID
        ws.set_column("C:C", 24)  # Designated Keeper Round
        ws.set_column("D:D", 12)  # Keeper Pick (overall)
        ws.set_column("E:E", 14)  # Draftboard Pick (round.pick)

    return out_xlsx



def main():
    # --- Config & pulls -----------------------------------------------------------
    league_id    = 1312084354846961664
    current_year = 2026
    name_disambiguation = {}
    ### IN 2025_keeper_rounds.csv, the code expects a column named "2025 keeper round". In 2025, this was placed manually

    league        = League(league_id)
    managers_list = league.get_users()      # list[dict]
    rosters       = league.get_rosters()    # list[dict]
    draft         = league.get_specific_draft()  # dict
    players       = Players()
    d             = players.get_all_players()
    player_list   = {k: d[k] for k in sorted(
        d.keys(),
        key=lambda k: (0, int(k)) if k.isdigit() else (1, k)  # nums first, then A–Z
    )}

    # --- Name disambiguation ------------------------------------------------------
    # Changes the player_list to account for any name disambiguation
    for player_id in name_disambiguation:
        player_list[player_id]['full_name'] = name_disambiguation[player_id]

    # --- Managers table -----------------------------------------------------------
    # Minimal columns, clean names/types
    managers_df = (
        pd.json_normalize(managers_list)
        .reindex(columns=["display_name", "user_id", "league_id"])
        .rename(columns={"user_id": "User_id", "league_id": "League_id"})
        .astype({"display_name": "string", "User_id": "string", "League_id": "string"})
    )

    # Draft position (1..N) per manager
    managers_df["Draft_order"] = managers_df["User_id"].map(draft["draft_order"]).astype("Int64")
    managers_df = managers_df.sort_values("Draft_order").reset_index(drop=True)

    # Optional but handy: add Roster_id from draft slots (slot -> roster)
    slot_to_roster = {int(k): int(v) for k, v in draft.get("slot_to_roster_id", {}).items()}
    if slot_to_roster:
        managers_df["Roster_id"] = managers_df["Draft_order"].map(slot_to_roster).astype("Int64")

    # --- Original picks ------------------------------------------
    num_rounds = int(draft.get("settings", {}).get("rounds", 22))

    # Build draft_pos dict in the SAME order as managers_df so your function's order check passes
    draft_pos_ordered = {uid: draft["draft_order"][uid] for uid in managers_df["User_id"]}
    managers_uid_order = list(draft_pos_ordered.keys())

    orig_picks_by_user = original_draft_picks(draft_pos_ordered, managers_uid_order, num_rounds)
    managers_df["Original_picks"] = managers_df["User_id"].map(orig_picks_by_user)

    # --- Keepers (merge from rosters) --------------------------------------------
    r = (pd.DataFrame(rosters)[["owner_id", "roster_id", "keepers"]]
        .rename(columns={"owner_id": "User_id", "roster_id": "Roster_id", "keepers": "Keepers"}))
    r["User_id"] = r["User_id"].astype(str)
    r["Keepers"] = r["Keepers"].apply(lambda k: k or [])  # None -> []

    if "Roster_id" in managers_df.columns:
        managers_df = managers_df.merge(r, on=["User_id", "Roster_id"], how="left")
    else:
        managers_df = managers_df.merge(r[["User_id", "Keepers"]], on="User_id", how="left")

    managers_df["Keepers"] = managers_df["Keepers"].apply(lambda k: k if isinstance(k, list) else [])

    # --- Current picks from Sleeper (post-trades) --------------------------------
    picks_map = sleeper_current_picks(league_id=league_id, season=current_year)
    managers_df["Current_picks"] = managers_df["User_id"].map(picks_map).apply(lambda x: x or [])

    # Keep the table ordered by draft slot
    managers_df = managers_df.sort_values("Draft_order").reset_index(drop=True)

    # --- Integrity check (expects display-name keys in draft order) --------------
    ordered = managers_df.sort_values("Draft_order")
    picks_by_name      = dict(zip(ordered["display_name"], ordered["Current_picks"]))
    managers_by_name   = ordered["display_name"].tolist()
    check_pick_integrity(picks_by_name, managers_by_name, num_rounds)




    #Other initialization items
    kr_doc = f'{current_year}_Keeper_Rounds.csv'

    # --- Load keeper-round sheet (keep only what we need) ------------------------
    k = (pd.read_csv(kr_doc, dtype={"Sleeper ID": "string"})
        .rename(columns={
            "Sleeper ID": "Sleeper_ID",
            "Player Name": "Player_name",
            "2025 keeper round": "Keeper_round_2025",
        }))

    # Clean types
    k["Sleeper_ID"]        = k["Sleeper_ID"].str.strip()
    k["Keeper_round_2025"] = pd.to_numeric(k["Keeper_round_2025"], errors="coerce").astype("Int64")

    # Build lookups
    round_map = dict(zip(k["Sleeper_ID"], k["Keeper_round_2025"]))
    name_map  = dict(zip(k["Sleeper_ID"], k["Player_name"]))

    # --- Ensure Keepers are strings, then map rounds -----------------------------
    managers_df["Keepers"] = managers_df["Keepers"].apply(lambda lst: lst if isinstance(lst, list) else [])
    managers_df["Keepers"] = managers_df["Keepers"].apply(lambda lst: [str(x).strip() for x in lst])

    # List of rounds aligned with the Keepers list
    managers_df["Keeper_rounds_2025"] = managers_df["Keepers"].apply(
        lambda ids: [round_map.get(pid) for pid in ids]
    )

    # (nice to have) zipped tuples (player_id, round) and names, if you want them:
    managers_df["Keepers_with_rounds"] = managers_df.apply(
        lambda r: list(zip(r["Keepers"], r["Keeper_rounds_2025"])), axis=1
    )
    managers_df["Keeper_names"] = managers_df["Keepers"].apply(lambda ids: [name_map.get(pid) for pid in ids])

    ok = check_keeper_integrity_df(
    managers_df=managers_df,
    rosters=rosters,
    player_list=player_list,            # Sleeper players dict keyed by string IDs
    early_round_threshold=10,           # early = round < 10
    max_keepers=6
    )
    print("Keeper integrity check passed:", ok)

    # Build assignments dict keyed by display_name
    keeper_assignments = assign_keepers_from_df(managers_df)

    # Add as a column
    managers_df["Keeper_assignments"] = managers_df["display_name"].map(keeper_assignments)

    xlsx_path = export_keeper_sheet(
    managers_df=managers_df,
    keeper_rounds_csv="2026_Keeper_rounds.csv",
    out_xlsx="2026_Keeper_Pick_Assignments.xlsx",
    player_list=player_list  # optional; helps fill names not present in CSV
    )
    print("Wrote:", xlsx_path)




    print('finished')

if __name__ == "__main__": 
    main()