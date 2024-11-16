import math
import re
import logging
from typing import List, Optional, Dict, Tuple, Set

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StateFilter

import pandas as pd

from database import Database
from scraper import Scraper
from optimization import (
    calculate_bmr,
    calculate_bmr_harris_benedict,
    calculate_daily_calories,
    calculate_macros,
    format_diet_text,
    find_all_solutions,
)
from keyboards import (
    yes_no_inline_keyboard,
    gender_inline_keyboard,
    activity_level_inline_keyboard,
    goal_inline_keyboard,
    confirm_inline_keyboard,
)

DATABASE = "products.db"

logger = logging.getLogger(__name__)

# Define FSM States
class Form(StatesGroup):
    weight = State()
    height = State()
    age = State()
    gender = State()
    body_fat_known = State()
    body_fat_percentage = State()
    waist = State()
    neck = State()
    hip = State()
    activity_level = State()
    goal = State()
    excluded_products = State()
    reviewing_day = State()

# Initialize Dispatcher and Router
router = Router()

@router.message(Command(commands=['start']))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Form.weight)
    await message.answer(
        "👋 Привет! Я помогу тебе составить персонализированный недельный рацион питания.\n\n"
        "Если захочешь прервать процесс, отправь команду /cancel.\n\n"
        "📊 <b>Шаг 1 из 7</b>\n"
        "Введите ваш вес в килограммах (например, 70.5):"
    )

@router.message(Command(commands=['help']))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Помощь</b>\n\n"
        "Я помогу вам составить персонализированный недельный рацион питания на основе ваших параметров и целей.\n\n"
        "Просто следуйте моим инструкциям и отвечайте на вопросы.\n\n"
        "Доступные команды:\n"
        "/start - начать заново\n"
        "/cancel - отменить текущий процесс"
    )

@router.message(Command(commands=['cancel']))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Процесс отменён. Чтобы начать заново, отправьте /start.", reply_markup=ReplyKeyboardRemove())

@router.message(StateFilter(Form.weight))
async def process_weight(message: Message, state: FSMContext):
    try:
        user_weight = float(message.text.strip().replace(',', '.'))
        if not (30 <= user_weight <= 300):
            raise ValueError("Вес вне допустимого диапазона.")
        await state.update_data(weight=user_weight)
        await state.set_state(Form.height)
        await message.answer(
            "📏 <b>Шаг 2 из 7</b>\n"
            "Введите ваш рост в сантиметрах (например, 175):"
        )
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение веса (число от 30 до 300 кг).")

@router.message(StateFilter(Form.height))
async def process_height(message: Message, state: FSMContext):
    try:
        user_height = float(message.text.strip().replace(',', '.'))
        if not (100 <= user_height <= 250):
            raise ValueError("Рост вне допустимого диапазона.")
        await state.update_data(height=user_height)
        await state.set_state(Form.age)
        await message.answer(
            "🎂 <b>Шаг 3 из 7</b>\n"
            "Введите ваш возраст (например, 25):"
        )
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение роста (число от 100 до 250 см).")

@router.message(StateFilter(Form.age))
async def process_age(message: Message, state: FSMContext):
    try:
        user_age = int(re.findall(r'\d+', message.text.strip())[0])
        if not (5 <= user_age <= 120):
            raise ValueError("Возраст вне допустимого диапазона.")
        await state.update_data(age=user_age)
        await state.set_state(Form.gender)
        await message.answer(
            "🚻 <b>Шаг 4 из 7</b>\n"
            "Выберите ваш пол:",
            reply_markup=gender_inline_keyboard()
        )
    except (ValueError, IndexError):
        await message.answer("⚠️ Пожалуйста, введите корректное значение возраста (число от 5 до 120).")

