import json
import os
import time
from flask import Flask, render_template, request, session, jsonify
from game_engine import (
    generate_problem, calculate_score, get_completion_bonus,
    get_star_rating, get_feedback_message, get_level_complete_message,
    get_boss_defeat_message, get_level_info, is_boss_level,
    calculate_boss_damage, check_achievements,
    generate_dungeon_problem, generate_gauntlet_problem,
    is_dungeon_boss_floor, get_dungeon_boss_special,
    LEVEL_CONFIG, DAMAGE, REALM_NAMES, LEVEL_NAMES, BOSS_NAMES, BOSS_HP,
    ACHIEVEMENTS, FAST_THRESHOLD, SLOW_THRESHOLD, FAIL_THRESHOLD,
    DUNGEON_FLOORS, DUNGEON_PROBLEMS_PER_FLOOR, DUNGEON_DAMAGE, DUNGEON_BOSSES,
    GAUNTLET_FAST_THRESHOLD, GAUNTLET_SLOW_THRESHOLD, GAUNTLET_FAIL_THRESHOLD,
    BASE_POINTS,
)

app = Flask(__name__)
app.secret_key = 'math-quest-secret-key-change-in-production'

REALM_ORDER = ['easy', 'medium', 'hard', 'expert']
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), 'accounts.json')


# --- Account persistence ---

def _load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=2)


def _get_account(name):
    accounts = _load_accounts()
    return accounts.get(name)


def _save_account(name, data):
    accounts = _load_accounts()
    accounts[name] = data
    _save_accounts(accounts)


def _delete_account(name):
    accounts = _load_accounts()
    accounts.pop(name, None)
    _save_accounts(accounts)


def _new_account_data():
    return {
        'completed_levels': {},
        'achievements': [],
        'score': 0,
        'total_fast_answers': 0,
        'bosses_defeated': 0,
        'timers_off': False,
    }


def _persist_game_to_account(game):
    """Save current game progress back to the account file."""
    name = game.get('player_name', '')
    if not name:
        return
    account = _get_account(name) or _new_account_data()
    account['completed_levels'] = game.get('completed_levels', {})
    account['achievements'] = game.get('achievements', [])
    account['score'] = game.get('score', 0)
    account['total_fast_answers'] = game.get('total_fast_answers', 0)
    account['bosses_defeated'] = game.get('bosses_defeated', 0)
    account['timers_off'] = game.get('timers_off', False)
    _save_account(name, account)


# --- Routes ---

@app.route('/')
def index():
    game = session.get('game')
    player_name = game.get('player_name', '') if game else ''
    completed = game.get('completed_levels', {}) if game else {}
    achievements = game.get('achievements', []) if game else []
    timers_off = game.get('timers_off', False) if game else False
    realm_status = {}
    for diff in REALM_ORDER:
        realm_status[diff] = _get_realm_status(completed, diff)
    accounts_data = _load_accounts()
    account_names = list(accounts_data.keys())

    # Calculate achievement percentages across all accounts
    total_accounts = len(accounts_data)
    ach_stats = {}
    for aid, adata in ACHIEVEMENTS.items():
        if total_accounts > 0:
            count = sum(1 for acc in accounts_data.values() if aid in acc.get('achievements', []))
            pct = round((count / total_accounts) * 100)
        else:
            pct = 0
        ach_stats[aid] = {**adata, 'pct': pct, 'earned': aid in achievements}

    return render_template('index.html', player_name=player_name,
                           realm_status=realm_status, achievements=achievements,
                           all_achievements=ACHIEVEMENTS, timers_off=timers_off,
                           accounts=account_names, ach_stats=ach_stats)


@app.route('/game')
def game():
    return render_template('game.html')


@app.route('/api/accounts')
def list_accounts():
    accounts = _load_accounts()
    result = []
    for name, data in accounts.items():
        result.append({
            'name': name,
            'score': data.get('score', 0),
            'achievements': len(data.get('achievements', [])),
        })
    return jsonify({'accounts': result})


