"""Texas Hold'em poker engine.

Single-table cash hand: 1 human + 3 AI bots.
Stateful — one Game instance per user, kept in memory by GameManager.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from itertools import combinations
from typing import Optional


SUITS = ["s", "h", "d", "c"]  # spades, hearts, diamonds, clubs
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14

SMALL_BLIND = 5
BIG_BLIND = 10
START_STACK = 1000  # chips per seat at the start of a hand


# ------------------------------ cards ------------------------------ #

def make_deck() -> list[str]:
    deck = [r + s for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


def card_rank(card: str) -> int:
    return RANK_VALUE[card[0]]


def card_suit(card: str) -> str:
    return card[1]


# ------------------------------ hand evaluation ------------------------------ #
# Returns a tuple sortable lexicographically; bigger == better.
# Categories:
# 8 straight flush, 7 quads, 6 full house, 5 flush, 4 straight,
# 3 trips, 2 two pair, 1 pair, 0 high card

def _eval_5(cards: list[str]) -> tuple:
    ranks = sorted((card_rank(c) for c in cards), reverse=True)
    suits = [card_suit(c) for c in cards]

    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    # group by (count desc, rank desc)
    grouped = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    count_pattern = tuple(c for _, c in grouped)
    rank_order = tuple(r for r, _ in grouped)

    flush = len(set(suits)) == 1

    uniq = sorted(set(ranks), reverse=True)
    straight_high = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        # wheel: A-2-3-4-5
        elif uniq == [14, 5, 4, 3, 2]:
            straight_high = 5

    if flush and straight_high:
        return (8, straight_high)
    if count_pattern == (4, 1):
        return (7, rank_order[0], rank_order[1])
    if count_pattern == (3, 2):
        return (6, rank_order[0], rank_order[1])
    if flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if count_pattern == (3, 1, 1):
        return (3, rank_order[0], rank_order[1], rank_order[2])
    if count_pattern == (2, 2, 1):
        return (2, rank_order[0], rank_order[1], rank_order[2])
    if count_pattern == (2, 1, 1, 1):
        return (1, rank_order[0], rank_order[1], rank_order[2], rank_order[3])
    return (0, *ranks)


def best_hand(cards: list[str]) -> tuple:
    """Best 5-card hand from <=7 cards."""
    if len(cards) < 5:
        # pad: just rank what we have, treated as high card
        return _eval_5(cards + [cards[0]] * (5 - len(cards)))
    best = (0,)
    for combo in combinations(cards, 5):
        s = _eval_5(list(combo))
        if s > best:
            best = s
    return best


HAND_NAMES = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "Pair",
    0: "High Card",
}


# ------------------------------ game state ------------------------------ #

STAGES = ["preflop", "flop", "turn", "river", "showdown", "finished"]


@dataclass
class Player:
    seat: int
    name: str
    is_human: bool
    stack: int = START_STACK
    hole: list[str] = field(default_factory=list)
    bet: int = 0          # chips put in this betting round
    total_bet: int = 0    # chips put in this hand
    folded: bool = False
    all_in: bool = False
    last_action: str = ""
    style: str = "balanced"  # AI personality

    def to_public(self, reveal: bool) -> dict:
        return {
            "seat": self.seat,
            "name": self.name,
            "is_human": self.is_human,
            "stack": self.stack,
            "hole": self.hole if reveal or self.is_human else ["??", "??"],
            "bet": self.bet,
            "folded": self.folded,
            "all_in": self.all_in,
            "last_action": self.last_action,
        }


@dataclass
class Game:
    user_id: int
    players: list[Player]
    deck: list[str] = field(default_factory=list)
    community: list[str] = field(default_factory=list)
    pot: int = 0
    current_bet: int = 0
    last_raise: int = BIG_BLIND
    stage: str = "preflop"
    turn_seat: int = 0
    dealer_seat: int = 0
    log: list[str] = field(default_factory=list)
    winners: list[dict] = field(default_factory=list)
    delta: int = 0  # chip delta for human after the hand


# ------------------------------ game manager ------------------------------ #

AI_NAMES = ["Volk", "Lira", "Onyx", "Sable", "Kira", "Nox", "Zane", "Rhea"]
AI_STYLES = ["tight", "balanced", "aggressive"]


class GameManager:
    """Holds one in-progress hand per user_id."""

    def __init__(self) -> None:
        self.games: dict[int, Game] = {}

    # --- lifecycle ---

    def new_hand(self, user_id: int, human_name: str, buy_in: int = START_STACK) -> Game:
        prev = self.games.get(user_id)
        # carry stacks from the previous hand if it finished
        if prev and prev.stage == "finished":
            seats = []
            for p in prev.players:
                # if a bot busted, replace with a fresh one
                if p.stack <= 0 and not p.is_human:
                    seats.append(Player(
                        seat=p.seat,
                        name=random.choice(AI_NAMES),
                        is_human=False,
                        stack=buy_in,
                        style=random.choice(AI_STYLES),
                    ))
                else:
                    p.hole = []
                    p.bet = 0
                    p.total_bet = 0
                    p.folded = False
                    p.all_in = False
                    p.last_action = ""
                    if p.is_human and p.stack <= 0:
                        # rebuy
                        p.stack = buy_in
                    seats.append(p)
            dealer = (prev.dealer_seat + 1) % len(seats)
        else:
            random.shuffle(AI_NAMES)
            seats = [
                Player(seat=0, name=human_name or "You", is_human=True, stack=buy_in),
                Player(seat=1, name=AI_NAMES[0], is_human=False, stack=buy_in,
                       style=random.choice(AI_STYLES)),
                Player(seat=2, name=AI_NAMES[1], is_human=False, stack=buy_in,
                       style=random.choice(AI_STYLES)),
                Player(seat=3, name=AI_NAMES[2], is_human=False, stack=buy_in,
                       style=random.choice(AI_STYLES)),
            ]
            dealer = random.randrange(4)

        game = Game(
            user_id=user_id,
            players=seats,
            deck=make_deck(),
            community=[],
            pot=0,
            current_bet=0,
            last_raise=BIG_BLIND,
            stage="preflop",
            dealer_seat=dealer,
            log=[],
        )
        self._post_blinds(game)
        self._deal_holes(game)
        # action starts left of big blind
        game.turn_seat = self._next_active(game, self._sb_seat(game) + 1)
        self.games[user_id] = game
        # let bots act if it's their turn
        self._auto_play_bots(game)
        return game

    def get(self, user_id: int) -> Optional[Game]:
        return self.games.get(user_id)

    # --- helpers ---

    def _sb_seat(self, g: Game) -> int:
        # heads-up rule not used (we always have 4 seats); SB = dealer + 1
        return (g.dealer_seat + 1) % len(g.players)

    def _bb_seat(self, g: Game) -> int:
        return (g.dealer_seat + 2) % len(g.players)

    def _post_blinds(self, g: Game) -> None:
        sb = g.players[self._sb_seat(g)]
        bb = g.players[self._bb_seat(g)]
        self._put_chips(sb, SMALL_BLIND)
        self._put_chips(bb, BIG_BLIND)
        g.pot = sb.bet + bb.bet
        g.current_bet = BIG_BLIND
        g.last_raise = BIG_BLIND
        g.log.append(f"{sb.name} posts SB {SMALL_BLIND}")
        g.log.append(f"{bb.name} posts BB {BIG_BLIND}")

    def _put_chips(self, p: Player, amount: int) -> int:
        amount = min(amount, p.stack)
        p.stack -= amount
        p.bet += amount
        p.total_bet += amount
        if p.stack == 0:
            p.all_in = True
        return amount

    def _deal_holes(self, g: Game) -> None:
        for p in g.players:
            p.hole = [g.deck.pop(), g.deck.pop()]

    def _active_players(self, g: Game) -> list[Player]:
        return [p for p in g.players if not p.folded]

    def _can_act(self, p: Player) -> bool:
        return not p.folded and not p.all_in and p.stack > 0

    def _next_active(self, g: Game, start: int) -> int:
        n = len(g.players)
        for i in range(n):
            seat = (start + i) % n
            if self._can_act(g.players[seat]):
                return seat
        return -1

    # --- betting round flow ---

    def _round_complete(self, g: Game) -> bool:
        active = self._active_players(g)
        if len(active) <= 1:
            return True
        actors = [p for p in active if not p.all_in]
        if not actors:
            return True
        # everyone who can act has matched current_bet AND has acted at least once this round
        for p in actors:
            if p.bet != g.current_bet:
                return False
            if p.last_action == "":
                return False
        return True

    def _advance_stage(self, g: Game) -> None:
        # reset bets for next street
        for p in g.players:
            p.bet = 0
            p.last_action = ""
        g.current_bet = 0
        g.last_raise = BIG_BLIND

        if g.stage == "preflop":
            g.stage = "flop"
            g.deck.pop()  # burn
            g.community += [g.deck.pop(), g.deck.pop(), g.deck.pop()]
            g.log.append("--- FLOP ---")
        elif g.stage == "flop":
            g.stage = "turn"
            g.deck.pop()
            g.community.append(g.deck.pop())
            g.log.append("--- TURN ---")
        elif g.stage == "turn":
            g.stage = "river"
            g.deck.pop()
            g.community.append(g.deck.pop())
            g.log.append("--- RIVER ---")
        elif g.stage == "river":
            self._showdown(g)
            return

        # action starts left of dealer
        g.turn_seat = self._next_active(g, g.dealer_seat + 1)
        if g.turn_seat == -1:
            # everyone all-in, fast-forward
            self._fast_forward_to_showdown(g)

    def _fast_forward_to_showdown(self, g: Game) -> None:
        while g.stage in ("preflop", "flop", "turn", "river"):
            if g.stage == "preflop":
                g.stage = "flop"
                g.deck.pop()
                g.community += [g.deck.pop(), g.deck.pop(), g.deck.pop()]
                g.log.append("--- FLOP ---")
            elif g.stage == "flop":
                g.stage = "turn"
                g.deck.pop()
                g.community.append(g.deck.pop())
                g.log.append("--- TURN ---")
            elif g.stage == "turn":
                g.stage = "river"
                g.deck.pop()
                g.community.append(g.deck.pop())
                g.log.append("--- RIVER ---")
            else:
                break
        self._showdown(g)

    # --- end of hand ---

    def _award_uncontested(self, g: Game) -> None:
        winner = self._active_players(g)[0]
        winner.stack += g.pot
        g.winners = [{
            "seat": winner.seat,
            "name": winner.name,
            "amount": g.pot,
            "hand": "Uncontested",
        }]
        if winner.is_human:
            g.delta = g.pot - g.players[0].total_bet
        else:
            g.delta = -g.players[0].total_bet
        g.log.append(f"{winner.name} wins {g.pot} (uncontested)")
        g.stage = "finished"

    def _showdown(self, g: Game) -> None:
        g.stage = "showdown"
        active = self._active_players(g)
        # build side pots based on total_bet contributions
        contribs = sorted(set(p.total_bet for p in g.players if p.total_bet > 0))
        pots: list[tuple[int, list[Player]]] = []  # (amount, eligibles)
        prev = 0
        for level in contribs:
            amount = 0
            eligibles = []
            for p in g.players:
                contrib = max(0, min(p.total_bet, level) - prev)
                amount += contrib
            for p in active:
                if p.total_bet >= level:
                    eligibles.append(p)
            if amount > 0 and eligibles:
                pots.append((amount, eligibles))
            prev = level

        winners_log: list[dict] = []
        for amount, eligibles in pots:
            scores = [(best_hand(p.hole + g.community), p) for p in eligibles]
            best_score = max(s for s, _ in scores)
            top = [p for s, p in scores if s == best_score]
            share = amount // len(top)
            remainder = amount - share * len(top)
            for i, p in enumerate(top):
                payout = share + (1 if i < remainder else 0)
                p.stack += payout
                winners_log.append({
                    "seat": p.seat,
                    "name": p.name,
                    "amount": payout,
                    "hand": HAND_NAMES[best_score[0]],
                    "hole": p.hole,
                })
                g.log.append(f"{p.name} wins {payout} with {HAND_NAMES[best_score[0]]}")
        g.winners = winners_log
        # human delta
        human = g.players[0]
        won = sum(w["amount"] for w in winners_log if w["seat"] == 0)
        g.delta = won - human.total_bet
        g.stage = "finished"

    # --- public actions ---

    def human_action(self, user_id: int, action: str, amount: int = 0) -> Game:
        g = self.games[user_id]
        if g.stage in ("showdown", "finished"):
            return g
        if g.turn_seat != 0:
            return g
        self._apply_action(g, g.players[0], action, amount)
        self._after_action(g)
        return g

    def _apply_action(self, g: Game, p: Player, action: str, amount: int = 0) -> None:
        if action == "fold":
            p.folded = True
            p.last_action = "fold"
            g.log.append(f"{p.name} folds")
            return
        if action == "check":
            if g.current_bet != p.bet:
                # invalid -> treat as call
                action = "call"
            else:
                p.last_action = "check"
                g.log.append(f"{p.name} checks")
                return
        if action == "call":
            need = g.current_bet - p.bet
            paid = self._put_chips(p, need)
            g.pot += paid
            p.last_action = "call" if paid >= need else "all-in"
            g.log.append(f"{p.name} calls {paid}")
            return
        if action == "raise":
            # amount = total bet target for this round
            target = max(amount, g.current_bet + g.last_raise)
            target = min(target, p.bet + p.stack)
            need = target - p.bet
            if need <= 0:
                # fall back to call
                self._apply_action(g, p, "call")
                return
            paid = self._put_chips(p, need)
            g.pot += paid
            raise_amount = (p.bet) - g.current_bet
            if raise_amount > 0:
                g.last_raise = max(g.last_raise, raise_amount)
                g.current_bet = p.bet
                # other players who already acted need to act again
                for other in g.players:
                    if other is not p and not other.folded and not other.all_in:
                        if other.last_action in ("check", "call"):
                            other.last_action = ""
            p.last_action = "all-in" if p.all_in else "raise"
            g.log.append(f"{p.name} {'goes all-in' if p.all_in else 'raises to'} {p.bet}")
            return
        if action == "allin":
            need = p.stack
            paid = self._put_chips(p, need)
            g.pot += paid
            if p.bet > g.current_bet:
                raise_amount = p.bet - g.current_bet
                g.last_raise = max(g.last_raise, raise_amount)
                g.current_bet = p.bet
                for other in g.players:
                    if other is not p and not other.folded and not other.all_in:
                        if other.last_action in ("check", "call"):
                            other.last_action = ""
            p.last_action = "all-in"
            g.log.append(f"{p.name} goes all-in for {paid}")
            return

    def _after_action(self, g: Game) -> None:
        active = self._active_players(g)
        if len(active) == 1:
            self._award_uncontested(g)
            return
        if self._round_complete(g):
            self._advance_stage(g)
            if g.stage in ("showdown", "finished"):
                return
        else:
            g.turn_seat = self._next_active(g, g.turn_seat + 1)
        self._auto_play_bots(g)

    # --- AI ---

    def _auto_play_bots(self, g: Game) -> None:
        # safety counter
        for _ in range(60):
            if g.stage in ("showdown", "finished"):
                return
            if g.turn_seat == 0:
                return
            p = g.players[g.turn_seat]
            if not self._can_act(p):
                g.turn_seat = self._next_active(g, g.turn_seat + 1)
                if g.turn_seat == -1 or self._round_complete(g):
                    self._advance_stage(g)
                continue
            action, amount = self._bot_decide(g, p)
            self._apply_action(g, p, action, amount)
            if len(self._active_players(g)) == 1:
                self._award_uncontested(g)
                return
            if self._round_complete(g):
                self._advance_stage(g)
                if g.stage in ("showdown", "finished"):
                    return
                continue
            g.turn_seat = self._next_active(g, g.turn_seat + 1)

    def _bot_decide(self, g: Game, p: Player) -> tuple[str, int]:
        strength = self._hand_strength(p.hole, g.community)
        to_call = g.current_bet - p.bet
        pot_odds = to_call / (g.pot + to_call) if (g.pot + to_call) > 0 else 0

        # personality tweaks
        if p.style == "tight":
            strength -= 0.07
        elif p.style == "aggressive":
            strength += 0.05

        # randomness
        strength += random.uniform(-0.04, 0.04)

        if to_call == 0:
            # check or bet
            if strength > 0.7 and random.random() < 0.6:
                bet = max(BIG_BLIND, int(g.pot * random.uniform(0.4, 0.8)))
                return ("raise", p.bet + bet)
            if strength > 0.55 and random.random() < 0.3:
                bet = max(BIG_BLIND, int(g.pot * 0.4))
                return ("raise", p.bet + bet)
            return ("check", 0)

        # facing a bet
        if strength < pot_odds - 0.05:
            return ("fold", 0)
        if strength > 0.78 and random.random() < 0.55:
            target = p.bet + to_call + max(BIG_BLIND, int(g.pot * random.uniform(0.6, 1.1)))
            return ("raise", target)
        if strength >= pot_odds:
            return ("call", 0)
        if random.random() < 0.15:  # bluff catch
            return ("call", 0)
        return ("fold", 0)

    def _hand_strength(self, hole: list[str], community: list[str]) -> float:
        """Rough 0..1 strength estimate (Monte Carlo lite)."""
        # If preflop: simple Chen-like score
        if not community:
            return self._preflop_strength(hole)
        # Post-flop: sample 60 random opponent hands & boards
        used = set(hole + community)
        deck = [c for c in (r + s for r in RANKS for s in SUITS) if c not in used]
        wins = ties = total = 0
        trials = 60
        for _ in range(trials):
            random.shuffle(deck)
            opp = deck[:2]
            board = community + deck[2:2 + (5 - len(community))]
            mine = best_hand(hole + board)
            theirs = best_hand(opp + board)
            if mine > theirs:
                wins += 1
            elif mine == theirs:
                ties += 1
            total += 1
        return (wins + ties * 0.5) / total

    def _preflop_strength(self, hole: list[str]) -> float:
        r1, r2 = card_rank(hole[0]), card_rank(hole[1])
        suited = card_suit(hole[0]) == card_suit(hole[1])
        high, low = max(r1, r2), min(r1, r2)
        # Chen-ish formula normalized
        base = {14: 10, 13: 8, 12: 7, 11: 6}.get(high, high / 2)
        score = base
        if r1 == r2:
            score = max(5, base * 2)
            if r1 < 5:
                score = 5
        gap = high - low - 1
        if gap == 0:
            pass
        elif gap == 1:
            score -= 1
        elif gap == 2:
            score -= 2
        elif gap == 3:
            score -= 4
        else:
            score -= 5
        if suited:
            score += 2
        if gap <= 1 and high < 12:
            score += 1
        # normalize ~ 0..1 (raw range roughly -3..20)
        return max(0.0, min(1.0, (score + 3) / 23))


# ------------------------------ serialization ------------------------------ #

def serialize_game(g: Game, viewer_user_id: int) -> dict:
    show = g.stage in ("showdown", "finished")
    return {
        "stage": g.stage,
        "pot": g.pot,
        "current_bet": g.current_bet,
        "min_raise": g.last_raise,
        "community": g.community,
        "turn_seat": g.turn_seat,
        "dealer_seat": g.dealer_seat,
        "players": [p.to_public(reveal=show) for p in g.players],
        "log": g.log[-20:],
        "winners": g.winners,
        "delta": g.delta,
        "small_blind": SMALL_BLIND,
        "big_blind": BIG_BLIND,
    }
