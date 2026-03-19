// Game State Machine
const GameScreen = {
    MAP: 'screen-map',
    INTRO: 'screen-intro',
    PLAY: 'screen-play',
    COMPLETE: 'screen-complete',
    GAMEOVER: 'screen-gameover',
    DUNGEON_INTRO: 'screen-dungeon-intro',
    DUNGEON_COMPLETE: 'screen-dungeon-complete',
    DUNGEON_GAMEOVER: 'screen-dungeon-gameover',
    GAUNTLET_INTRO: 'screen-gauntlet-intro',
    GAUNTLET_GAMEOVER: 'screen-gauntlet-gameover',
};

// Timer thresholds (must match server)
const FAST_THRESHOLD = 5;
const SLOW_THRESHOLD = 15;
const FAIL_THRESHOLD = 30;

// Normal damage by difficulty (for detecting critical hits)
const DAMAGE_BY_DIFF = {easy: 15, medium: 20, hard: 25, expert: 30};

let gameState = {};
let gameMode = 'quest';
let levelMap = [];
let currentLevelInfo = {};
let submitting = false;
let timerInterval = null;
let problemStartTime = 0;
let timersOff = false;
let activeBossSpecial = null;
let mindflayerTimeout = null;

// --- Screen Management ---

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
    document.getElementById(screenId).classList.remove('hidden');
}

// --- API Helpers ---

async function api(url, method = 'GET', body = null) {
    const opts = {method, headers: {'Content-Type': 'application/json'}};
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 404 && err.error === 'No active game') {
            window.location.href = '/';
            return null;
        }
        throw new Error(err.error || 'API error');
    }
    return res.json();
}

// --- Initialize ---

async function init() {
    const data = await api('/api/state');
    if (!data) return;
    gameState = data.game_state;
    gameMode = gameState.mode || 'quest';
    timersOff = gameState.timers_off || false;

    bindEvents();

    if (gameMode === 'quest') {
        levelMap = data.level_map;
        renderLevelMap();
        showScreen(GameScreen.MAP);
    } else if (gameMode === 'dungeon') {
        showDungeonFloorIntro();
    } else if (gameMode === 'gauntlet') {
        showScreen(GameScreen.GAUNTLET_INTRO);
    }
}

// ========================================
// QUEST MODE (existing)
// ========================================

function renderLevelMap() {
    document.getElementById('map-realm-title').textContent = gameState.realm;
    document.getElementById('map-score').textContent = gameState.score.toLocaleString();

    const path = document.getElementById('level-path');
    path.innerHTML = '';

    levelMap.forEach((lvl, i) => {
        if (i > 0) {
            const connector = document.createElement('div');
            connector.className = 'level-connector' + (lvl.unlocked ? ' unlocked' : '');
            path.appendChild(connector);
        }

        const node = document.createElement('button');
        node.className = 'level-node' + (lvl.unlocked ? ' unlocked' : ' locked');
        if (lvl.stars > 0) node.classList.add('completed');
        if (lvl.is_boss) node.classList.add('boss-node');
        node.dataset.level = lvl.level;

        const starsHtml = lvl.stars > 0
            ? '<div class="node-stars">' + '\u2B50'.repeat(lvl.stars) + '<span class="empty-stars">' + '\u2606'.repeat(3 - lvl.stars) + '</span></div>'
            : '';

        const bossTag = lvl.is_boss ? '<span class="boss-tag">\uD83D\uDC7E BOSS</span>' : '';

        node.innerHTML = `
            <div class="node-number">${lvl.unlocked ? lvl.level : '\uD83D\uDD12'}</div>
            <div class="node-name">${lvl.name}</div>
            ${bossTag}
            ${starsHtml}
        `;

        if (lvl.unlocked) {
            node.addEventListener('click', () => startLevelIntro(lvl.level));
        }

        path.appendChild(node);
    });
}