@app.route('/api/account/load', methods=['POST'])
def load_account():
    data = request.get_json()
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'No name provided'}), 400
    account = _get_account(name)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    # Load into session
    session['game'] = {
        'mode': 'quest',
        'player_name': name,
        'difficulty': 'easy',
        'current_level': 1,
        'hp': 100,
        'max_hp': 100,
        'score': account.get('score', 0),
        'streak': 0,
        'best_streak': 0,
        'problems_answered': 0,
        'problems_correct': 0,
        'level_score': 0,
        'current_problem': None,
        'problem_start_time': None,
        'fast_streak': 0,
        'heals_this_level': 0,
        'total_fast_answers': account.get('total_fast_answers', 0),
        'bosses_defeated': account.get('bosses_defeated', 0),
        'boss_hp': 0,
        'boss_max_hp': 0,
        'in_boss_fight': False,
        'charge_meter': 0,
        'completed_levels': account.get('completed_levels', {}),
        'achievements': account.get('achievements', []),
        'timers_off': account.get('timers_off', False),
    }
    return jsonify({'status': 'ok', 'name': name})


@app.route('/api/account/delete', methods=['POST'])
def delete_account():
    data = request.get_json()
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'No name provided'}), 400
    _delete_account(name)
    # If current session is this account, clear it
    game = session.get('game')
    if game and game.get('player_name') == name:
        session.pop('game', None)
    return jsonify({'status': 'ok'})


@app.route('/api/start', methods=['POST'])
def start_game():
    data = request.get_json()
    difficulty = data.get('difficulty', 'easy')
    player_name = data.get('player_name', 'Wizard')
    timers_off = data.get('timers_off', False)

    if difficulty not in LEVEL_CONFIG:
        return jsonify({'error': 'Invalid difficulty'}), 400

    # Try to load existing account, or create new
    account = _get_account(player_name)
    if account:
        prev_completed = account.get('completed_levels', {})
        prev_score = account.get('score', 0)
        prev_achievements = account.get('achievements', [])
        prev_total_fast = account.get('total_fast_answers', 0)
        prev_bosses = account.get('bosses_defeated', 0)
    else:
        prev_game = session.get('game', {})
        if prev_game.get('player_name') == player_name:
            prev_completed = prev_game.get('completed_levels', {})
            prev_score = prev_game.get('score', 0)
            prev_achievements = prev_game.get('achievements', [])
            prev_total_fast = prev_game.get('total_fast_answers', 0)
            prev_bosses = prev_game.get('bosses_defeated', 0)
        else:
            prev_completed = {}
            prev_score = 0
            prev_achievements = []
            prev_total_fast = 0
            prev_bosses = 0

    status = _get_realm_status(prev_completed, difficulty)
    if status == 'locked':
        return jsonify({'error': 'Realm locked'}), 403

    session['game'] = {
        'mode': 'quest',
        'player_name': player_name,
        'difficulty': difficulty,
        'current_level': 1,
        'hp': 100,
        'max_hp': 100,
        'score': prev_score,
        'streak': 0,
        'best_streak': 0,
        'problems_answered': 0,
        'problems_correct': 0,
        'level_score': 0,
        'current_problem': None,
        'problem_start_time': None,
        'fast_streak': 0,
        'heals_this_level': 0,
        'total_fast_answers': prev_total_fast,
        'bosses_defeated': prev_bosses,
        'boss_hp': 0,
        'boss_max_hp': 0,
        'in_boss_fight': False,
        'charge_meter': 0,
        'completed_levels': prev_completed,
        'achievements': prev_achievements,
        'timers_off': timers_off,
    }

    # Save/create account
    _persist_game_to_account(session['game'])

    return jsonify({
        'status': 'ok',
        'game_state': _safe_state(),
        'level_map': _get_level_map(),
    })


@app.route('/api/start-dungeon', methods=['POST'])
def start_dungeon():
    data = request.get_json()
    player_name = data.get('player_name', 'Wizard')

    account = _get_account(player_name)
    prev_score = account.get('score', 0) if account else 0

    session['game'] = {
        'mode': 'dungeon',
        'player_name': player_name,
        'floor': 1,
        'floor_problems_answered': 0,
        'floor_problems_correct': 0,
        'hp': 100,
        'max_hp': 100,
        'score': prev_score,
        'dungeon_score': 0,
        'streak': 0,
        'best_streak': 0,
        'problems_answered': 0,
        'problems_correct': 0,
        'current_problem': None,
        'problem_start_time': None,
        'in_boss_fight': False,
        'boss_hp': 0,
        'boss_max_hp': 0,
        'boss_name': '',
        'boss_enraged': False,
        'boss_special_active': None,
        'timers_off': False,
    }
    return jsonify({'status': 'ok', 'mode': 'dungeon'})


