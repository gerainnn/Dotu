"""Quick sanity test for the poker engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.poker import GameManager, serialize_game, best_hand, HAND_NAMES

# Hand evaluator spot checks
def name_of(cards):
    return HAND_NAMES[best_hand(cards)[0]]

assert name_of(["As","Ks","Qs","Js","Ts"]) == "Straight Flush"
assert name_of(["Ah","Ad","Ac","As","2d"]) == "Four of a Kind"
assert name_of(["Ah","Ad","Ac","2s","2d"]) == "Full House"
assert name_of(["Ah","Kh","Qh","Jh","9h"]) == "Flush"
assert name_of(["5s","4d","3c","2h","Ah"]) == "Straight"  # wheel
assert name_of(["8s","8d","8c","2h","5d"]) == "Three of a Kind"
assert name_of(["8s","8d","2c","2h","5d"]) == "Two Pair"
assert name_of(["8s","8d","2c","7h","5d"]) == "Pair"
assert name_of(["As","Kd","Qc","Jh","9d"]) == "High Card"
print("hand evaluator: OK")

# Run a few full hands
mgr = GameManager()
for i in range(20):
    g = mgr.new_hand(user_id=42, human_name="Test")
    # human just folds every time
    safety = 0
    while g.stage not in ("showdown", "finished"):
        if g.turn_seat == 0:
            g = mgr.human_action(42, "fold")
        else:
            # bots auto-played already; if they didn't finish, advance
            break
        safety += 1
        if safety > 30:
            raise SystemExit("infinite loop")
    assert g.stage in ("showdown", "finished"), f"stage={g.stage}"
print("20 hands (human folds): OK")

# Run a hand where human always calls/checks
for i in range(20):
    g = mgr.new_hand(user_id=99, human_name="Caller")
    safety = 0
    while g.stage not in ("showdown", "finished"):
        if g.turn_seat == 0:
            me = g.players[0]
            to_call = g.current_bet - me.bet
            g = mgr.human_action(99, "check" if to_call == 0 else "call")
        else:
            break
        safety += 1
        if safety > 60:
            raise SystemExit("infinite loop")
    assert g.stage in ("showdown", "finished")
print("20 hands (human passive): OK")

# Serialization
payload = serialize_game(g, viewer_user_id=99)
assert "players" in payload and "community" in payload
print("serialize: OK")
print("ALL OK")