async function startLevelIntro(level) {
    const data = await api('/api/start-level', 'POST', {level});
    if (!data) return;

    gameState = data.game_state;
    currentLevelInfo = data.level_info;

    document.getElementById('intro-realm').textContent = currentLevelInfo.realm;
    document.getElementById('intro-level-name').textContent =
        `Level ${currentLevelInfo.level}: ${currentLevelInfo.name}`;

    const bossIntro = document.getElementById('boss-intro');
    const problemsStat = document.getElementById('intro-problems-stat');

    const previewEl = document.getElementById('intro-example');
    if (data.example_problem) {
        previewEl.textContent = data.example_problem + ' = ?';
        previewEl.classList.remove('hidden');
    } else {
        previewEl.classList.add('hidden');
    }

    if (currentLevelInfo.is_boss) {
        document.getElementById('intro-desc').textContent =
            'Defeat the guardian to conquer this realm!';
        problemsStat.classList.add('hidden');
        bossIntro.classList.remove('hidden');
        document.getElementById('boss-intro-name').textContent = currentLevelInfo.boss.name;
        document.getElementById('boss-intro-hp').textContent = `${currentLevelInfo.boss.hp} HP`;
    } else {
        document.getElementById('intro-desc').textContent =
            `Solve ${currentLevelInfo.num_problems} problems to advance`;
        document.getElementById('intro-problems').textContent = currentLevelInfo.num_problems;
        problemsStat.classList.remove('hidden');
        bossIntro.classList.add('hidden');
    }

    showScreen(GameScreen.INTRO);
    window._firstProblem = data.problem;
}

function showLevelComplete(data) {
    stopTimer();

    document.getElementById('complete-title').textContent =
        data.level_complete_message || 'Level Complete!';

    const banner = document.getElementById('boss-defeat-banner');
    if (data.boss_defeated) {
        banner.classList.remove('hidden');
        document.getElementById('boss-defeat-name').textContent = gameState.boss_name || 'The Boss';
    } else {
        banner.classList.add('hidden');
    }

    const starsDiv = document.getElementById('stars-display');
    starsDiv.innerHTML = '';
    for (let i = 0; i < 3; i++) {
        const star = document.createElement('span');
        star.className = 'complete-star' + (i < data.stars ? ' earned' : '');
        star.textContent = i < data.stars ? '\u2B50' : '\u2606';
        star.style.animationDelay = (i * 0.3) + 's';
        starsDiv.appendChild(star);
    }

    const gs = data.game_state;
    const accuracy = gs.problems_answered > 0
        ? Math.round((gs.problems_correct / gs.problems_answered) * 100) : 0;

    document.getElementById('complete-accuracy').textContent = accuracy + '%';
    document.getElementById('complete-streak').textContent = gs.best_streak;
    document.getElementById('complete-level-score').textContent = gs.level_score.toLocaleString();
    document.getElementById('complete-bonus').textContent = '+' + data.completion_bonus.toLocaleString();
    document.getElementById('complete-message').textContent = data.level_complete_message;

    const achPopup = document.getElementById('achievement-popup');
    if (data.new_achievements && data.new_achievements.length > 0) {
        achPopup.classList.remove('hidden');
        achPopup.innerHTML = data.new_achievements.map(a =>
            `<div class="achievement-earned">
                <span class="ach-icon">${a.icon}</span>
                <span class="ach-info">
                    <strong>${a.name}</strong>
                    <span class="ach-desc">${a.description}</span>
                </span>
            </div>`
        ).join('');
    } else {
        achPopup.classList.add('hidden');
    }

    const nextBtn = document.getElementById('btn-next-level');
    nextBtn.style.display = gs.current_level >= 5 ? 'none' : '';

    showScreen(GameScreen.COMPLETE);
    Animations.confetti();
}