@app.route('/api/dungeon-floor', methods=['POST'])
def dungeon_start_floor():
    """Initialize current dungeon floor and get first problem."""
    game = session.get('game')
    if not game or game.get('mode') != 'dungeon':
        return jsonify({'error': 'No active dungeon'}), 404

    _dungeon_start_floor(game)

    problem = generate_dungeon_problem(game['floor'])
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()

    boss_special = None
    if game.get('in_boss_fight'):
        boss_special = get_dungeon_boss_special(game['floor'])
        game['boss_special_active'] = boss_special

    session.modified = True

    resp = {
        'floor': game['floor'],
        'is_boss': game.get('in_boss_fight', False),
        'problem': {
            'expression': problem['expression'],
            'problem_number': 1,
            'total_problems': DUNGEON_PROBLEMS_PER_FLOOR,
            'is_boss': game.get('in_boss_fight', False),
        },
        'game_state': _safe_state(),
    }
    if game.get('in_boss_fight'):
        boss = DUNGEON_BOSSES[game['floor']]
        resp['boss_info'] = {'name': boss['name'], 'hp': boss['hp']}
    if boss_special:
        resp['boss_special'] = boss_special
    return jsonify(resp)


@app.route('/api/start-gauntlet', methods=['POST'])
def start_gauntlet():
    data = request.get_json()
    player_name = data.get('player_name', 'Wizard')

    account = _get_account(player_name)
    prev_score = account.get('score', 0) if account else 0

    session['game'] = {
        'mode': 'gauntlet',
        'player_name': player_name,
        'hp': 1,
        'max_hp': 1,
        'score': prev_score,
        'gauntlet_score': 0,
        'streak': 0,
        'best_streak': 0,
        'problems_answered': 0,
        'problems_correct': 0,
        'current_problem': None,
        'problem_start_time': None,
        'timers_off': False,
    }
    return jsonify({'status': 'ok', 'mode': 'gauntlet'})


@app.route('/api/gauntlet-start', methods=['POST'])
def gauntlet_start():
    """Get first problem for gauntlet."""
    game = session.get('game')
    if not game or game.get('mode') != 'gauntlet':
        return jsonify({'error': 'No active gauntlet'}), 404

    problem = generate_gauntlet_problem()
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()
    session.modified = True

    return jsonify({
        'problem': {
            'expression': problem['expression'],
            'problem_number': 1,
            'total_problems': 0,
            'is_boss': False,
        },
        'game_state': _safe_state(),
    })


@app.route('/api/state')
def get_state():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404
    mode = game.get('mode', 'quest')
    result = {'game_state': _safe_state()}
    if mode == 'quest':
        result['level_map'] = _get_level_map()
    return jsonify(result)


@app.route('/api/start-level', methods=['POST'])
def start_level():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404

    data = request.get_json()
    level = data.get('level', game['current_level'])

    if level not in LEVEL_CONFIG[game['difficulty']]:
        return jsonify({'error': 'Invalid level'}), 400

    if not _is_level_unlocked(game, level):
        return jsonify({'error': 'Level locked'}), 403

    game['current_level'] = level
    game['hp'] = 100
    game['problems_answered'] = 0
    game['problems_correct'] = 0
    game['level_score'] = 0
    game['streak'] = 0
    game['fast_streak'] = 0
    game['heals_this_level'] = 0
    game['charge_meter'] = 0

    boss_level = is_boss_level(game['difficulty'], level)
    game['in_boss_fight'] = boss_level
    if boss_level:
        game['boss_hp'] = BOSS_HP[game['difficulty']]
        game['boss_max_hp'] = BOSS_HP[game['difficulty']]
    else:
        game['boss_hp'] = 0
        game['boss_max_hp'] = 0

    problem = generate_problem(game['difficulty'], level)
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()
    session.modified = True

    level_info = get_level_info(game['difficulty'], level)

    # Generate an example problem for preview
    example = generate_problem(game['difficulty'], level)

    return jsonify({
        'level_info': level_info,
        'problem': _problem_response(problem, game, level_info),
        'example_problem': example['expression'],
        'game_state': _safe_state(),
    })