@router.callback_query(StateFilter(Form.gender), lambda c: c.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    await state.set_state(Form.body_fat_known)
    await callback.message.edit_text(
        "🔍 <b>Шаг 5 из 7</b>\n"
        "Известен ли вам процент жира в вашем организме?",
        reply_markup=yes_no_inline_keyboard()
    )

@router.callback_query(StateFilter(Form.body_fat_known), lambda c: c.data in ["yes", "no"])
async def process_body_fat_known(callback: CallbackQuery, state: FSMContext):
    answer = callback.data
    if answer == "yes":
        await state.set_state(Form.body_fat_percentage)
        await callback.message.edit_text(
            "💯 Введите процент жира в вашем организме (например, 15.5):"
        )
    else:
        data = await state.get_data()
        if data.get('gender') == 'female':
            await state.set_state(Form.hip)
            await callback.message.edit_text("📏 Введите обхват бёдер в сантиметрах:")
        else:
            await state.set_state(Form.waist)
            await callback.message.edit_text("📏 Введите обхват талии в сантиметрах:")

@router.message(StateFilter(Form.body_fat_percentage))
async def process_body_fat_percentage(message: Message, state: FSMContext):
    try:
        body_fat_percentage = float(message.text.strip().replace(',', '.'))
        if not (0 < body_fat_percentage < 100):
            raise ValueError("Процент жира вне допустимого диапазона.")
        await state.update_data(body_fat_percentage=body_fat_percentage)
        await message.answer(f'📊 Ваш приблизительный процент жира в организме: {body_fat_percentage:.2f}%')
        await ask_activity_level(message, state)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение процента жира (число от 0 до 100).")

@router.message(StateFilter(Form.waist))
async def process_waist(message: Message, state: FSMContext):
    try:
        waist = float(message.text.strip().replace(',', '.'))
        if not (30 <= waist <= 200):
            raise ValueError("Обхват талии вне допустимого диапазона.")
        await state.update_data(waist=waist)
        await state.set_state(Form.neck)
        await message.answer("📏 Введите обхват шеи в сантиметрах:")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение обхвата талии (число от 30 до 200 см).")

@router.message(StateFilter(Form.neck))
async def process_neck(message: Message, state: FSMContext):
    try:
        neck = float(message.text.strip().replace(',', '.'))
        if not (10 <= neck <= 100):
            raise ValueError("Обхват шеи вне допустимого диапазона.")
        await state.update_data(neck=neck)
        data = await state.get_data()
        if data['gender'] == 'female':
            await state.set_state(Form.hip)
            await message.answer("📏 Введите обхват бёдер в сантиметрах:")
        else:
            await calculate_body_fat_percentage(state, message)
            await ask_activity_level(message, state)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение обхвата шеи (число от 10 до 100 см).")

@router.message(StateFilter(Form.hip))
async def process_hip(message: Message, state: FSMContext):
    try:
        hip = float(message.text.strip().replace(',', '.'))
        if not (20 <= hip <= 200):
            raise ValueError("Обхват бёдер вне допустимого диапазона.")
        await state.update_data(hip=hip)
        # Calculate body fat percentage for females
        await calculate_body_fat_percentage(state, message)
        await ask_activity_level(message, state)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение обхвата бёдер (число от 20 до 200 см).")

async def calculate_body_fat_percentage(state: FSMContext, message: Message):
    data = await state.get_data()
    try:
        if data['gender'] == 'male':
            waist = data['waist']
            neck = data['neck']
            height = data['height']
            if waist - neck <= 0 or height <= 0:
                raise ValueError
            body_fat_percentage = 495 / (
                1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)
            ) - 450
        else:
            waist = data['waist']
            neck = data['neck']
            hip = data.get('hip')
            height = data['height']
            if waist + hip - neck <= 0 or height <= 0:
                raise ValueError
            body_fat_percentage = 495 / (
                1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height)
            ) - 450
        body_fat_percentage = max(0, min(body_fat_percentage, 100))  # Clamp between 0 and 100
        await state.update_data(body_fat_percentage=body_fat_percentage)
        await message.answer(f'📊 Ваш приблизительный процент жира в организме: {body_fat_percentage:.2f}%')
    except (ValueError, KeyError):
        await message.answer("⚠️ Некорректные данные для расчёта процента жира. Пожалуйста, проверьте введённые значения.")
        await state.clear()

async def ask_activity_level(message: Message, state: FSMContext):
    await state.set_state(Form.activity_level)
    await message.answer(
        "🏃 <b>Шаг 6 из 7</b>\n"
        "Выберите уровень активности:",
        reply_markup=activity_level_inline_keyboard()
    )