function showGameOver(data) {
    stopTimer();
    const gs = data.game_state;

    if (gameMode === 'dungeon') {
        document.getElementById('dungeon-death-floor').textContent = gs.floor;
        document.getElementById('dungeon-death-score').textContent = (gs.dungeon_score || 0).toLocaleString();
        document.getElementById('dungeon-death-msg').textContent = `You fell on floor ${gs.floor}.`;
        showScreen(GameScreen.DUNGEON_GAMEOVER);
        return;
    }

    if (gameMode === 'gauntlet') {
        document.getElementById('gauntlet-final-survived').textContent = gs.problems_correct;
        document.getElementById('gauntlet-final-score').textContent = (gs.gauntlet_score || 0).toLocaleString();
        document.getElementById('gauntlet-final-streak').textContent = gs.best_streak;
        showScreen(GameScreen.GAUNTLET_GAMEOVER);
        return;
    }

    document.getElementById('gameover-solved').textContent = gs.problems_correct;
    document.getElementById('gameover-score').textContent = gs.level_score.toLocaleString();
    showScreen(GameScreen.GAMEOVER);
}

// ========================================
// DUNGEON MODE
// ========================================

async function showDungeonFloorIntro() {
    const floor = gameState.floor || 1;
    document.getElementById('dungeon-floor-badge').textContent = `Floor ${floor}`;
    document.getElementById('dungeon-hp-preview').textContent = gameState.hp;

    const bossFloors = {10: 'Grokk the Ogre', 20: 'Xalthar the Beholder', 30: 'Zerathul the Mindflayer'};
    const bossIntro = document.getElementById('dungeon-boss-intro');

    if (bossFloors[floor]) {
        bossIntro.classList.remove('hidden');
        document.getElementById('dungeon-boss-name').textContent = bossFloors[floor];
        const bossHps = {10: 120, 20: 180, 30: 250};
        document.getElementById('dungeon-boss-hp').textContent = bossHps[floor] + ' HP';
        const warnings = {
            10: 'Ogre Smash: Miss a charged problem and you die instantly!',
            20: 'Evil Eye: Numbers will float and dance before your eyes!',
            30: 'Mind Blast: The problem vanishes after 3 seconds!',
        };
        document.getElementById('dungeon-boss-warning').textContent = warnings[floor];
        document.getElementById('dungeon-floor-title').textContent = 'Boss Battle!';
        document.getElementById('dungeon-floor-desc').textContent = 'Defeat the guardian to continue deeper.';
    } else {
        bossIntro.classList.add('hidden');
        if (floor <= 10) {
            document.getElementById('dungeon-floor-title').textContent = 'Upper Depths';
            document.getElementById('dungeon-floor-desc').textContent = 'Addition & Subtraction';
        } else if (floor <= 20) {
            document.getElementById('dungeon-floor-title').textContent = 'Middle Depths';
            document.getElementById('dungeon-floor-desc').textContent = 'All Four Operations';
        } else {
            document.getElementById('dungeon-floor-title').textContent = 'The Abyss';
            document.getElementById('dungeon-floor-desc').textContent = 'Multi-step & Parentheses';
        }
    }

    showScreen(GameScreen.DUNGEON_INTRO);
}

async function startDungeonFloor() {
    const data = await api('/api/dungeon-floor', 'POST');
    if (!data) return;
    gameState = data.game_state;
    window._firstProblem = data.problem;
    activeBossSpecial = data.boss_special || null;
    startPlayingMode();
}

// ========================================
// GAUNTLET MODE
// ========================================

async function startGauntlet() {
    const data = await api('/api/gauntlet-start', 'POST');
    if (!data) return;
    gameState = data.game_state;
    window._firstProblem = data.problem;
    activeBossSpecial = null;
    startPlayingMode();
}

// ========================================
// SHARED PLAY SCREEN
// ========================================