@app.route('/api/problem')
def get_problem():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404

    mode = game.get('mode', 'quest')

    if mode == 'dungeon':
        return _dungeon_get_problem(game)
    elif mode == 'gauntlet':
        return _gauntlet_get_problem(game)

    # Quest mode
    level_config = LEVEL_CONFIG[game['difficulty']][game['current_level']]

    if not game.get('in_boss_fight'):
        if game['problems_answered'] >= level_config['num_problems']:
            return jsonify({'error': 'Level complete'}), 400

    problem = generate_problem(game['difficulty'], game['current_level'])
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()
    session.modified = True

    level_info = get_level_info(game['difficulty'], game['current_level'])

    return jsonify({
        'problem': _problem_response(problem, game, level_info),
        'game_state': _safe_state(),
    })


@app.route('/api/answer', methods=['POST'])
def submit_answer():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404

    if game.get('current_problem') is None:
        return jsonify({'error': 'No active problem'}), 400

    mode = game.get('mode', 'quest')
    if mode == 'dungeon':
        return _dungeon_answer(game)
    elif mode == 'gauntlet':
        return _gauntlet_answer(game)

    data = request.get_json()
    timed_out = data.get('timed_out', False)

    # If timers are off, timed_out should never be sent, but handle gracefully
    if game.get('timers_off') and timed_out:
        timed_out = False

    if timed_out:
        correct = False
        player_answer = None
    else:
        try:
            player_answer = int(data.get('answer', ''))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid answer'}), 400

    correct_answer = game['current_problem']
    if not timed_out:
        correct = (player_answer == correct_answer)
    time_taken = time.time() - (game['problem_start_time'] or time.time())

    game['problems_answered'] += 1
    points_earned = 0
    speed_bonus = False
    streak_mult = 1.0

    is_fast = time_taken < FAST_THRESHOLD
    is_slow = time_taken > SLOW_THRESHOLD
    is_very_slow = time_taken > FAIL_THRESHOLD
    healed = 0
    boss_damage_dealt = 0
    boss_attack_damage = 0
    boss_enraged = False
    power_strike = False
    power_strike_damage = 0

    in_boss = game.get('in_boss_fight', False)

    if in_boss:
        boss_enraged = game['boss_hp'] <= game['boss_max_hp'] // 2

    if correct:
        game['problems_correct'] += 1
        game['streak'] += 1
        game['best_streak'] = max(game['best_streak'], game['streak'])
        points_earned, speed_bonus, streak_mult = calculate_score(
            game['difficulty'], time_taken, game['streak']
        )
        # Slow penalty: 20% less points
        if is_slow:
            points_earned = int(points_earned * 0.8)
        # Timers-off mode: 0 points after 30s
        if game.get('timers_off') and is_very_slow:
            points_earned = 0
        game['score'] += points_earned
        game['level_score'] += points_earned

        if is_fast:
            game['total_fast_answers'] = game.get('total_fast_answers', 0) + 1
            game['fast_streak'] = game.get('fast_streak', 0) + 1
        else:
            game['fast_streak'] = 0

        if game['fast_streak'] >= 3:
            healed = 15
            game['hp'] = min(game['max_hp'], game['hp'] + healed)
            game['fast_streak'] = 0
            game['heals_this_level'] = game.get('heals_this_level', 0) + 1

        if in_boss:
            boss_damage_dealt = calculate_boss_damage(points_earned)

            game['charge_meter'] = game.get('charge_meter', 0) + 1
            if game['charge_meter'] >= 5:
                power_strike = True
                power_strike_damage = DAMAGE[game['difficulty']] * 3
                boss_damage_dealt += power_strike_damage
                game['charge_meter'] = 0

            game['boss_hp'] = max(0, game['boss_hp'] - boss_damage_dealt)

            if not is_fast:
                if boss_enraged:
                    boss_attack_damage = DAMAGE[game['difficulty']]
                    game['hp'] = max(0, game['hp'] - boss_attack_damage)
                elif is_slow:
                    boss_attack_damage = DAMAGE[game['difficulty']]
                    game['hp'] = max(0, game['hp'] - boss_attack_damage)
    else:
        game['streak'] = 0
        game['fast_streak'] = 0
        if in_boss:
            game['charge_meter'] = 0
        damage = DAMAGE[game['difficulty']]
        if in_boss:
            boss_attack_damage = damage * 2
            game['hp'] = max(0, game['hp'] - boss_attack_damage)
        else:
            game['hp'] = max(0, game['hp'] - damage)

    game['current_problem'] = None
    game['problem_start_time'] = None

    level_config = LEVEL_CONFIG[game['difficulty']][game['current_level']]
    in_boss = game.get('in_boss_fight', False)

    if in_boss:
        boss_defeated = game['boss_hp'] <= 0
        level_complete = boss_defeated and game['hp'] > 0
        game_over = game['hp'] <= 0
    else:
        boss_defeated = False
        level_complete = game['problems_answered'] >= level_config['num_problems'] and game['hp'] > 0
        game_over = game['hp'] <= 0

    completion_bonus = 0
    stars = 0
    level_complete_message = ''
    new_achievements = []

    if level_complete:
        completion_bonus = get_completion_bonus(game['difficulty'], game['hp'])
        game['score'] += completion_bonus
        game['level_score'] += completion_bonus
        stars = get_star_rating(game['hp'])
        level_key = f"{game['difficulty']}_{game['current_level']}"
        prev_stars = game['completed_levels'].get(level_key, 0)
        game['completed_levels'][level_key] = max(prev_stars, stars)

        if boss_defeated:
            game['bosses_defeated'] = game.get('bosses_defeated', 0) + 1
            game['_defeated_boss'] = game['difficulty']
            level_complete_message = get_boss_defeat_message()
        else:
            level_complete_message = get_level_complete_message(game['hp'])

        game['_just_completed'] = True
        new_achievements = check_achievements(game)
        game['_just_completed'] = False
        game.pop('_defeated_boss', None)
        for ach in new_achievements:
            if ach not in game.get('achievements', []):
                game.setdefault('achievements', []).append(ach)

        # Persist to account
        _persist_game_to_account(game)

    if game_over:
        _persist_game_to_account(game)

    feedback = get_feedback_message(correct, speed_bonus, game['streak'])

    session.modified = True

    return jsonify({
        'correct': correct,
        'correct_answer': correct_answer,
        'points_earned': points_earned,
        'completion_bonus': completion_bonus,
        'speed_bonus': speed_bonus,
        'slow_penalty': is_slow and correct,
        'streak_multiplier': streak_mult,
        'feedback_message': feedback,
        'level_complete': level_complete,
        'level_complete_message': level_complete_message,
        'stars': stars,
        'game_over': game_over,
        'damage': boss_attack_damage if in_boss else (DAMAGE[game['difficulty']] if not correct else 0),
        'healed': healed,
        'boss_damage_dealt': boss_damage_dealt,
        'boss_defeated': boss_defeated if in_boss else False,
        'boss_enraged': boss_enraged,
        'boss_attack_damage': boss_attack_damage,
        'power_strike': power_strike,
        'power_strike_damage': power_strike_damage,
        'charge_meter': game.get('charge_meter', 0),
        'timed_out': timed_out,
        'new_achievements': [
            {'id': a, **ACHIEVEMENTS[a]} for a in new_achievements
        ],
        'game_state': _safe_state(),
    })


