"""
Castle Busters — Telegram-бот (полная версия)
Упрощённая пошаговая игра: атакуй замок противника, защищай свой.
Токен указан ниже — замени на свой после проверки.
"""

import asyncio
import json
import random
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ─── CONFIG ────────────────────────────────────────────────
BOT_TOKEN = "889916471:AAFUlcvz7ibEAK4QPNKuKBTyV-28R14e2lA"
WEB_APP_URL = "https://your-domain.com/index.html"  # ← замени на свой URL
ADMIN_ID = 889916471  # ← замени на свой Telegram ID

# ─── LOGGING ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("castle_busters")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ─── GAME DATA (in-memory; для продакшна замени на SQLite) ─
players: dict[int, dict] = {}
battles: dict[int, dict] = {}
leaderboard: list[dict] = []

# ─── UNITS ─────────────────────────────────────────────────
UNITS = {
    "warrior": {
        "name": "⚔️ Воин",
        "attack": 15,
        "defense": 10,
        "hp": 100,
        "cost": 50,
        "emoji": "⚔️",
    },
    "archer": {
        "name": "🏹 Лучник",
        "attack": 20,
        "defense": 5,
        "hp": 70,
        "cost": 70,
        "emoji": "🏹",
    },
    "mage": {
        "name": "🔮 Маг",
        "attack": 35,
        "defense": 3,
        "hp": 50,
        "cost": 120,
        "emoji": "🔮",
    },
    "knight": {
        "name": "🛡️ Рыцарь",
        "attack": 10,
        "defense": 25,
        "hp": 150,
        "cost": 100,
        "emoji": "🛡️",
    },
    "dragon": {
        "name": "🐉 Дракон",
        "attack": 50,
        "defense": 15,
        "hp": 200,
        "cost": 300,
        "emoji": "🐉",
    },
}

# ─── CASTLE LEVELS ─────────────────────────────────────────
CASTLE_LEVELS = {
    1: {"castle_hp": 500, "upgrade_cost": 200},
    2: {"castle_hp": 800, "upgrade_cost": 400},
    3: {"castle_hp": 1200, "upgrade_cost": 800},
    4: {"castle_hp": 1800, "upgrade_cost": 1500},
    5: {"castle_hp": 2500, "upgrade_cost": 3000},
}

# ─── FSM STATES ────────────────────────────────────────────
class GameState(StatesGroup):
    waiting_name = State()
    in_battle = State()
    waiting_action = State()


# ─── HELPER FUNCTIONS ──────────────────────────────────────
def get_or_create_player(user_id: int, username: str = "") -> dict:
    if user_id not in players:
        players[user_id] = {
            "user_id": user_id,
            "username": username,
            "gold": 500,
            "castle_level": 1,
            "castle_hp": CASTLE_LEVELS[1]["castle_hp"],
            "castle_max_hp": CASTLE_LEVELS[1]["castle_hp"],
            "army": {},
            "wins": 0,
            "losses": 0,
            "created_at": datetime.now().isoformat(),
        }
    return players[user_id]


def get_army_power(army: dict) -> dict:
    total_attack = 0
    total_defense = 0
    total_hp = 0
    for unit_key, count in army.items():
        if unit_key in UNITS and count > 0:
            u = UNITS[unit_key]
            total_attack += u["attack"] * count
            total_defense += u["defense"] * count
            total_hp += u["hp"] * count
    return {"attack": total_attack, "defense": total_defense, "hp": total_hp}


