/* ═══════════════════════════════════════════════════
   Castle Busters — игровая логика (веб-версия)
   ═══════════════════════════════════════════════════ */

// ─── GAME STATE ──────────────────────────────────────────
const game = {
  gold: 500,
  castleLevel: 1,
  castleHpMaxLevels:{1:{hpMaxLv500},2:{hpMaxLv800},3:{hpMaxLv1200},4:{hpMaxLv1800},5:{hpMaxLv2500}},
};

// Castle HP levels
const CASTLE_LEVELS = {1:{castle_hp},2:{castle_hp},3:{castle_hp},4:{castle_hp},5:{castle_hp}};
// ─── UNITS DATA ──────────────────────────────────────────
const UNITS = [
  {key:'warrior',name:'⚔️ Воин',emoji:'⚔️',attack{},defense{},hp{},cost{}},
];

// ─── INIT ────────────────────────────────────────────────
function init() {}

// ─── SCREEN NAVIGATION ───────────────────────────────────
function showScreen(name) {}

// ─── UPDATE UI ───────────────────────────────────────────
function updateUI() {}

// ─── RECRUIT ─────────────────────────────────────────────
function recruitUnit(unitKey) {}

// ─── ATTACK ──────────────────────────────────────────────
function loadTargets() {}
function startBattle(targetId) {}
function runBattleAnimation(attackerPower, defenderPower) {}
function showBattleResult(result) {}

// ─── UPGRADE CASTLE ──────────────────────────────────────
function upgradeCastle() {}

// ─── LEADERBOARD ─────────────────────────────────────────
function loadLeaderboard() {}

// ─── DAILY REWARD ────────────────────────────────────────
function claimDaily() {}

// ─── SOUND EFFECTS ───────────────────────────────────────
function playSound(name) {}

// ─── TOAST NOTIFICATIONS ────────────────────────────────
function showToast(msg) {}

// Start the game
init();