@app.route('/api/restart-level', methods=['POST'])
def restart_level():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404

    game['hp'] = 100
    game['problems_answered'] = 0
    game['problems_correct'] = 0
    game['level_score'] = 0
    game['streak'] = 0
    game['fast_streak'] = 0
    game['heals_this_level'] = 0
    game['charge_meter'] = 0

    boss_level = is_boss_level(game['difficulty'], game['current_level'])
    game['in_boss_fight'] = boss_level
    if boss_level:
        game['boss_hp'] = BOSS_HP[game['difficulty']]
        game['boss_max_hp'] = BOSS_HP[game['difficulty']]

    problem = generate_problem(game['difficulty'], game['current_level'])
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()

    level_info = get_level_info(game['difficulty'], game['current_level'])
    session.modified = True

    return jsonify({
        'level_info': level_info,
        'problem': _problem_response(problem, game, level_info),
        'game_state': _safe_state(),
    })


@app.route('/api/level-map')
def level_map():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404
    return jsonify({'level_map': _get_level_map()})


@app.route('/api/achievements')
def achievements():
    game = session.get('game')
    if not game:
        return jsonify({'error': 'No active game'}), 404
    earned = game.get('achievements', [])
    result = []
    for aid, adata in ACHIEVEMENTS.items():
        result.append({
            'id': aid,
            'earned': aid in earned,
            **adata,
        })
    return jsonify({'achievements': result})