function startPlayingMode() {
    showScreen(GameScreen.PLAY);

    const bossContainer = document.getElementById('boss-bar-container');
    const progressContainer = document.getElementById('progress-container');
    const chargeContainer = document.getElementById('charge-container');
    const enragedBanner = document.getElementById('boss-enraged-banner');
    const dungeonBar = document.getElementById('dungeon-floor-bar');
    const gauntletBar = document.getElementById('gauntlet-survived-bar');
    const hpContainer = document.querySelector('.hp-container');
    const specialOverlay = document.getElementById('boss-special-overlay');

    specialOverlay.classList.add('hidden');

    if (gameMode === 'dungeon') {
        dungeonBar.classList.remove('hidden');
        gauntletBar.classList.add('hidden');
        hpContainer.style.display = '';
        updateDungeonFloorUI();

        if (gameState.in_boss_fight) {
            bossContainer.classList.remove('hidden');
            progressContainer.classList.add('hidden');
            chargeContainer.classList.add('hidden');
            enragedBanner.classList.add('hidden');
            updateBossBar();
        } else {
            bossContainer.classList.add('hidden');
            chargeContainer.classList.add('hidden');
            progressContainer.classList.remove('hidden');
            enragedBanner.classList.add('hidden');
        }
    } else if (gameMode === 'gauntlet') {
        dungeonBar.classList.add('hidden');
        gauntletBar.classList.remove('hidden');
        hpContainer.style.display = 'none';
        bossContainer.classList.add('hidden');
        chargeContainer.classList.add('hidden');
        progressContainer.classList.add('hidden');
        enragedBanner.classList.add('hidden');
        document.getElementById('gauntlet-survived-count').textContent = gameState.problems_correct;
    } else {
        // Quest mode
        dungeonBar.classList.add('hidden');
        gauntletBar.classList.add('hidden');
        hpContainer.style.display = '';

        if (gameState.in_boss_fight) {
            bossContainer.classList.remove('hidden');
            chargeContainer.classList.remove('hidden');
            progressContainer.classList.add('hidden');
            enragedBanner.classList.add('hidden');
            updateBossBar();
            updateChargeMeter(0);
        } else {
            bossContainer.classList.add('hidden');
            chargeContainer.classList.add('hidden');
            progressContainer.classList.remove('hidden');
            enragedBanner.classList.add('hidden');
        }
    }

    updatePlayUI();
    showProblem(window._firstProblem);
    if (activeBossSpecial) applyBossSpecial(activeBossSpecial);
    focusInput();
}

function startPlaying() {
    startPlayingMode();
}

function updateDungeonFloorUI() {
    const floor = gameState.floor || 1;
    document.getElementById('dungeon-floor-num').textContent = floor;
    const pct = ((floor - 1) / 30) * 100;
    document.getElementById('dungeon-floor-progress').style.width = pct + '%';
}

// --- Timer ---

function getTimerThresholds() {
    if (gameMode === 'gauntlet') {
        const gt = gameState.gauntlet_timer || {};
        return {
            fast: gt.fast || 5,
            slow: gt.slow || 10,
            fail: gt.fail || 15,
        };
    }
    return {fast: FAST_THRESHOLD, slow: SLOW_THRESHOLD, fail: FAIL_THRESHOLD};
}

