# Battle Line keeper pick assignments

## Setup

From PowerShell in the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Generate the 2026 assignments

1. Confirm every selected keeper has a numeric value in the `2026 keeper round`
   column of `2026_Keeper_Rounds.csv`. Values such as `2026 ADP Round + 4`
   must be resolved using the league's agreed ADP source first.
2. Run:

```powershell
python Pick_assignment_26.py
```

The script validates the live Sleeper draft, rosters, traded picks, keeper rules,
and keeper-round inputs before writing `2026_Keeper_Pick_Assignments.xlsx`.

## Tests

```powershell
python -m unittest discover -s tests -v
```