def format_player_stats(p: dict) -> str:
    army = get_army_power(p["army"])
    army_str = ""
    for ukey, udata in UNITS.items():
        cnt = p["army"].get(ukey, 0)
        if cnt > 0:
            army_str += f"  {udata['emoji']} {udata['name']}: {cnt} шт.\n"
    if not army_str:
        army_str = "  (армия пуста)"

    return (
        f"🏰 **Замок Насти** — Уровень {p['castle_level']}\n"
        f"❤️ HP замка: {p['castle_hp']}/{p['castle_max_hp']}\n"
        f"💰 Золото: {p['gold']}\n"
        f"⚔️ Атака армии: {army['attack']}\n"
        f"🛡️ Защита армии: {army['defense']}\n"
        f"👥 HP армии: {army['hp']}\n"
        f"🏆 Побед: {p['wins']} | Поражений: {p['losses']}\n"
        f"\n🗡️ **Армия:**\n{army_str}"
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏰 Мой замок", callback_data="menu_castle")
    kb.button(text="🛒 Нанять армию", callback_data="menu_recruit")
    kb.button(text="⚔️ Атаковать", callback_data="menu_attack")
    kb.button(text="📈 Улучшить замок", callback_data="menu_upgrade")
    kb.button(text="🏆 Рейтинг", callback_data="menu_leaderboard")
    kb.button(text="🎮 Играть (Web)", web_app=WebAppInfo(url=WEB_APP_URL))
    kb.button(text="❓ Помощь", callback_data="menu_help")
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def recruit_kb(player_gold: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ukey, udata in UNITS.items():
        affordable = "✅" if player_gold >= udata["cost"] else "❌"
        kb.button(
            text=f"{udata['emoji']} {udata['name']} — {udata['cost']}💰 {affordable}",
            callback_data=f"recruit_{ukey}",
        )
    kb.button(text="⬅️ Назад", callback_data="menu_main")
    kb.adjust(1, 1, 1, 1, 1, 1)
    return kb.as_markup()


def attack_target_kb(player_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    targets = [
        (uid, p) for uid, p in players.items()
        if uid != player_id and p["castle_hp"] > 0
    ]
    random.shuffle(targets)
    for uid, p in targets[:6]:
        army = get_army_power(p["army"])
        kb.button(
            text=f"{p.get('username', 'Игрок')} 🏰{p['castle_level']} ⚔️{army['attack']}",
            callback_data=f"attack_{uid}",
        )
    if not targets:
        kb.button(text="Нет целей для атаки", callback_data="noop")
    kb.button(text="⬅️ Назад", callback_data="menu_main")
    kb.adjust(1, 1, 1, 1, 1, 1, 1)
    return kb.as_markup()


def confirm_attack_kb(target_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ В бой!", callback_data=f"do_attack_{target_id}")
    kb.button(text="⬅️ Отмена", callback_data="menu_attack")
    kb.adjust(2)
    return kb.as_markup()


# ─── BATTLE LOGIC ──────────────────────────────────────────
def simulate_battle(attacker: dict, defender: dict) -> dict:
    att_army = get_army_power(attacker["army"])
    def_army = get_army_power(defender["army"])

    att_power = att_army["attack"] + random.randint(0, 20)
    def_power = def_army["defense"] + def_army["attack"] // 2 + random.randint(0, 15)

    # Урон по замку защитника
    damage_to_def_castle = max(10, att_power - def_army["defense"])

    # Контратака — урон по замку атакующего
    counter_damage = max(5, def_army["attack"] - att_army["defense"] // 2)

    # Потери армии (10-30% от числа юнитов)
    att_losses = {}
    def_losses = {}
    for ukey, count in attacker["army"].items():
        if count > 0:
            lost = max(0, int(count * random.uniform(0.1, 0.3)))
            att_losses[ukey] = lost
    for ukey, count in defender["army"].items():
        if count > 0:
            lost = max(0, int(count * random.uniform(0.1, 0.3)))
            def_losses[ukey] = lost

    # Применяем урон
    defender["castle_hp"] = max(0, defender["castle_hp"] - damage_to_def_castle)
    attacker["castle_hp"] = max(0, attacker["castle_hp"] - counter_damage)

    # Применяем потери
    for ukey, lost in att_losses.items():
        attacker["army"][ukey] = max(0, attacker["army"].get(ukey, 0) - lost)
    for ukey, lost in def_losses.items():
        defender["army"][ukey] = max(0, defender["army"].get(ukey, 0) - lost)

    # Награды
    gold_reward = 0
    victory = False
    if defender["castle_hp"] <= 0:
        victory = True
        gold_reward = random.randint(100, 300) + defender["castle_level"] * 50
        attacker["gold"] += gold_reward
        attacker["wins"] += 1
        defender["losses"] += 1
        # Восстановление замка защитника
        defender["castle_hp"] = defender["castle_max_hp"]
    else:
        # Частичная награда за урон
        gold_reward = random.randint(10, 30)
        attacker["gold"] += gold_reward

    return {
        "victory": victory,
        "damage_dealt": damage_to_def_castle,
        "counter_damage": counter_damage,
        "gold_reward": gold_reward,
        "att_losses": att_losses,
        "def_losses": def_losses,
        "defender_castle_hp": defender["castle_hp"],
        "attacker_castle_hp": attacker["castle_hp"],
    }


def format_battle_result(result: dict, attacker: dict, defender: dict) -> str:
    status = "🎉 **ПОБЕДА!**" if result["victory"] else "⚔️ Бой завершён"
    text = f"{status}\n\n"
    text += f"💥 Урон замку врага: **{result['damage_dealt']}**\n"
    text += f"🛡️ Контратака по твоему замку: **{result['counter_damage']}**\n"
    text += f"💰 Награда: **{result['gold_reward']}** золота\n\n"

    losses_text = ""
    for ukey, lost in result["att_losses"].items():
        if lost > 0:
            losses_text += f"  {UNITS[ukey]['emoji']} Потеряно {UNITS[ukey]['name']}: {lost}\n"
    if not losses_text:
        losses_text = "  Без потерь! 🎯\n"
    text += f"📉 **Твои потери:**\n{losses_text}\n"

    text += f"🏰 HP твоего замка: {result['attacker_castle_hp']}/{attacker['castle_max_hp']}\n"
    text += f"🏰 HP замка врага: {result['defender_castle_hp']}/{defender['castle_max_hp']}"

    if result["victory"]:
        text += "\n\n🔥 Замок врага разрушен! Золото захвачено!"

    return text


# ─── COMMAND HANDLERS ──────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    player = get_or_create_player(user.id, user.username or user.first_name)

    welcome = (
        f"Привет, {user.first_name}! 🏰\n\n"
        f"Добро пожаловать в **Castle Busters**!\n"
        f"Строй замок, нанимай армию и разрушай крепости врагов!\n\n"
        f"🎁 Стартовый бонус: **500 золота**\n"
        f"🏰 Твой замок: **Уровень 1** (HP: 500)\n\n"
        f"Выбери действие:"
    )
    await message.answer(welcome, reply_markup=main_menu_kb(), parse_mode="Markdown")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 **Как играть в Castle Busters**\n\n"
        "1. **🏰 Мой замок** — посмотреть статистику\n"
        "2. **🛒 Нанять армию** — купить юнитов за золото\n"
        "3. **⚔️ Атаковать** — выбрать цель и напасть\n"
        "4. **📈 Улучшить замок** — повысить уровень и HP\n"
        "5. **🏆 Рейтинг** — топ игроков по победам\n"
        "6. **🎮 Играть (Web)** — веб-версия игры\n\n"
        "**Юниты:**\n"
        "⚔️ Воин — сбалансированный, 50💰\n"
        "🏹 Лучник — высокая атака, 70💰\n"
        "🔮 Маг — мощная атака, мало HP, 120💰\n"
        "🛡️ Рыцарь — танк, много HP, 100💰\n"
        "🐉 Дракон — легендарный, 300💰\n\n"
        "**Совет:** Нанимай разную армию — атака и защита одинаково важны!"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb())


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    player = get_or_create_player(message.from_user.id, message.from_user.username or "")
    await message.answer(format_player_stats(player), parse_mode="Markdown", reply_markup=main_menu_kb())


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    uid = message.from_user.id
    if uid in players:
        del players[uid]
    get_or_create_player(uid, message.from_user.username or "")
    await message.answer("🔄 Игра сброшена! Начинаем заново.", reply_markup=main_menu_kb())


@dp.message(Command("top"))
async def cmd_top(message: Message):
    await show_leaderboard(message)


@dp.message(F.text == "/daily")
async def cmd_daily(message: Message):
    player = get_or_create_player(message.from_user.id, message.from_user.username or "")
    today = datetime.now().strftime("%Y-%m-%d")
    last_claim = player.get("last_daily", "")

    if last_claim == today:
        await message.answer("⏰ Ты уже получил награду сегодня! Возвращайся завтра.")
        return

    reward = random.randint(50, 150)
    player["gold"] += reward
    player["last_daily"] = today
    await message.answer(
        f"🎁 Ежедневная награда!\nПолучено: **{reward}** золота!\n"
        f"💰 Текущий баланс: {player['gold']}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


# ─── CALLBACK HANDLERS ─────────────────────────────────────
@dp.callback_query(F.data == "menu_main")
async def cb_main(call: CallbackQuery):
    await call.message.edit_text("🏰 **Castle Busters**\nВыбери действие:", parse_mode="Markdown", reply_markup=main_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "menu_castle")
async def cb_castle(call: CallbackQuery):
    player = get_or_create_player(call.from_user.id, call.from_user.username or "")
    await call.message.edit_text(format_player_stats(player), parse_mode="Markdown", reply_markup=main_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "menu_recruit")
async def cb_recruit(call: CallbackQuery):
    player = get_or_create_player(call.from_user.id, call.from_user.username or "")
    text = (
        "🛒 **Найм армии**\n\n"
        "Выбери юнита для покупки:\n"
        "(цена указана за 1 юнита)\n\n"
        f"💰 Твоё золото: **{player['gold']}**"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=recruit_kb(player["gold"]))
    await call.answer()


@dp.callback_query(F.data.startswith("recruit_"))
async def cb_do_recruit(call: CallbackQuery):
    unit_key = call.data.replace("recruit_", "")
    if unit_key not in UNITS:
        await call.answer("Неизвестный юнит!", show_alert=True)
        return

    player = get_or_create_player(call.from_user.id, call.from_user.username or "")
    unit = UNITS[unit_key]

    if player["gold"] < unit["cost"]:
        await call.answer(f"Не хватает золота! Нужно {unit['cost']}, у тебя {player['gold']}", show_alert=True)
        return

    player["gold"] -= unit["cost"]
    player["army"][unit_key] = player["army"].get(unit_key, 0) + 1

    await call.answer(f"✅ Нанят: {unit['name']}!", show_alert=False)
    await call.message.edit_text(
        f"🛒 **Найм армии**\n\n"
        f"✅ Нанят: {unit['emoji']} {unit['name']}\n"
        f"💰 Осталось золота: {player['gold']}\n\n"
        f"Армия: {unit['emoji']} x{player['army'][unit_key]}",
        parse_mode="Markdown",
        reply_markup=recruit_kb(player["gold"]),
    )


@dp.callback_query(F.data == "menu_attack")
async def cb_attack_menu(call: CallbackQuery):
    player = get_or_create_player(call.from_user.id, call.from_user.username or "")
    army = get_army_power(player["army"])

    if army["attack"] == 0:
        await call.answer("Сначала найми армию!", show_alert=True)
        return

    text = (
        "⚔️ **Выбор цели для атаки**\n\n"
        f"Твоя мощь атаки: {army['attack']}\n"
        f"Твоя защита: {army['defense']}\n\n"
        "Выбери кого атаковать:"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=attack_target_kb(call.from_user.id))
    await call.answer()


@dp.callback_query(F.data.startswith("attack_"))
async def cb_attack_target(call: CallbackQuery):
    target_id = int(call.data.replace("attack_", ""))
    if target_id not in players:
        await call.answer("Игрок не найден!", show_alert=True)
        return

    defender = players[target_id]
    def_army = get_army_power(defender["army"])
    attacker = get_or_create_player(call.from_user.id, call.from_user.username or "")
    att_army = get_army_power(attacker["army"])

    text = (
        f"⚔️ **Подтверждение атаки**\n\n"
        f"🎯 Цель: {defender.get('username', 'Игрок')}\n"
        f"🏰 Замок: Уровень {defender['castle_level']}\n"
        f"❤️ HP замка: {defender['castle_hp']}/{defender['castle_max_hp']}\n"
        f"🛡️ Защита: {def_army['defense']}\n"
        f"⚔️ Атака: {def_army['attack']}\n\n"
        f"— Твоя армия —\n"
        f"⚔️ Атака: {att_army['attack']}\n"
        f"🛡️ Защита: {att_army['defense']}\n\n"
        f"Готов к битве?"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=confirm_attack_kb(target_id))
    await call.answer()


@dp.callback_query(F.data.startswith("do_attack_"))
async def cb_do_attack(call: CallbackQuery):
    target_id = int(call.data.replace("do_attack_", ""))
    if target_id not in players:
        await call.answer("Игрок не найден!", show_alert=True)
        return

    attacker = get_or_create_player(call.from_user.id, call.from_user.username or "")
    defender = players[target_id]

    if attacker["castle_hp"] <= 0:
        attacker["castle_hp"] = attacker["castle_max_hp"]
        await call.answer("Твой замок восстановлен перед боем!", show_alert=True)

    result = simulate_battle(attacker, defender)
    battle_text = format_battle_result(result, attacker, defender)

    await call.message.edit_text(battle_text, parse_mode="Markdown", reply_markup=main_menu_kb())
    await call.answer("Бой завершён!")


@dp.callback_query(F.data == "menu_upgrade")
async def cb_upgrade(call: CallbackQuery):
    player = get_or_create_player(call.from_user.id, call.from_user.username or "")
    current_level = player["castle_level"]
    next_level = current_level + 1

    if next_level > max(CASTLE_LEVELS.keys()):
        await call.answer("Максимальный уровень замка!", show_alert=True)
        return

    upgrade_cost = CASTLE_LEVELS[next_level]["upgrade_cost"]

    text = (
        f"📈 **Улучшение замка**\n\n"
        f"Текущий уровень: **{current_level}**\n"
        f"HP замка: {player['castle_hp']}/{player['castle_max_hp']}\n\n"
        f"⬆️ Следующий уровень: **{next_level}**\n"
        f"🏰 Новый HP: {CASTLE_LEVELS[next_level]['castle_hp']}\n"
        f"💰 Стоимость: {upgrade_cost}\n"
        f"💰 Твоё золото: {player['gold']}\n"
    )

    kb = InlineKeyboardBuilder()
    if player["gold"] >= upgrade_cost:
        kb.button(text=f"✅ Улучшить ({upgrade_cost}💰)", callback_data=f"do_upgrade_{next_level}")
    else:
        kb.button(text=f"❌ Не хватает золота", callback_data="noop")
    kb.button(text="⬅️ Назад", callback_data="menu_main")
    kb.adjust(1, 1)

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("do_upgrade_"))
async def cb_do_upgrade(call: CallbackQuery):
    new_level = int(call.data.replace("do_upgrade_", ""))
    player = get_or_create_player(call.from_user.id, call.from_user.username or "")

    if new_level not in CASTLE_LEVELS:
        await call.answer("Ошибка уровня!", show_alert=True)
        return

    cost = CASTLE_LEVELS[new_level]["upgrade_cost"]
    if player["gold"] < cost:
        await call.answer("Не хватает золота!", show_alert=True)
        return

    player["gold"] -= cost
    player["castle_level"] = new_level
    player["castle_max_hp"] = CASTLE_LEVELS[new_level]["castle_hp"]
    player["castle_hp"] = player["castle_max_hp"]  # Полное восстановление при улучшении

    await call.answer(f"🏰 Замок улучшен до уровня {new_level}!", show_alert=False)
    await call.message.edit_text(
        f"📈 **Замок улучшен!**\n\n"
        f"🏰 Новый уровень: **{new_level}**\n"
        f"❤️ HP замка: {player['castle_hp']}/{player['castle_max_hp']}\n"
        f"💰 Осталось золота: {player['gold']}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


@dp.callback_query(F.data == "menu_leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    await show_leaderboard(call.message, is_callback=True, callback=call)


async def show_leaderboard(message: Message, is_callback: bool = False, callback: CallbackQuery = None):
    sorted_players = sorted(players.values(), key=lambda p: (p["wins"], p["gold"]), reverse=True)
    if not sorted_players:
        text = "🏆 **Рейтинг игроков**\n\nПока нет данных. Сыграй первую битву!"
    else:
        text = "🏆 **Рейтинг игроков**\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(sorted_players[:10]):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} {p.get('username', 'Игрок')} — 👑{p['wins']} побед | 💰{p['gold']}\n"

    if is_callback and callback:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
        await callback.answer()
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb())


@dp.callback_query(F.data == "menu_help")
async def cb_help(call: CallbackQuery):
    text = (
        "📖 **Как играть**\n\n"
        "1️⃣ Нанимай армию за золото\n"
        "2️⃣ Атакуй замки других игроков\n"
        "3️⃣ Получай золото за победы\n"
        "4️⃣ Улучшай свой замок\n"
        "5️⃣ Получай ежедневную награду — /daily\n\n"
        "**Команды:**\n"
        "/start — главное меню\n"
        "/help — помощь\n"
        "/stats — статистика\n"
        "/top — рейтинг\n"
        "/daily — ежедневная награда\n"
        "/reset — сбросить игру"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


# ─── AUTO-HEAL: восстановление HP замка каждые 5 мин ───────
async def auto_heal_task():
    while True:
        await asyncio.sleep(300)  # 5 минут
        for player in players.values():
            if player["castle_hp"] < player["castle_max_hp"]:
                heal = player["castle_max_hp"] // 10  # 10% от макс HP
                player["castle_hp"] = min(player["castle_max_hp"], player["castle_hp"] + heal)
        log.info("Auto-heal: замки восстановлены")


# ─── STARTUP ───────────────────────────────────────────────
async def on_startup():
    log.info("Castle Busters бот запущен!")
    asyncio.create_task(auto_heal_task())


async def main():
    await on_startup()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