function startTimer() {
    stopTimer();
    problemStartTime = Date.now();

    if (timersOff && gameMode !== 'gauntlet') return;

    const {fast, slow, fail} = getTimerThresholds();
    const timerContainer = document.getElementById('timer-container');
    const timerBar = document.getElementById('timer-bar');
    const timerText = document.getElementById('timer-text');

    if (gameMode === 'gauntlet') {
        // Gauntlet: always show timer
        timerContainer.classList.remove('hidden');
        timerBar.style.width = '100%';
        timerBar.className = 'timer-bar-inner timer-normal';
        timerText.textContent = fail + 's';
    } else {
        timerContainer.classList.add('hidden');
        timerBar.style.width = '100%';
        timerBar.className = 'timer-bar-inner';
    }

    timerInterval = setInterval(() => {
        const elapsed = (Date.now() - problemStartTime) / 1000;

        if (gameMode === 'gauntlet') {
            // Gauntlet: always visible, 3 phases within 15s
            timerContainer.classList.remove('hidden');
            if (elapsed < fast) {
                const remaining = fast - elapsed;
                const pct = (remaining / fast) * 100;
                timerBar.style.width = (33 + 67 * remaining / fast) + '%';
                timerBar.className = 'timer-bar-inner timer-normal';
                timerText.textContent = Math.ceil(fail - elapsed) + 's';
            } else if (elapsed < slow) {
                const remaining = slow - elapsed;
                const pct = (remaining / (slow - fast)) * 100;
                timerBar.style.width = (10 + 23 * remaining / (slow - fast)) + '%';
                timerBar.className = 'timer-bar-inner timer-normal';
                timerText.textContent = Math.ceil(fail - elapsed) + 's';
            } else if (elapsed < fail) {
                const remaining = fail - elapsed;
                timerBar.style.width = (10 * remaining / (fail - slow)) + '%';
                timerBar.className = 'timer-bar-inner timer-danger';
                timerText.textContent = Math.ceil(remaining) + 's !';
            } else {
                stopTimer();
                autoFail();
            }
        } else {
            if (elapsed < fast) {
                timerContainer.classList.add('hidden');
            } else if (elapsed < slow) {
                timerContainer.classList.remove('hidden');
                const remaining = slow - elapsed;
                const pct = (remaining / (slow - fast)) * 100;
                timerBar.style.width = pct + '%';
                timerBar.className = 'timer-bar-inner timer-normal';
                timerText.textContent = Math.ceil(remaining) + 's';
            } else if (elapsed < fail) {
                timerContainer.classList.remove('hidden');
                const remaining = fail - elapsed;
                const pct = (remaining / (fail - slow)) * 100;
                timerBar.style.width = pct + '%';
                timerBar.className = 'timer-bar-inner timer-danger';
                timerText.textContent = Math.ceil(remaining) + 's !';
            } else {
                stopTimer();
                autoFail();
            }
        }
    }, 100);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    document.getElementById('timer-container').classList.add('hidden');
}

async function autoFail() {
    if (submitting) return;
    submitting = true;
    document.getElementById('btn-submit').disabled = true;

    const data = await api('/api/answer', 'POST', {timed_out: true});
    if (!data) return;

    gameState = data.game_state;
    clearBossSpecialEffects();
    await showFeedback(data);
    document.getElementById('btn-submit').disabled = false;

    if (data.game_over) {
        showGameOver(data);
    } else if (gameMode === 'dungeon' && data.dungeon_complete) {
        showDungeonComplete();
    } else if (gameMode === 'dungeon' && data.floor_complete) {
        showDungeonFloorIntro();
    } else {
        const next = await api('/api/problem');
        if (next) {
            gameState = next.game_state;
            activeBossSpecial = next.boss_special || null;
            updatePlayUI();
            if (gameMode === 'dungeon') updateDungeonFloorUI();
            if (gameState.in_boss_fight) updateBossBar();
            if (gameMode === 'gauntlet') {
                document.getElementById('gauntlet-survived-count').textContent = gameState.problems_correct;
            }
            showProblem(next.problem);
            if (activeBossSpecial) applyBossSpecial(activeBossSpecial);
        }
    }
}

// --- Gameplay ---

function showProblem(problemData) {
    const expr = document.getElementById('problem-expression');
    expr.textContent = problemData.expression;
    expr.classList.remove('mindflayer-hidden');

    if (!problemData.is_boss && problemData.total_problems > 0) {
        document.getElementById('progress-text').textContent =
            `${problemData.problem_number} / ${problemData.total_problems}`;
        const pct = ((problemData.problem_number - 1) / problemData.total_problems) * 100;
        document.getElementById('progress-bar').style.width = pct + '%';
    }

    document.getElementById('answer-input').value = '';
    focusInput();
    submitting = false;
    startTimer();

    const card = document.getElementById('problem-card');
    card.classList.remove('problem-enter');
    void card.offsetWidth;
    card.classList.add('problem-enter');
}

