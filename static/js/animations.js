// Animations module
const Animations = {
    shakeElement(el) {
        el.classList.add('shake');
        setTimeout(() => el.classList.remove('shake'), 500);
    },

    pulseElement(el, type) {
        el.classList.add('pulse-' + type);
        setTimeout(() => el.classList.remove('pulse-' + type), 600);
    },

    drainHP(damage) {
        const bar = document.getElementById('hp-bar');
        bar.classList.add('hp-flash');
        setTimeout(() => bar.classList.remove('hp-flash'), 400);
    },

    healHP() {
        const bar = document.getElementById('hp-bar');
        bar.classList.add('hp-heal');
        setTimeout(() => bar.classList.remove('hp-heal'), 600);
    },

    bossDamage() {
        const bar = document.getElementById('boss-bar');
        if (!bar) return;
        bar.classList.add('boss-hit');
        setTimeout(() => bar.classList.remove('boss-hit'), 400);
    },

    powerStrike() {
        const flash = document.createElement('div');
        flash.className = 'power-strike-flash';
        document.body.appendChild(flash);
        setTimeout(() => flash.remove(), 600);
        // Also shake the boss bar
        const container = document.getElementById('boss-bar-container');
        if (container) {
            container.classList.add('shake');
            setTimeout(() => container.classList.remove('shake'), 500);
        }
    },

    floatPoints(container, points) {
        const el = document.createElement('div');
        el.className = 'float-points';
        el.textContent = '+' + points;
        container.appendChild(el);
        setTimeout(() => el.remove(), 1000);
    },

    confetti() {
        const container = document.querySelector('.screen:not(.hidden)');
        if (!container) return;

        const colors = ['#d4a03c', '#2ecc71', '#e74c3c', '#3498db', '#9b59b6', '#f39c12'];
        for (let i = 0; i < 40; i++) {
            const piece = document.createElement('div');
            piece.className = 'confetti-piece';
            piece.style.left = Math.random() * 100 + '%';
            piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            piece.style.animationDelay = (Math.random() * 0.5) + 's';
            piece.style.animationDuration = (1.5 + Math.random() * 2) + 's';
            container.appendChild(piece);
            setTimeout(() => piece.remove(), 4000);
        }
    },
};
