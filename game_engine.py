import random
import time

REALM_NAMES = {
    'easy': 'The Enchanted Forest',
    'medium': 'The Crystal Caverns',
    'hard': 'The Frozen Mountains',
    'expert': "The Dragon's Keep",
}

LEVEL_NAMES = {
    'easy': {
        1: 'First Steps',
        2: 'Forest Path',
        3: 'Mossy Bridge',
        4: 'Triple Threat',
        5: 'Forest Guardian',
    },
    'medium': {
        1: 'Into the Dark',
        2: 'Crossroads',
        3: 'Crystal Chamber',
        4: 'Two Steps Deep',
        5: 'Cavern Boss',
    },
    'hard': {
        1: 'Times Table Peak',
        2: 'Avalanche Alley',
        3: 'The Great Divide',
        4: 'Four Winds',
        5: 'Mountain Summit',
    },
    'expert': {
        1: 'Order of Power',
        2: 'Dragon Math',
        3: 'Triple Flame',
        4: 'Arcane Parentheses',
        5: 'The Final Boss',
    },
}

BOSS_NAMES = {
    'easy': 'Thornback the Treant',
    'medium': 'Crystalis the Golem',
    'hard': 'Frostfang the Yeti',
    'expert': 'Infernus the Dragon',
}

BOSS_HP = {
    'easy': 80,
    'medium': 120,
    'hard': 160,
    'expert': 200,
}

LEVEL_CONFIG = {
    'easy': {
        1: {'num_problems': 6, 'operations': ['+'], 'operand_range': (1, 9), 'steps': 1},
        2: {'num_problems': 7, 'operations': ['+'], 'operand_range': (1, 15), 'steps': 1},
        3: {'num_problems': 7, 'operations': ['+'], 'operand_range': (5, 20), 'steps': 1},
        4: {'num_problems': 8, 'operations': ['+'], 'operand_range': (10, 20), 'steps': 1, 'three_addends_chance': 0.4},
        5: {'num_problems': 0, 'operations': ['+'], 'operand_range': (1, 20), 'steps': 1, 'boss': True, 'three_addends_chance': 0.3},
    },
    'medium': {
        1: {'num_problems': 7, 'operations': ['-'], 'operand_range': (1, 20), 'steps': 1},
        2: {'num_problems': 8, 'operations': ['+', '-'], 'operand_range': (1, 30), 'steps': 1},
        3: {'num_problems': 8, 'operations': ['+', '-'], 'operand_range': (10, 50), 'steps': 1},
        4: {'num_problems': 8, 'operations': ['+', '-'], 'operand_range': (5, 30), 'steps': 2},
        5: {'num_problems': 0, 'operations': ['+', '-'], 'operand_range': (5, 50), 'steps': 2, 'boss': True},
    },
    'hard': {
        1: {'num_problems': 8, 'operations': ['*'], 'operand_range': (1, 9), 'steps': 1},
        2: {'num_problems': 8, 'operations': ['*'], 'operand_range': (2, 12), 'steps': 1},
        3: {'num_problems': 8, 'operations': ['/'], 'operand_range': (2, 9), 'steps': 1},
        4: {'num_problems': 10, 'operations': ['+', '-', '*', '/'], 'operand_range': (2, 12), 'steps': 1},
        5: {'num_problems': 0, 'operations': ['+', '-', '*', '/'], 'operand_range': (2, 15), 'steps': 2, 'boss': True},
    },
    'expert': {
        1: {'num_problems': 8, 'operations': ['+', '-', '*'], 'operand_range': (2, 15), 'steps': 2},
        2: {'num_problems': 10, 'operations': ['*', '/'], 'operand_range': (3, 15), 'steps': 1, 'large_mult': True},
        3: {'num_problems': 10, 'operations': ['+', '-', '*', '/'], 'operand_range': (2, 12), 'steps': 3},
        4: {'num_problems': 10, 'operations': ['+', '-', '*'], 'operand_range': (2, 15), 'steps': 2, 'parentheses': True},
        5: {'num_problems': 0, 'operations': ['+', '-', '*', '/'], 'operand_range': (2, 15), 'steps': 3, 'parentheses': True, 'boss': True},
    },
}

DAMAGE = {
    'easy': 15,
    'medium': 20,
    'hard': 25,
    'expert': 30,
}