# --- Dungeon Mode Helpers ---

def _dungeon_start_floor(game):
    """Set up the current dungeon floor."""
    floor = game['floor']
    game['floor_problems_answered'] = 0
    game['floor_problems_correct'] = 0

    if is_dungeon_boss_floor(floor):
        boss = DUNGEON_BOSSES[floor]
        game['in_boss_fight'] = True
        game['boss_hp'] = boss['hp']
        game['boss_max_hp'] = boss['hp']
        game['boss_name'] = boss['name']
        game['boss_enraged'] = False
        game['boss_special_active'] = None
    else:
        game['in_boss_fight'] = False
        game['boss_hp'] = 0
        game['boss_max_hp'] = 0
        game['boss_name'] = ''
        game['boss_special_active'] = None


def _dungeon_get_problem(game):
    floor = game['floor']
    problem = generate_dungeon_problem(floor)
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()

    boss_special = None
    if game.get('in_boss_fight'):
        boss_special = get_dungeon_boss_special(floor)
        game['boss_special_active'] = boss_special

    session.modified = True
    resp = {
        'problem': {
            'expression': problem['expression'],
            'problem_number': game['floor_problems_answered'] + 1,
            'total_problems': DUNGEON_PROBLEMS_PER_FLOOR,
            'is_boss': game.get('in_boss_fight', False),
        },
        'game_state': _safe_state(),
    }
    if boss_special:
        resp['boss_special'] = boss_special
    return jsonify(resp)


def _dungeon_answer(game):
    data = request.get_json()
    timed_out = data.get('timed_out', False)

    if timed_out:
        correct = False
        player_answer = None
    else:
        try:
            player_answer = int(data.get('answer', ''))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid answer'}), 400

    correct_answer = game['current_problem']
    if not timed_out:
        correct = (player_answer == correct_answer)

    time_taken = time.time() - (game['problem_start_time'] or time.time())
    game['problems_answered'] += 1
    game['floor_problems_answered'] += 1

    is_fast = time_taken < FAST_THRESHOLD
    is_slow = time_taken > SLOW_THRESHOLD

    points_earned = 0
    speed_bonus = False
    streak_mult = 1.0
    boss_damage_dealt = 0
    boss_attack_damage = 0
    boss_special = game.get('boss_special_active')
    in_boss = game.get('in_boss_fight', False)
    boss_enraged = False

    if in_boss:
        boss_enraged = game['boss_hp'] <= game['boss_max_hp'] // 2

    # Determine effective difficulty tier for scoring
    floor = game['floor']
    if floor <= 10:
        score_diff = 'easy'
    elif floor <= 20:
        score_diff = 'medium'
    else:
        score_diff = 'hard'

    if correct:
        game['problems_correct'] += 1
        game['floor_problems_correct'] += 1
        game['streak'] += 1
        game['best_streak'] = max(game['best_streak'], game['streak'])
        points_earned, speed_bonus, streak_mult = calculate_score(score_diff, time_taken, game['streak'])
        if is_slow:
            points_earned = int(points_earned * 0.8)
        game['dungeon_score'] = game.get('dungeon_score', 0) + points_earned
        game['score'] += points_earned

        if in_boss:
            boss_damage_dealt = calculate_boss_damage(points_earned)
            game['boss_hp'] = max(0, game['boss_hp'] - boss_damage_dealt)

            # Boss retaliation (enraged: damage on non-fast; else: damage on slow)
            if not is_fast:
                if boss_enraged:
                    boss_attack_damage = DUNGEON_DAMAGE
                    game['hp'] = max(0, game['hp'] - boss_attack_damage)
                elif is_slow:
                    boss_attack_damage = DUNGEON_DAMAGE
                    game['hp'] = max(0, game['hp'] - boss_attack_damage)
    else:
        game['streak'] = 0
        # Ogre special: instant kill on miss
        if boss_special == 'ogre_instakill':
            game['hp'] = 0
        elif in_boss:
            boss_attack_damage = DUNGEON_DAMAGE * 2
            game['hp'] = max(0, game['hp'] - boss_attack_damage)
        else:
            game['hp'] = max(0, game['hp'] - DUNGEON_DAMAGE)

    game['current_problem'] = None
    game['problem_start_time'] = None
    game['boss_special_active'] = None

    game_over = game['hp'] <= 0
    boss_defeated = in_boss and game['boss_hp'] <= 0 and not game_over
    floor_complete = False
    dungeon_complete = False

    if boss_defeated:
        floor_complete = True
        if game['floor'] >= DUNGEON_FLOORS:
            dungeon_complete = True
    elif not in_boss and not game_over:
        if game['floor_problems_answered'] >= DUNGEON_PROBLEMS_PER_FLOOR:
            floor_complete = True

    next_floor = game['floor'] + 1 if floor_complete and not dungeon_complete else game['floor']

    if floor_complete and not dungeon_complete:
        game['floor'] = next_floor
        _dungeon_start_floor(game)

    session.modified = True

    feedback = get_feedback_message(correct, speed_bonus, game['streak'])

    return jsonify({
        'correct': correct,
        'correct_answer': correct_answer,
        'points_earned': points_earned,
        'speed_bonus': speed_bonus,
        'slow_penalty': is_slow and correct,
        'streak_multiplier': streak_mult,
        'feedback_message': feedback,
        'damage': boss_attack_damage if in_boss else (DUNGEON_DAMAGE if not correct else 0),
        'boss_damage_dealt': boss_damage_dealt,
        'boss_defeated': boss_defeated,
        'boss_enraged': boss_enraged,
        'boss_attack_damage': boss_attack_damage,
        'boss_special': boss_special,
        'floor_complete': floor_complete,
        'dungeon_complete': dungeon_complete,
        'game_over': game_over,
        'timed_out': timed_out,
        'game_state': _safe_state(),
    })