function updatePlayUI() {
    if (gameMode !== 'gauntlet') {
        const hp = gameState.hp;
        const hpBar = document.getElementById('hp-bar');
        hpBar.style.width = hp + '%';
        hpBar.className = 'hp-bar-inner';
        if (hp > 60) hpBar.classList.add('hp-high');
        else if (hp > 30) hpBar.classList.add('hp-mid');
        else hpBar.classList.add('hp-low');
        document.getElementById('hp-text').textContent = hp;
    }

    const scoreVal = gameMode === 'dungeon' ? (gameState.dungeon_score || 0) :
                     gameMode === 'gauntlet' ? (gameState.gauntlet_score || 0) :
                     gameState.score;
    document.getElementById('play-score').textContent = scoreVal.toLocaleString();

    const streak = gameState.streak;
    const streakDisplay = document.getElementById('streak-display');
    document.getElementById('streak-count').textContent = streak;
    const icon = document.getElementById('streak-icon');

    if (streak >= 10) {
        icon.textContent = '\uD83D\uDD25\uD83D\uDD25';
        streakDisplay.className = 'streak-display streak-legendary';
    } else if (streak >= 5) {
        icon.textContent = '\uD83D\uDD25';
        streakDisplay.className = 'streak-display streak-hot';
    } else if (streak >= 3) {
        icon.textContent = '\u2728';
        streakDisplay.className = 'streak-display streak-warm';
    } else {
        icon.textContent = '';
        streakDisplay.className = 'streak-display';
    }
}

function updateBossBar() {
    const bossHp = gameState.boss_hp;
    const bossMaxHp = gameState.boss_max_hp;
    const pct = bossMaxHp > 0 ? (bossHp / bossMaxHp) * 100 : 0;
    const bar = document.getElementById('boss-bar');
    bar.style.width = pct + '%';
    document.getElementById('boss-bar-hp').textContent = bossHp;
    document.getElementById('boss-bar-label').textContent = gameState.boss_name || 'Boss';

    const banner = document.getElementById('boss-enraged-banner');
    if (gameState.boss_enraged) {
        banner.classList.remove('hidden');
        document.getElementById('enraged-text').textContent =
            `${gameState.boss_name} is Enraged! Finish quickly!`;
    } else {
        banner.classList.add('hidden');
    }
}

function updateChargeMeter(charge) {
    const pips = document.querySelectorAll('.charge-pip');
    pips.forEach((pip, i) => {
        if (i < charge) pip.classList.add('filled');
        else pip.classList.remove('filled');
    });
}

// --- Boss Specials ---

function applyBossSpecial(special) {
    const overlay = document.getElementById('boss-special-overlay');
    const text = document.getElementById('boss-special-text');

    if (special === 'ogre_instakill') {
        overlay.classList.remove('hidden');
        text.textContent = '\uD83D\uDCA2 OGRE SMASH! Miss this and you DIE!';
        overlay.className = 'boss-special-overlay boss-special-ogre';
    } else if (special === 'beholder_float') {
        overlay.classList.remove('hidden');
        text.textContent = '\uD83D\uDC41\uFE0F Evil Eye! The numbers dance...';
        overlay.className = 'boss-special-overlay boss-special-beholder';
        document.getElementById('problem-expression').classList.add('beholder-float');
    } else if (special === 'mindflayer_vanish') {
        overlay.classList.remove('hidden');
        text.textContent = '\uD83E\uDDE0 Mind Blast! Remember quickly...';
        overlay.className = 'boss-special-overlay boss-special-mindflayer';
        if (mindflayerTimeout) clearTimeout(mindflayerTimeout);
        mindflayerTimeout = setTimeout(() => {
            document.getElementById('problem-expression').classList.add('mindflayer-hidden');
        }, 3000);
    }
}