BASE_POINTS = {
    'easy': 10,
    'medium': 25,
    'hard': 50,
    'expert': 100,
}

# Timer thresholds (seconds)
FAST_THRESHOLD = 5
SLOW_THRESHOLD = 15
FAIL_THRESHOLD = 30

CORRECT_MESSAGES = [
    "Correct!", "Well done!", "Brilliant!", "Nailed it!", "Superb!",
    "Math wizard!", "Excellent!", "Keep it up!", "Awesome!", "Perfect!",
]

CORRECT_FAST_MESSAGES = [
    "Lightning fast!", "Speed demon!", "Turbo brain!", "Blazing!",
    "Quick draw!", "Incredible speed!",
]

CORRECT_STREAK_MESSAGES = [
    "Unstoppable!", "On a roll!", "Can't be stopped!",
    "Dominating!", "Legendary streak!",
]

WRONG_MESSAGES = [
    "Not quite!", "Almost!", "Keep trying!", "You've got this!",
    "Don't give up!", "Stay strong!",
]

LEVEL_COMPLETE_MESSAGES = [
    "Level cleared!", "Onward, brave wizard!", "Victory is yours!",
    "The realm trembles before you!",
]

PERFECT_MESSAGES = [
    "FLAWLESS! Not a scratch!", "Perfect! Untouchable!",
    "The wizard is unbeatable!", "Absolute legend!",
]

BOSS_DEFEAT_MESSAGES = [
    "The beast has fallen!", "Victory over the guardian!",
    "The realm is yours!", "A legendary triumph!",
]

DISPLAY_OPS = {'+': '+', '-': '-', '*': '\u00d7', '/': '\u00f7'}

# --- Dungeon Mode ---

DUNGEON_FLOORS = 30
DUNGEON_PROBLEMS_PER_FLOOR = 4
DUNGEON_DAMAGE = 10  # flat -10 HP per wrong/timeout

DUNGEON_BOSSES = {
    10: {'name': 'Grokk the Ogre', 'hp': 120, 'special': 'ogre_instakill'},
    20: {'name': 'Xalthar the Beholder', 'hp': 180, 'special': 'beholder_float'},
    30: {'name': 'Zerathul the Mindflayer', 'hp': 250, 'special': 'mindflayer_vanish'},
}

# --- Gauntlet Mode ---

GAUNTLET_FAST_THRESHOLD = 5
GAUNTLET_SLOW_THRESHOLD = 10
GAUNTLET_FAIL_THRESHOLD = 15

# --- Achievements ---

ACHIEVEMENTS = {
    'speed_demon': {
        'name': 'Speed Demon',
        'description': 'Answer 10 problems in under 3 seconds each',
        'icon': '\u26A1',
    },
    'perfectionist': {
        'name': 'Perfectionist',
        'description': 'Get 3 stars on every level in a realm',
        'icon': '\u2B50',
    },
    'survivor': {
        'name': 'Survivor',
        'description': 'Complete a level with only 5 HP remaining',
        'icon': '\U0001F9E1',
    },
    'streak_master': {
        'name': 'Streak Master',
        'description': 'Reach a streak of 10 in a single level',
        'icon': '\U0001F525',
    },
    'boss_slayer': {
        'name': 'Boss Slayer',
        'description': 'Defeat your first boss',
        'icon': '\u2694\uFE0F',
    },
    'dragon_slayer': {
        'name': 'Dragon Slayer',
        'description': 'Defeat Infernus the Dragon',
        'icon': '\U0001F409',
    },
    'healer': {
        'name': 'Natural Healer',
        'description': 'Heal yourself 3 times in a single level',
        'icon': '\U0001F33F',
    },
    'realm_conqueror': {
        'name': 'Realm Conqueror',
        'description': 'Complete all 5 levels of any realm',
        'icon': '\U0001F451',
    },
}


def generate_problem(difficulty, level):
    config = LEVEL_CONFIG[difficulty][level]
    steps = config['steps']
    ops = config['operations']
    lo, hi = config['operand_range']

    if config.get('parentheses') and steps >= 2:
        return _generate_parentheses_problem(ops, lo, hi, steps)

    if config.get('three_addends_chance') and random.random() < config['three_addends_chance']:
        return _generate_three_addend(lo, hi)

    if config.get('large_mult'):
        return _generate_large_mult(ops, lo, hi)

    if steps == 1:
        return _generate_single_step(ops, lo, hi)
    else:
        return _generate_multi_step(ops, lo, hi, steps)