@router.callback_query(StateFilter(Form.activity_level), lambda c: c.data.startswith("activity_"))
async def process_activity_level(callback: CallbackQuery, state: FSMContext):
    activity_levels = {
        "activity_sedentary": "sedentary",
        "activity_light": "lightly_active",
        "activity_moderate": "moderately_active",
        "activity_high": "very_active",
        "activity_extra": "extra_active",
    }
    activity_level = activity_levels.get(callback.data)
    if activity_level:
        await state.update_data(activity_level=activity_level)
        await state.set_state(Form.goal)
        await callback.message.edit_text(
            "🎯 <b>Шаг 7 из 7</b>\n"
            "Выберите вашу цель:",
            reply_markup=goal_inline_keyboard()
        )
    else:
        await callback.answer("Пожалуйста, выберите уровень активности от 1 до 5.")

@router.callback_query(StateFilter(Form.goal), lambda c: c.data.startswith("goal_"))
async def process_goal(callback: CallbackQuery, state: FSMContext):
    goals = {
        "goal_lose_weight": "lose_weight",
        "goal_maintain_weight": "maintain_weight",
        "goal_gain_weight": "gain_weight",
    }
    goal = goals.get(callback.data)
    if goal:
        await state.update_data(goal=goal)
        await state.set_state(Form.excluded_products)
        await callback.message.edit_text(
            "🍽 Введите названия продуктов, которые вы не хотите видеть в рационе (через запятую), или отправьте 'нет'."
        )
    else:
        await callback.answer("Пожалуйста, выберите цель из предложенных.")

@router.message(StateFilter(Form.excluded_products))
async def process_excluded_products(message: Message, state: FSMContext):
    excluded_products = (
        [name.strip() for name in message.text.split(",")]
        if message.text.lower().strip() != "нет"
        else []
    )
    await state.update_data(excluded_products=excluded_products)
    await message.answer(
        "⏳ Спасибо! Начинаю составление вашего недельного рациона...\nЭто может занять несколько минут.",
        reply_markup=ReplyKeyboardRemove(),
    )

    db = Database(DATABASE)
    await db.initialize()

    needs_update = await db.needs_update()
    if needs_update:
        logger.info("Обновление данных о продуктах...")
        async with Scraper() as scraper:
            products_df = await scraper.parse_products()
        if not products_df.empty:
            await db.save_products(products_df)
            logger.info("Данные о продуктах обновлены.")
        else:
            await message.answer("⚠️ Не удалось получить данные о продуктах.")
            await state.clear()
            return
    else:
        logger.info("Загрузка данных о продуктах из базы данных.")
        products_df = await db.load_products()

    if products_df.empty:
        await message.answer("⚠️ Не удалось получить данные о продуктах.")
        await state.clear()
        return

    await state.update_data(products_df=products_df)
    await generate_weekly_plan(message, state)

async def generate_weekly_plan(message: Message, state: FSMContext):
    data = await state.get_data()
    proteins_target = data.get('proteins_target')
    fats_target = data.get('fats_target')
    carbs_target = data.get('carbs_target')
    daily_calories = data.get('daily_calories')

    if not all([proteins_target, fats_target, carbs_target, daily_calories]):
        # Perform calculations
        weight = data['weight']
        body_fat_percentage = data.get('body_fat_percentage')
        gender = data['gender']
        height = data['height']
        age = data['age']
        activity_level = data['activity_level']
        goal = data['goal']

        if body_fat_percentage is not None:
            bmr = calculate_bmr(weight, body_fat_percentage)
        else:
            bmr = calculate_bmr_harris_benedict(gender, weight, height, age)

        daily_calories = calculate_daily_calories(bmr, activity_level)
        proteins_target, fats_target, carbs_target = calculate_macros(weight, daily_calories, goal)

        await state.update_data(
            proteins_target=proteins_target,
            fats_target=fats_target,
            carbs_target=carbs_target,
            daily_calories=daily_calories
        )

    await message.answer(
        f"📊 <b>Ваши ежедневные цели:</b>\n"
        f"Калории: {daily_calories:.2f} ккал\n"
        f"Белки: {proteins_target:.2f} г\n"
        f"Жиры: {fats_target:.2f} г\n"
        f"Углеводы: {carbs_target:.2f} г"
    )

    # Initialize weekly plan
    weekly_plan = []
    await state.update_data(weekly_plan=weekly_plan, current_day=1, rejected_solutions=set(), attempts={})

    # Proceed to first day
    await state.set_state(Form.reviewing_day)
    await present_day_plan(message, state)

