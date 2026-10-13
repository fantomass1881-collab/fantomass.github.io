/* ═══════════════════════════════════════════════════
   Castle Busters — игровая логика (веб-версия)
   ═══════════════════════════════════════════════════ */

// ─── CASTLE LEVELS ───────────────────────────────────────
const CASTLE_LEVELS = {
  1: { castle_hp: 500, upgrade_cost: 200 },
  2: { castle_hp: 800, upgrade_cost: 400 },
  3: { castle_hp: 1200, upgrade_cost: 800 },
  4: { castle_hp: 1800, upgrade_cost: 1500 },
  5: { castle_hp: 2500, upgrade_cost: 3000 },
};

// ─── UNITS DATA ──────────────────────────────────────────
const UNITS = [
  { key: 'warrior', name: 'Воин', emoji: '⚔️', attack: 15, defense: 10, hp: 100, cost: 50 },
  { key: 'archer', name: 'Лучник', emoji: '🏹', attack: 20, defense: 5, hp: 70, cost: 70 },
  { key: 'mage', name: 'Маг', emoji: '🔮', attack: 35, defense: 3, hp: 50, cost: 120 },
  { key: 'knight', name: 'Рыцарь', emoji: '🛡️', attack: 10, defense: 25, hp: 150, cost: 100 },
  { key: 'dragon', name: 'Дракон', emoji: '🐉', attack: 50, defense: 15, hp: 200, cost: 300 },
];

const SAVE_KEY = 'castleBustersSave';

// ─── GAME STATE ──────────────────────────────────────────
let game = {
  gold: 500,
  castleLevel: 1,
  castleHp: CASTLE_LEVELS[1].castle_hp,
  castleMaxHp: CASTLE_LEVELS[1].castle_hp,
  army: {},
  wins: 0,
  losses: 0,
  lastDaily: null,
};

let currentTarget = null;

// ─── INIT ────────────────────────────────────────────────
function init() {
  loadGame();
  renderUnitShop();
  updateUI();
}

function loadGame() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (raw) {
      const saved = JSON.parse(raw);
      game = Object.assign(game, saved);
    }
  } catch (e) {
    console.warn('Не удалось загрузить сохранение', e);
  }
}

function saveGame() {
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(game));
  } catch (e) {
    console.warn('Не удалось сохранить игру', e);
  }
}

// ─── SCREEN NAVIGATION ───────────────────────────────────
function showScreen(name) {
  playSound('click');
  document.querySelectorAll('.screen').forEach((el) => el.classList.remove('active'));
  const target = document.getElementById(`screen-${name}`);
  if (target) target.classList.add('active');

  if (name === 'recruit') renderUnitShop();
  if (name === 'attack') loadTargets();
  if (name === 'leaderboard') loadLeaderboard();
}

// ─── ARMY HELPERS ────────────────────────────────────────
function getArmyPower(army) {
  let attack = 0;
  let defense = 0;
  let hp = 0;
  UNITS.forEach((u) => {
    const count = army[u.key] || 0;
    attack += u.attack * count;
    defense += u.defense * count;
    hp += u.hp * count;
  });
  return { attack, defense, hp };
}

function getUnitByKey(key) {
  return UNITS.find((u) => u.key === key);
}

// ─── UPDATE UI ───────────────────────────────────────────
function updateUI() {
  document.getElementById('gold').textContent = game.gold;
  document.getElementById('recruit-gold').textContent = game.gold;
  document.getElementById('castle-level').textContent = `Ур. ${game.castleLevel}`;

  const hpPercent = Math.max(0, Math.round((game.castleHp / game.castleMaxHp) * 100));
  const hpBar = document.getElementById('castle-hp-bar');
  hpBar.style.width = `${hpPercent}%`;
  hpBar.classList.toggle('low', hpPercent <= 25);
  hpBar.classList.toggle('mid', hpPercent > 25 && hpPercent <= 60);
  document.getElementById('castle-hp-text').textContent = `${game.castleHp} / ${game.castleMaxHp}`;

  document.getElementById('wins').textContent = game.wins;
  document.getElementById('losses').textContent = game.losses;

  renderArmyPreview();
}

function renderArmyPreview() {
  const list = document.getElementById('army-list');
  const owned = UNITS.filter((u) => (game.army[u.key] || 0) > 0);
  if (owned.length === 0) {
    list.innerHTML = '<p class="empty-army">Армия пуста. Нанимай воинов!</p>';
    return;
  }
  list.innerHTML = owned
    .map((u) => `<div class="army-unit"><span>${u.emoji}</span><span>${game.army[u.key]}</span></div>`)
    .join('');
}