def _generate_single_step(ops, lo, hi):
    op = random.choice(ops)
    if op == '/':
        return _generate_division(lo, hi)

    a = random.randint(lo, hi)
    b = random.randint(lo, hi)

    if op == '-':
        a, b = max(a, b), min(a, b)

    answer = _eval_op(a, op, b)
    expression = f"{a} {DISPLAY_OPS[op]} {b}"
    return {'expression': expression, 'answer': answer}


def _generate_division(lo, hi):
    divisor = random.randint(max(2, lo), min(12, hi))
    answer = random.randint(max(1, lo), hi)
    dividend = answer * divisor
    expression = f"{dividend} {DISPLAY_OPS['/']} {divisor}"
    return {'expression': expression, 'answer': answer}


def _generate_three_addend(lo, hi):
    a = random.randint(lo, hi)
    b = random.randint(lo, hi)
    c = random.randint(lo, hi)
    answer = a + b + c
    expression = f"{a} + {b} + {c}"
    return {'expression': expression, 'answer': answer}


def _generate_large_mult(ops, lo, hi):
    op = random.choice(ops)
    if op == '/':
        divisor = random.randint(3, 12)
        answer = random.randint(lo, hi)
        dividend = answer * divisor
        expression = f"{dividend} {DISPLAY_OPS['/']} {divisor}"
        return {'expression': expression, 'answer': answer}
    else:
        a = random.randint(lo, hi)
        b = random.randint(lo, hi)
        answer = a * b
        expression = f"{a} {DISPLAY_OPS['*']} {b}"
        return {'expression': expression, 'answer': answer}


def _generate_multi_step(ops, lo, hi, steps):
    for _ in range(50):
        parts_display = []
        parts_eval = []
        a = random.randint(lo, hi)
        parts_display.append(str(a))
        parts_eval.append(str(a))

        for _ in range(steps):
            op = random.choice(ops)
            b = random.randint(lo, hi)

            if op == '/':
                b = random.randint(2, min(9, hi))
                current_val = eval(' '.join(parts_eval))
                if current_val <= 0:
                    b = random.randint(lo, hi)
                    op = '+'
                else:
                    remainder = current_val % b
                    if remainder != 0:
                        adjust = random.choice([-1, 1]) * remainder
                        parts_eval[-1] = str(int(parts_eval[-1]) + adjust)
                        parts_display[-1] = parts_eval[-1]

            parts_display.append(DISPLAY_OPS[op])
            parts_display.append(str(b))
            parts_eval.append(op)
            parts_eval.append(str(b))

        answer = eval(' '.join(parts_eval))
        if answer == int(answer) and answer >= 0:
            expression = ' '.join(parts_display)
            return {'expression': expression, 'answer': int(answer)}

    return _generate_single_step(ops, lo, hi)


def _generate_parentheses_problem(ops, lo, hi, steps):
    for _ in range(50):
        if steps >= 3:
            a, b, c, d = [random.randint(lo, hi) for _ in range(4)]
            op1 = random.choice(['+', '-'])
            op2 = random.choice(['*'])
            op3 = random.choice(['+', '-'])
            template = random.choice(['(a op1 b) op2 c op3 d', 'a op2 (b op1 c) op3 d'])
        else:
            a, b, c = [random.randint(lo, hi) for _ in range(3)]
            op1 = random.choice(['+', '-'])
            op2 = random.choice(['*'])
            template = random.choice(['(a op1 b) op2 c', 'a op2 (b op1 c)'])

        if template == '(a op1 b) op2 c':
            expr_eval = f"({a}{op1}{b}){op2}{c}"
            expr_display = f"({a} {DISPLAY_OPS[op1]} {b}) {DISPLAY_OPS[op2]} {c}"
        elif template == 'a op2 (b op1 c)':
            expr_eval = f"{a}{op2}({b}{op1}{c})"
            expr_display = f"{a} {DISPLAY_OPS[op2]} ({b} {DISPLAY_OPS[op1]} {c})"
        elif template == '(a op1 b) op2 c op3 d':
            expr_eval = f"({a}{op1}{b}){op2}{c}{op3}{d}"
            expr_display = f"({a} {DISPLAY_OPS[op1]} {b}) {DISPLAY_OPS[op2]} {c} {DISPLAY_OPS[op3]} {d}"
        else:
            expr_eval = f"{a}{op2}({b}{op1}{c}){op3}{d}"
            expr_display = f"{a} {DISPLAY_OPS[op2]} ({b} {DISPLAY_OPS[op1]} {c}) {DISPLAY_OPS[op3]} {d}"

        answer = eval(expr_eval)
        if answer == int(answer) and answer >= 0:
            return {'expression': expr_display, 'answer': int(answer)}

    return _generate_multi_step(ops, lo, hi, 2)