async def present_day_plan(message: Message, state: FSMContext):
    data = await state.get_data()
    current_day = data['current_day']
    weekly_plan = data['weekly_plan']
    rejected_solutions = data.get('rejected_solutions', set())
    attempts = data.get('attempts', {})
    products_df = data['products_df']
    proteins_target = data['proteins_target']
    fats_target = data['fats_target']
    carbs_target = data['carbs_target']
    daily_calories = data['daily_calories']
    excluded_products = data['excluded_products']

    solutions = await find_all_solutions(
        products_df,
        proteins_target,
        fats_target,
        carbs_target,
        daily_calories,
        excluded_products,
        rejected_solutions,
        day=current_day
    )

    if solutions:
        sol = solutions[0]
        diet = sol['products']
        await state.update_data(current_solution=sol)
        diet_text = format_diet_text(
            diet,
            proteins_target,
            fats_target,
            carbs_target,
            daily_calories,
            sol['total_cost'],
            current_day
        )
        await message.answer(
            f"{diet_text}\n\nВы принимаете этот рацион?",
            reply_markup=confirm_inline_keyboard()
        )
    else:
        await message.answer(f"⚠️ Не удалось составить рацион на день {current_day}.")
        weekly_plan.append({
            'day': current_day,
            'diet': None,
            'total_cost': 0
        })
        if current_day < 7:
            await state.update_data(current_day=current_day + 1, weekly_plan=weekly_plan)
            await present_day_plan(message, state)
        else:
            await show_final_plan(message, state)

@router.callback_query(StateFilter(Form.reviewing_day), lambda c: c.data in ["accept", "reject"])
async def process_day_review(callback: CallbackQuery, state: FSMContext):
    user_response = callback.data
    data = await state.get_data()
    current_day = data['current_day']
    weekly_plan = data.get('weekly_plan', [])
    rejected_solutions = data.get('rejected_solutions', set())
    attempts = data.get('attempts', {})
    current_solution = data.get('current_solution')

    if user_response == 'accept':
        # Accept the diet
        weekly_plan.append({
            'day': current_day,
            'diet': current_solution['products'],
            'total_cost': current_solution['total_cost']
        })
    else:
        # Reject the diet
        rejected_solutions.add(current_solution['ids'])  # ids уже кортеж
        attempts[current_day] = attempts.get(current_day, 0) + 1
        if attempts[current_day] < 5:
            await state.update_data(rejected_solutions=rejected_solutions, attempts=attempts)
            await callback.message.edit_text("🔄 Попробуем другой вариант...")
            await present_day_plan(callback.message, state)
            return
        else:
            await callback.message.edit_text(f"⚠️ Не удалось найти подходящий рацион на день {current_day}.")
            weekly_plan.append({
                'day': current_day,
                'diet': None,
                'total_cost': 0
            })

    # Update state
    await state.update_data(weekly_plan=weekly_plan, rejected_solutions=rejected_solutions, attempts=attempts)

    # Proceed to next day or finish
    if current_day < 7:
        await state.update_data(current_day=current_day + 1)
        await present_day_plan(callback.message, state)
    else:
        await show_final_plan(callback.message, state)

async def show_final_plan(message: Message, state: FSMContext):
    data = await state.get_data()
    weekly_plan = data.get('weekly_plan', [])
    total_cost = sum(day['total_cost'] for day in weekly_plan)

    final_text = "📅 <b>Ваш недельный план питания:</b>\n\n"
    for day in weekly_plan:
        day_num = day['day']
        diet = day['diet']
        if diet is not None:
            diet_text = format_diet_text(
                diet,
                data['proteins_target'],
                data['fats_target'],
                data['carbs_target'],
                data['daily_calories'],
                day['total_cost'],
                day_num
            )
            final_text += f"{diet_text}\n\n"
        else:
            final_text += f"🍽 <b>Рацион на день {day_num}:</b>\n\n⚠️ Не удалось составить рацион.\n\n"

    final_text += f"<b>Общая стоимость недели: {total_cost:.2f}₽</b>"

    await message.answer(final_text)
    await state.clear()