// ─── RECRUIT ─────────────────────────────────────────────
function renderUnitShop() {
  const shop = document.getElementById('unit-shop');
  shop.innerHTML = UNITS.map((u) => {
    const canAfford = game.gold >= u.cost;
    return `
      <div class="unit-card">
        <div class="unit-info">
          <div class="unit-emoji">${u.emoji}</div>
          <div class="unit-details">
            <h4>${u.name}</h4>
            <div class="unit-stats">⚔️${u.attack} 🛡️${u.defense} ❤️${u.hp} · ${u.cost}💰</div>
          </div>
        </div>
        <button class="unit-buy-btn ${canAfford ? 'can-afford' : 'cant-afford'}"
          onclick="recruitUnit('${u.key}')" ${canAfford ? '' : 'disabled'}>Нанять</button>
      </div>`;
  }).join('');
  document.getElementById('recruit-gold').textContent = game.gold;
}

function recruitUnit(unitKey) {
  const unit = getUnitByKey(unitKey);
  if (!unit) return;
  if (game.gold < unit.cost) {
    showToast('Не хватает золота!');
    return;
  }
  game.gold -= unit.cost;
  game.army[unitKey] = (game.army[unitKey] || 0) + 1;
  playSound('recruit');
  showToast(`Нанят: ${unit.emoji} ${unit.name}`);
  saveGame();
  renderUnitShop();
  updateUI();
}

// ─── ATTACK ──────────────────────────────────────────────
function generateEnemy(seed) {
  const level = Math.max(1, Math.min(5, game.castleLevel + Math.floor(Math.random() * 3) - 1));
  const army = {};
  const unitCount = 2 + Math.floor(Math.random() * 4);
  for (let i = 0; i < unitCount; i++) {
    const u = UNITS[Math.floor(Math.random() * UNITS.length)];
    army[u.key] = (army[u.key] || 0) + 1 + Math.floor(Math.random() * 3);
  }
  const names = ['Гром', 'Вереск', 'Сталь', 'Ворон', 'Буря', 'Пепел', 'Клык', 'Тень'];
  return {
    id: seed,
    name: `Замок «${names[seed % names.length]}»`,
    castleLevel: level,
    castleHp: CASTLE_LEVELS[level].castle_hp,
    castleMaxHp: CASTLE_LEVELS[level].castle_hp,
    army,
  };
}

function loadTargets() {
  const power = getArmyPower(game.army);
  document.getElementById('attack-power').textContent = power.attack;

  const list = document.getElementById('target-list');
  const targets = [1, 2, 3, 4].map((seed) => generateEnemy(seed + Math.floor(Date.now() / 100000)));

  list.innerHTML = targets
    .map((t) => {
      const enemyPower = getArmyPower(t.army);
      return `
        <div class="target-card" onclick='startBattle(${JSON.stringify(t).replace(/'/g, "&#39;")})'>
          <div>
            <div class="target-name">${t.name}</div>
            <div class="target-info">🏰 Ур.${t.castleLevel} · ⚔️${enemyPower.attack} · 🛡️${enemyPower.defense}</div>
          </div>
        </div>`;
    })
    .join('');
}

function startBattle(target) {
  currentTarget = target;
  playSound('attack');
  showScreen('battle');

  document.getElementById('attacker-hp').textContent = `${game.castleHp}/${game.castleMaxHp}`;
  document.getElementById('defender-hp').textContent = `${target.castleHp}/${target.castleMaxHp}`;
  document.getElementById('battle-log').innerHTML = '';
  document.getElementById('battle-actions').innerHTML =
    '<button class="btn btn-danger" onclick="runBattleAnimation()">⚔️ Начать бой</button>';
}