def _eval_op(a, op, b):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        return a // b


def calculate_score(difficulty, time_taken, streak):
    base = BASE_POINTS[difficulty]

    if time_taken < 3:
        speed_bonus = 1.0
    elif time_taken < 5:
        speed_bonus = 0.5
    elif time_taken < 8:
        speed_bonus = 0.25
    else:
        speed_bonus = 0.0

    if streak >= 10:
        streak_mult = 3.0
    elif streak >= 8:
        streak_mult = 2.5
    elif streak >= 5:
        streak_mult = 2.0
    elif streak >= 3:
        streak_mult = 1.5
    else:
        streak_mult = 1.0

    points = int(base * (1 + speed_bonus) * streak_mult)
    return points, speed_bonus > 0, streak_mult


def get_completion_bonus(difficulty, hp):
    base_bonus = BASE_POINTS[difficulty] * 10
    if hp >= 100:
        return base_bonus * 2
    elif hp >= 50:
        return base_bonus
    else:
        return base_bonus // 2


def get_star_rating(hp):
    if hp >= 100:
        return 3
    elif hp > 50:
        return 2
    else:
        return 1


def get_feedback_message(correct, speed_bonus, streak):
    if not correct:
        return random.choice(WRONG_MESSAGES)
    if streak >= 5:
        return random.choice(CORRECT_STREAK_MESSAGES)
    if speed_bonus:
        return random.choice(CORRECT_FAST_MESSAGES)
    return random.choice(CORRECT_MESSAGES)


def get_level_complete_message(hp):
    if hp >= 100:
        return random.choice(PERFECT_MESSAGES)
    return random.choice(LEVEL_COMPLETE_MESSAGES)


def get_boss_defeat_message():
    return random.choice(BOSS_DEFEAT_MESSAGES)


def is_boss_level(difficulty, level):
    return LEVEL_CONFIG[difficulty][level].get('boss', False)


def get_boss_info(difficulty):
    return {
        'name': BOSS_NAMES[difficulty],
        'max_hp': BOSS_HP[difficulty],
        'hp': BOSS_HP[difficulty],
    }


def calculate_boss_damage(points_earned):
    """How much damage a correct answer deals to the boss."""
    return max(5, points_earned // 2)


def get_level_info(difficulty, level):
    config = LEVEL_CONFIG[difficulty][level]
    info = {
        'level': level,
        'difficulty': difficulty,
        'realm': REALM_NAMES[difficulty],
        'name': LEVEL_NAMES[difficulty][level],
        'num_problems': config['num_problems'],
        'is_boss': config.get('boss', False),
    }
    if config.get('boss'):
        info['boss'] = get_boss_info(difficulty)
    return info


def get_dungeon_floor_config(floor):
    """Return problem config based on dungeon floor tier."""
    if floor <= 10:
        # Tier 1: Addition + Subtraction
        if floor <= 3:
            return {'operations': ['+', '-'], 'operand_range': (1, 15), 'steps': 1}
        elif floor <= 7:
            return {'operations': ['+', '-'], 'operand_range': (5, 30), 'steps': 1}
        elif floor <= 9:
            return {'operations': ['+', '-'], 'operand_range': (10, 50), 'steps': 1}
        else:
            return {'operations': ['+', '-'], 'operand_range': (10, 50), 'steps': 1}
    elif floor <= 20:
        # Tier 2: All four operations
        if floor <= 13:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (2, 9), 'steps': 1}
        elif floor <= 17:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (2, 12), 'steps': 1}
        elif floor <= 19:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (3, 15), 'steps': 1}
        else:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (3, 15), 'steps': 2}
    else:
        # Tier 3: All four, tougher
        if floor <= 23:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (3, 15), 'steps': 2}
        elif floor <= 27:
            return {'operations': ['+', '-', '*', '/'], 'operand_range': (5, 20), 'steps': 2}
        elif floor <= 29:
            return {'operations': ['+', '-', '*'], 'operand_range': (2, 15), 'steps': 2, 'parentheses': True}
        else:
            return {'operations': ['+', '-', '*'], 'operand_range': (2, 15), 'steps': 3, 'parentheses': True}