# --- Gauntlet Mode Helpers ---

def _gauntlet_get_problem(game):
    problem = generate_gauntlet_problem()
    game['current_problem'] = problem['answer']
    game['problem_start_time'] = time.time()
    session.modified = True
    return jsonify({
        'problem': {
            'expression': problem['expression'],
            'problem_number': game['problems_correct'] + 1,
            'total_problems': 0,
            'is_boss': False,
        },
        'game_state': _safe_state(),
    })


def _gauntlet_answer(game):
    data = request.get_json()
    timed_out = data.get('timed_out', False)

    if timed_out:
        correct = False
        player_answer = None
    else:
        try:
            player_answer = int(data.get('answer', ''))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid answer'}), 400

    correct_answer = game['current_problem']
    if not timed_out:
        correct = (player_answer == correct_answer)

    time_taken = time.time() - (game['problem_start_time'] or time.time())
    game['problems_answered'] += 1

    is_fast = time_taken < GAUNTLET_FAST_THRESHOLD
    is_slow = time_taken > GAUNTLET_SLOW_THRESHOLD

    points_earned = 0
    speed_bonus = False
    streak_mult = 1.0

    if correct:
        game['problems_correct'] += 1
        game['streak'] += 1
        game['best_streak'] = max(game['best_streak'], game['streak'])
        points_earned, speed_bonus, streak_mult = calculate_score('expert', time_taken, game['streak'])
        if is_slow:
            points_earned = int(points_earned * 0.8)
        game['gauntlet_score'] = game.get('gauntlet_score', 0) + points_earned
        game['score'] += points_earned
    else:
        game['streak'] = 0

    game['current_problem'] = None
    game['problem_start_time'] = None

    # One wrong/timeout = death
    game_over = not correct

    session.modified = True

    feedback = get_feedback_message(correct, speed_bonus, game['streak'])

    return jsonify({
        'correct': correct,
        'correct_answer': correct_answer,
        'points_earned': points_earned,
        'speed_bonus': speed_bonus,
        'slow_penalty': is_slow and correct,
        'streak_multiplier': streak_mult,
        'feedback_message': feedback,
        'damage': 1 if not correct else 0,
        'game_over': game_over,
        'timed_out': timed_out,
        'game_state': _safe_state(),
    })