function addBattleLog(text) {
  const log = document.getElementById('battle-log');
  const entry = document.createElement('div');
  entry.className = 'battle-log-entry';
  entry.textContent = text;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

function runBattleAnimation() {
  document.getElementById('battle-actions').innerHTML = '';
  const attackerArmy = getArmyPower(game.army);
  const defenderArmy = getArmyPower(currentTarget.army);

  const attPower = attackerArmy.attack + Math.floor(Math.random() * 21);
  const defPower = defenderArmy.defense + Math.floor(defenderArmy.attack / 2) + Math.floor(Math.random() * 16);

  const damageToDefCastle = Math.max(10, attPower - defenderArmy.defense);
  const counterDamage = Math.max(5, defenderArmy.attack - Math.floor(attackerArmy.defense / 2));

  let step = 0;
  const steps = [
    () => addBattleLog(`⚔️ Твоя армия атакует! Урон: ${attPower}`),
    () => addBattleLog(`🛡️ Защита врага держит удар. Пробито: ${damageToDefCastle}`),
    () => {
      currentTarget.castleHp = Math.max(0, currentTarget.castleHp - damageToDefCastle);
      document.getElementById('defender-hp').textContent = `${currentTarget.castleHp}/${currentTarget.castleMaxHp}`;
      addBattleLog(`💥 HP замка врага: ${currentTarget.castleHp}/${currentTarget.castleMaxHp}`);
    },
    () => addBattleLog(`🔥 Враг контратакует! Урон по твоему замку: ${counterDamage}`),
    () => {
      game.castleHp = Math.max(0, game.castleHp - counterDamage);
      document.getElementById('attacker-hp').textContent = `${game.castleHp}/${game.castleMaxHp}`;
      addBattleLog(`❤️ HP твоего замка: ${game.castleHp}/${game.castleMaxHp}`);
    },
    () => finishBattle(damageToDefCastle, counterDamage),
  ];

  const interval = setInterval(() => {
    if (step >= steps.length) {
      clearInterval(interval);
      return;
    }
    steps[step]();
    step += 1;
  }, 700);
}

function finishBattle(damageDealt, counterDamage) {
  const victory = currentTarget.castleHp <= 0;
  let goldReward = 0;

  if (victory) {
    goldReward = 100 + Math.floor(Math.random() * 201) + currentTarget.castleLevel * 50;
    game.gold += goldReward;
    game.wins += 1;
  } else {
    goldReward = 10 + Math.floor(Math.random() * 21);
    game.gold += goldReward;
  }

  if (game.castleHp <= 0) {
    game.losses += 1;
    game.castleHp = game.castleMaxHp;
  }

  saveGame();
  showBattleResult({ victory, goldReward, damageDealt, counterDamage });
}

function showBattleResult(result) {
  playSound(result.victory ? 'victory' : 'defeat');
  const container = document.getElementById('result-container');
  container.innerHTML = `
    <div class="result-title">${result.victory ? '🎉 Победа!' : '⚔️ Бой завершён'}</div>
    <div class="result-details">
      💥 Урон замку врага: ${result.damageDealt}<br>
      🛡️ Контратака по твоему замку: ${result.counterDamage}<br>
      💰 Награда: ${result.goldReward} золота<br>
      🏰 HP твоего замка: ${game.castleHp}/${game.castleMaxHp}
    </div>`;
  showScreen('result');
  updateUI();
}

// ─── UPGRADE CASTLE ──────────────────────────────────────
function upgradeCastle() {
  const nextLevel = game.castleLevel + 1;
  if (!CASTLE_LEVELS[nextLevel]) {
    showToast('Максимальный уровень замка!');
    return;
  }
  const cost = CASTLE_LEVELS[nextLevel].upgrade_cost;
  if (game.gold < cost) {
    showToast(`Не хватает золота! Нужно ${cost}💰`);
    return;
  }
  game.gold -= cost;
  game.castleLevel = nextLevel;
  game.castleMaxHp = CASTLE_LEVELS[nextLevel].castle_hp;
  game.castleHp = game.castleMaxHp;
  playSound('click');
  showToast(`🏰 Замок улучшен до уровня ${nextLevel}!`);
  saveGame();
  updateUI();
}

// ─── LEADERBOARD ─────────────────────────────────────────
function loadLeaderboard() {
  const list = document.getElementById('leaderboard-list');
  const entries = [
    { name: 'Ты', wins: game.wins, gold: game.gold },
    { name: 'Гром', wins: Math.max(0, game.wins + 2), gold: 600 },
    { name: 'Вереск', wins: Math.max(0, game.wins - 1), gold: 450 },
    { name: 'Ворон', wins: Math.max(0, game.wins + 1), gold: 520 },
  ].sort((a, b) => b.wins - a.wins || b.gold - a.gold);

  const medals = ['🥇', '🥈', '🥉'];
  list.innerHTML = entries
    .map((e, i) => `
      <div class="leaderboard-entry">
        <span class="leaderboard-rank">${medals[i] || `${i + 1}.`}</span>
        <span class="leaderboard-name">${e.name}</span>
        <span class="leaderboard-stats">🏆${e.wins} · 💰${e.gold}</span>
      </div>`)
    .join('');
}

// ─── DAILY REWARD ────────────────────────────────────────
function claimDaily() {
  const today = new Date().toISOString().slice(0, 10);
  if (game.lastDaily === today) {
    showToast('Ты уже получил награду сегодня!');
    return;
  }
  const reward = 50 + Math.floor(Math.random() * 101);
  game.gold += reward;
  game.lastDaily = today;
  playSound('recruit');
  showToast(`🎁 Получено ${reward} золота!`);
  saveGame();
  updateUI();
}

// ─── SOUND EFFECTS ───────────────────────────────────────
function playSound(name) {
  const audio = document.getElementById(`sfx-${name}`);
  if (!audio) return;
  audio.currentTime = 0;
  audio.play().catch(() => {});
}

// ─── TOAST NOTIFICATIONS ─────────────────────────────────
let toastTimeout = null;
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove('show'), 2200);
}

// Start the game
init();