def generate_dungeon_problem(floor):
    """Generate a problem appropriate for the given dungeon floor."""
    config = get_dungeon_floor_config(floor)
    ops = config['operations']
    lo, hi = config['operand_range']
    steps = config['steps']

    if config.get('parentheses') and steps >= 2:
        return _generate_parentheses_problem(ops, lo, hi, steps)
    if steps == 1:
        return _generate_single_step(ops, lo, hi)
    return _generate_multi_step(ops, lo, hi, steps)


def generate_gauntlet_problem():
    """Generate hardest-tier problems for survival gauntlet."""
    configs = [
        {'operations': ['+', '-', '*', '/'], 'operand_range': (2, 15), 'steps': 2},
        {'operations': ['+', '-', '*'], 'operand_range': (2, 15), 'steps': 2, 'parentheses': True},
        {'operations': ['+', '-', '*', '/'], 'operand_range': (3, 15), 'steps': 3},
        {'operations': ['*', '/'], 'operand_range': (3, 15), 'steps': 1, 'large_mult': True},
    ]
    config = random.choice(configs)
    ops = config['operations']
    lo, hi = config['operand_range']
    steps = config['steps']

    if config.get('parentheses') and steps >= 2:
        return _generate_parentheses_problem(ops, lo, hi, steps)
    if config.get('large_mult'):
        return _generate_large_mult(ops, lo, hi)
    if steps == 1:
        return _generate_single_step(ops, lo, hi)
    return _generate_multi_step(ops, lo, hi, steps)


def is_dungeon_boss_floor(floor):
    return floor in DUNGEON_BOSSES


def get_dungeon_boss_special(floor):
    """20% chance of boss special move per problem."""
    if floor not in DUNGEON_BOSSES:
        return None
    if random.random() < 0.2:
        return DUNGEON_BOSSES[floor]['special']
    return None


def check_achievements(game):
    """Check all achievements and return list of newly earned ones."""
    earned = game.get('achievements', [])
    new_achievements = []

    # Speed Demon: 10 fast answers total
    if 'speed_demon' not in earned and game.get('total_fast_answers', 0) >= 10:
        new_achievements.append('speed_demon')

    # Streak Master: streak of 10
    if 'streak_master' not in earned and game.get('best_streak', 0) >= 10:
        new_achievements.append('streak_master')

    # Survivor: complete level with 5 HP
    if 'survivor' not in earned and game.get('_just_completed', False) and game.get('hp', 100) <= 5:
        new_achievements.append('survivor')

    # Boss Slayer: defeat any boss
    if 'boss_slayer' not in earned and game.get('bosses_defeated', 0) >= 1:
        new_achievements.append('boss_slayer')

    # Dragon Slayer: defeat expert boss
    if 'dragon_slayer' not in earned and game.get('_defeated_boss', '') == 'expert':
        new_achievements.append('dragon_slayer')

    # Healer: heal 3 times in one level
    if 'healer' not in earned and game.get('heals_this_level', 0) >= 3:
        new_achievements.append('healer')

    # Realm Conqueror: all 5 levels of any realm
    if 'realm_conqueror' not in earned:
        completed = game.get('completed_levels', {})
        for diff in ['easy', 'medium', 'hard', 'expert']:
            all_done = all(completed.get(f'{diff}_{i}', 0) > 0 for i in range(1, 6))
            if all_done:
                new_achievements.append('realm_conqueror')
                break

    # Perfectionist: 3 stars on all levels of a realm
    if 'perfectionist' not in earned:
        completed = game.get('completed_levels', {})
        for diff in ['easy', 'medium', 'hard', 'expert']:
            all_three = all(completed.get(f'{diff}_{i}', 0) >= 3 for i in range(1, 6))
            if all_three:
                new_achievements.append('perfectionist')
                break

    return new_achievements