def _problem_response(problem, game, level_info):
    if game.get('in_boss_fight'):
        return {
            'expression': problem['expression'],
            'problem_number': game['problems_answered'] + 1,
            'total_problems': 0,
            'is_boss': True,
        }
    return {
        'expression': problem['expression'],
        'problem_number': game['problems_answered'] + 1,
        'total_problems': level_info['num_problems'],
        'is_boss': False,
    }


def _safe_state():
    game = session.get('game', {})
    mode = game.get('mode', 'quest')
    state = {
        'mode': mode,
        'player_name': game.get('player_name', ''),
        'hp': game.get('hp', 100),
        'max_hp': game.get('max_hp', 100),
        'score': game.get('score', 0),
        'streak': game.get('streak', 0),
        'best_streak': game.get('best_streak', 0),
        'problems_answered': game.get('problems_answered', 0),
        'problems_correct': game.get('problems_correct', 0),
        'timers_off': game.get('timers_off', False),
    }

    if mode == 'quest':
        state['difficulty'] = game.get('difficulty', '')
        state['current_level'] = game.get('current_level', 1)
        state['level_score'] = game.get('level_score', 0)
        state['realm'] = REALM_NAMES.get(game.get('difficulty', ''), '')
        state['in_boss_fight'] = game.get('in_boss_fight', False)
        state['boss_hp'] = game.get('boss_hp', 0)
        state['boss_max_hp'] = game.get('boss_max_hp', 0)
        state['charge_meter'] = game.get('charge_meter', 0)
        if game.get('in_boss_fight'):
            state['boss_name'] = BOSS_NAMES.get(game.get('difficulty', ''), '')
            state['boss_enraged'] = game.get('boss_hp', 0) <= game.get('boss_max_hp', 0) // 2

    elif mode == 'dungeon':
        state['floor'] = game.get('floor', 1)
        state['dungeon_score'] = game.get('dungeon_score', 0)
        state['floor_problems_answered'] = game.get('floor_problems_answered', 0)
        state['in_boss_fight'] = game.get('in_boss_fight', False)
        state['boss_hp'] = game.get('boss_hp', 0)
        state['boss_max_hp'] = game.get('boss_max_hp', 0)
        state['boss_name'] = game.get('boss_name', '')
        state['boss_enraged'] = game.get('boss_hp', 0) <= game.get('boss_max_hp', 0) // 2 if game.get('in_boss_fight') else False

    elif mode == 'gauntlet':
        state['gauntlet_score'] = game.get('gauntlet_score', 0)
        state['gauntlet_timer'] = {
            'fast': GAUNTLET_FAST_THRESHOLD,
            'slow': GAUNTLET_SLOW_THRESHOLD,
            'fail': GAUNTLET_FAIL_THRESHOLD,
        }

    return state


def _get_level_map():
    game = session.get('game', {})
    difficulty = game.get('difficulty', 'easy')
    levels = []
    for lvl in range(1, 6):
        level_key = f"{difficulty}_{lvl}"
        stars = game.get('completed_levels', {}).get(level_key, 0)
        unlocked = _is_level_unlocked(game, lvl)
        is_boss = is_boss_level(difficulty, lvl)
        levels.append({
            'level': lvl,
            'name': LEVEL_NAMES.get(difficulty, {}).get(lvl, f'Level {lvl}'),
            'stars': stars,
            'unlocked': unlocked,
            'realm': REALM_NAMES.get(difficulty, ''),
            'is_boss': is_boss,
        })
    return levels


def _is_level_unlocked(game, level):
    if level == 1:
        return True
    prev_key = f"{game['difficulty']}_{level - 1}"
    return game.get('completed_levels', {}).get(prev_key, 0) > 0


def _get_realm_status(completed, difficulty):
    if difficulty == 'easy':
        return 'open'
    if difficulty == 'medium':
        easy_done = all(completed.get(f'easy_{i}', 0) > 0 for i in range(1, 6))
        return 'open' if easy_done else 'warning'
    if difficulty == 'hard':
        medium_done = all(completed.get(f'medium_{i}', 0) > 0 for i in range(1, 6))
        return 'open' if medium_done else 'locked'
    if difficulty == 'expert':
        hard_done = all(completed.get(f'hard_{i}', 0) > 0 for i in range(1, 6))
        return 'open' if hard_done else 'locked'
    return 'locked'


if __name__ == '__main__':
    app.run(debug=True, port=5050)