function clearBossSpecialEffects() {
    document.getElementById('boss-special-overlay').classList.add('hidden');
    document.getElementById('problem-expression').classList.remove('beholder-float', 'mindflayer-hidden');
    if (mindflayerTimeout) {
        clearTimeout(mindflayerTimeout);
        mindflayerTimeout = null;
    }
    activeBossSpecial = null;
}

// --- Submit Answer ---

async function submitAnswer() {
    if (submitting) return;
    const input = document.getElementById('answer-input');
    const val = input.value.trim();
    if (val === '') return;

    submitting = true;
    stopTimer();
    clearBossSpecialEffects();
    document.getElementById('btn-submit').disabled = true;

    const data = await api('/api/answer', 'POST', {answer: parseInt(val, 10)});
    if (!data) return;

    gameState = data.game_state;

    await showFeedback(data);

    document.getElementById('btn-submit').disabled = false;

    if (data.game_over) {
        showGameOver(data);
    } else if (gameMode === 'quest' && data.level_complete) {
        showLevelComplete(data);
    } else if (gameMode === 'dungeon' && data.dungeon_complete) {
        showDungeonComplete();
    } else if (gameMode === 'dungeon' && data.floor_complete) {
        showDungeonFloorIntro();
    } else {
        const next = await api('/api/problem');
        if (next) {
            gameState = next.game_state;
            activeBossSpecial = next.boss_special || null;
            updatePlayUI();
            if (gameMode === 'dungeon') updateDungeonFloorUI();
            if (gameState.in_boss_fight) updateBossBar();
            if (gameMode === 'gauntlet') {
                document.getElementById('gauntlet-survived-count').textContent = gameState.problems_correct;
            }
            showProblem(next.problem);
            if (activeBossSpecial) applyBossSpecial(activeBossSpecial);
        }
    }
}

async function showFeedback(data) {
    const overlay = document.getElementById('feedback-overlay');
    const content = document.getElementById('feedback-content');

    if (data.correct) {
        let html = `<div class="feedback-correct">
            <div class="feedback-icon">\u2705</div>
            <div class="feedback-text">${data.feedback_message}</div>
            <div class="feedback-points">+${data.points_earned} pts</div>`;
        if (data.speed_bonus) html += '<div class="feedback-speed">FAST!</div>';
        if (data.slow_penalty) html += '<div class="feedback-slow">SLOW -20%</div>';
        if (data.streak_multiplier > 1) html += `<div class="feedback-streak">x${data.streak_multiplier} streak</div>`;
        if (data.healed > 0) html += `<div class="feedback-heal">+${data.healed} HP healed!</div>`;
        if (data.power_strike) html += `<div class="feedback-power-strike">\u26A1 POWER STRIKE! -${data.power_strike_damage} boss HP</div>`;
        if (data.boss_damage_dealt > 0) html += `<div class="feedback-boss-dmg">\u2694\uFE0F -${data.boss_damage_dealt} boss HP</div>`;
        if (data.boss_attack_damage > 0) html += `<div class="feedback-boss-retaliate">Boss retaliates! -${data.boss_attack_damage} HP</div>`;
        html += '</div>';
        content.innerHTML = html;

        if (data.boss_attack_damage > 0) {
            overlay.className = 'feedback-overlay feedback-mixed-bg';
        } else {
            overlay.className = 'feedback-overlay feedback-correct-bg';
        }
        Animations.pulseElement(document.getElementById('problem-card'), 'correct');
        if (data.healed > 0) Animations.healHP();
        if (data.boss_damage_dealt > 0) Animations.bossDamage();
        if (data.boss_attack_damage > 0) Animations.drainHP(data.boss_attack_damage);
        if (data.power_strike) Animations.powerStrike();
    } else {
        const reason = data.timed_out ? "Time's up!" : data.feedback_message;
        let dmgText = '';
        if (gameMode === 'gauntlet') {
            dmgText = 'INSTANT DEATH';
        } else if (data.boss_special === 'ogre_instakill') {
            dmgText = 'OGRE SMASH! INSTANT DEATH!';
        } else {
            dmgText = `-${data.damage} HP`;
        }
        let wrongHtml = `<div class="feedback-wrong">
            <div class="feedback-icon">\u274C</div>
            <div class="feedback-text">${reason}</div>
            <div class="feedback-answer">The answer was ${data.correct_answer}</div>
            <div class="feedback-damage">${dmgText}</div>`;
        if (gameMode === 'quest' && data.damage > DAMAGE_BY_DIFF[gameState.difficulty]) {
            wrongHtml += '<div class="feedback-crit">CRITICAL HIT!</div>';
        }
        wrongHtml += '</div>';
        content.innerHTML = wrongHtml;
        overlay.className = 'feedback-overlay feedback-wrong-bg';
        Animations.shakeElement(document.getElementById('problem-card'));
        if (gameMode !== 'gauntlet') Animations.drainHP(data.damage);
    }

    if (gameMode === 'quest' && gameState.in_boss_fight) {
        updateChargeMeter(data.charge_meter || 0);
    }

    overlay.classList.remove('hidden');
    updatePlayUI();
    if (gameState.in_boss_fight) updateBossBar();

    await new Promise(r => setTimeout(r, data.correct ? 1200 : 2000));
    overlay.classList.add('hidden');
}

// --- Dungeon Complete ---

function showDungeonComplete() {
    stopTimer();
    const gs = gameState;
    document.getElementById('dungeon-final-hp').textContent = gs.hp;
    document.getElementById('dungeon-final-score').textContent = (gs.dungeon_score || 0).toLocaleString();
    const acc = gs.problems_answered > 0
        ? Math.round((gs.problems_correct / gs.problems_answered) * 100) : 0;
    document.getElementById('dungeon-final-accuracy').textContent = acc + '%';
    document.getElementById('dungeon-final-streak').textContent = gs.best_streak;
    showScreen(GameScreen.DUNGEON_COMPLETE);
    Animations.confetti();
}

// --- Event Binding ---

function bindEvents() {
    document.getElementById('btn-ready').addEventListener('click', startPlaying);
    document.getElementById('btn-submit').addEventListener('click', submitAnswer);

    document.getElementById('answer-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitAnswer();
    });

    document.getElementById('btn-next-level').addEventListener('click', async () => {
        const nextLevel = gameState.current_level + 1;
        if (nextLevel <= 5) {
            await startLevelIntro(nextLevel);
        } else {
            await refreshMap();
            showScreen(GameScreen.MAP);
        }
    });

    document.getElementById('btn-back-map').addEventListener('click', async () => {
        stopTimer();
        await refreshMap();
        showScreen(GameScreen.MAP);
    });

    document.getElementById('btn-retry').addEventListener('click', async () => {
        const data = await api('/api/restart-level', 'POST');
        if (!data) return;
        gameState = data.game_state;
        currentLevelInfo = data.level_info;
        window._firstProblem = data.problem;
        startPlaying();
    });

    document.getElementById('btn-gameover-map').addEventListener('click', async () => {
        await refreshMap();
        showScreen(GameScreen.MAP);
    });

    // Dungeon events
    document.getElementById('btn-dungeon-ready').addEventListener('click', startDungeonFloor);

    // Gauntlet events
    document.getElementById('btn-gauntlet-ready').addEventListener('click', startGauntlet);
}

async function refreshMap() {
    const data = await api('/api/state');
    if (data) {
        gameState = data.game_state;
        levelMap = data.level_map;
        renderLevelMap();
    }
}

function focusInput() {
    setTimeout(() => document.getElementById('answer-input').focus(), 100);
}

// Start
init();
