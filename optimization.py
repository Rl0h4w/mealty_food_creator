import math
import logging
from typing import List, Dict, Set, Tuple, Optional
import re
import pandas as pd
from pulp import (
    LpProblem,
    LpVariable,
    LpMinimize,
    LpStatus,
    lpSum,
    PULP_CBC_CMD,
)

logger = logging.getLogger(__name__)

def calculate_bmr(weight: float, body_fat_percentage: float) -> float:
    """
    Calculate Basal Metabolic Rate (BMR) based on weight and body fat percentage.

    Args:
        weight (float): Weight in kilograms.
        body_fat_percentage (float): Body fat percentage.

    Returns:
        float: Calculated BMR.
    """
    body_fat_decimal = body_fat_percentage / 100
    lean_body_mass = weight * (1 - body_fat_decimal)
    bmr = 370 + (21.6 * lean_body_mass)
    logger.debug(f"Calculated BMR: {bmr}")
    return bmr

def calculate_bmr_harris_benedict(gender: str, weight: float, height: float, age: int) -> float:
    """
    Calculate Basal Metabolic Rate (BMR) using the Harris-Benedict equation.

    Args:
        gender (str): 'male' or 'female'.
        weight (float): Weight in kilograms.
        height (float): Height in centimeters.
        age (int): Age in years.

    Returns:
        float: Calculated BMR.
    """
    if gender == "male":
        bmr = 88.36 + (13.4 * weight) + (4.8 * height) - (5.7 * age)
    else:
        bmr = 447.6 + (9.2 * weight) + (3.1 * height) - (4.3 * age)
    logger.debug(f"Calculated BMR (Harris-Benedict): {bmr}")
    return bmr

def calculate_daily_calories(bmr: float, activity_level: str) -> float:
    """
    Calculate daily caloric needs based on BMR and activity level.

    Args:
        bmr (float): Basal Metabolic Rate.
        activity_level (str): Activity level keyword.

    Returns:
        float: Daily caloric needs.
    """
    activity_multipliers = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9,
    }
    multiplier = activity_multipliers.get(activity_level, 1.2)
    daily_calories = bmr * multiplier
    logger.debug(f"Calculated daily calories: {daily_calories}")
    return daily_calories

def calculate_macros(weight: float, daily_calories: float, goal: str) -> Tuple[float, float, float]:
    """
    Calculate daily macronutrient targets based on weight, caloric needs, and goal.

    Args:
        weight (float): Weight in kilograms.
        daily_calories (float): Daily caloric needs.
        goal (str): 'lose_weight', 'maintain_weight', or 'gain_weight'.

    Returns:
        Tuple[float, float, float]: Protein, fat, and carbohydrate targets in grams.
    """
    if goal == "lose_weight":
        adjusted_calories = daily_calories - 500
        protein = 2.0 * weight
    elif goal == "gain_weight":
        adjusted_calories = daily_calories + 500
        protein = 1.6 * weight
    else:  # maintain_weight
        adjusted_calories = daily_calories
        protein = 1.4 * weight

    fat = 1.0 * weight

    calories_from_protein = protein * 4
    calories_from_fat = fat * 9
    remaining_calories = adjusted_calories - (calories_from_protein + calories_from_fat)
    carbs = remaining_calories / 4 if remaining_calories > 0 else 0

    logger.debug(f"Calculated macros - Protein: {protein}, Fat: {fat}, Carbs: {carbs}")
    return protein, fat, carbs

def format_diet_text(
    diet_df: pd.DataFrame,
    proteins_target: float,
    fats_target: float,
    carbs_target: float,
    daily_calories: float,
    total_cost: float,
    day: int
) -> str:
    """
    Format the diet plan into a readable text format.

    Args:
        diet_df (pd.DataFrame): DataFrame containing diet products and quantities.
        proteins_target (float): Target protein intake.
        fats_target (float): Target fat intake.
        carbs_target (float): Target carbohydrate intake.
        daily_calories (float): Target daily calories.
        total_cost (float): Total cost of the diet for the day.
        day (int): Day number.

    Returns:
        str: Formatted diet plan text.
    """
    total_proteins = (diet_df['proteins'] * diet_df['quantity']).sum()
    total_fats = (diet_df['fats'] * diet_df['quantity']).sum()
    total_carbs = (diet_df['carbs'] * diet_df['quantity']).sum()
    total_calories = (diet_df['calories'] * diet_df['quantity']).sum()

    text_lines = [
        f"🍽 <b>Рацион на день {day}:</b>\n",
    ]

    for _, row in diet_df.iterrows():
        text_lines.append(f"- {row['name']}: {int(row['quantity'])} порц. (Цена: {row['price']}₽)")

    text_lines.extend([
        "\n<b>Итого:</b>",
        f"Белки: {total_proteins:.2f} г (Цель: {proteins_target:.2f} г)",
        f"Жиры: {total_fats:.2f} г (Цель: {fats_target:.2f} г)",
        f"Углеводы: {total_carbs:.2f} г (Цель: {carbs_target:.2f} г)",
        f"Калории: {total_calories:.2f} ккал (Цель: {daily_calories:.2f} ккал)",
        f"Общая стоимость: {total_cost:.2f}₽"
    ])

    diet_text = "\n".join(text_lines)
    logger.debug(f"Formatted diet text for day {day}.")
    return diet_text

async def find_all_solutions(
    products_df: pd.DataFrame,
    proteins_target: float,
    fats_target: float,
    carbs_target: float,
    daily_calories: float,
    excluded_products: List[str] = [],
    rejected_solutions: Set[Tuple[int, ...]] = set(),
    day: Optional[int] = None
) -> List[Dict]:
    """
    Find multiple diet solutions that meet the nutritional targets while minimizing cost.

    Args:
        products_df (pd.DataFrame): DataFrame containing product details.
        proteins_target (float): Daily protein target in grams.
        fats_target (float): Daily fat target in grams.
        carbs_target (float): Daily carbohydrate target in grams.
        daily_calories (float): Daily caloric target.
        excluded_products (List[str], optional): List of product names to exclude.
        rejected_solutions (Set[Tuple[int, ...]], optional): Set of previously rejected solution indices.
        day (Optional[int], optional): Current day number for logging purposes.

    Returns:
        List[Dict]: List of diet solutions with product quantities and total cost.
    """
    solutions = []
    deviation = 0.05  # 5% deviation
    max_solutions = 5
    attempt_limit = 50  # Increased to allow more attempts if needed
    attempts = 0

    logger.info(f"Starting optimization for day {day}.")

    # Exclude products based on user input
    if excluded_products:
        pattern = '|'.join(map(re.escape, excluded_products))
        initial_count = len(products_df)
        products_df = products_df[~products_df['name'].str.contains(pattern, case=False, na=False)]
        logger.info(f"Excluded {initial_count - len(products_df)} products based on user preferences.")

    # Reset index for pulp variable mapping
    products_df = products_df.reset_index(drop=True)
    num_products = len(products_df)
    logger.info(f"Number of products available for optimization: {num_products}")

    # Precompute pulp variables outside the loop to save time
    product_vars = {
        i: LpVariable(f"Product_{i}", lowBound=0, upBound=3, cat='Integer')  # Maximum 3 portions
        for i in products_df.index
    }

    while len(solutions) < max_solutions and attempts < attempt_limit:
        prob = LpProblem(f"Diet_Optimization_Day_{day}", LpMinimize)

        # Objective Function: Minimize total cost
        prob += lpSum([products_df.loc[i, 'price'] * product_vars[i] for i in products_df.index]), "Total_Cost"

        # Nutrient Constraints with ±5% deviation
        prob += lpSum([products_df.loc[i, 'proteins'] * product_vars[i] for i in products_df.index]) >= proteins_target * (1 - deviation), "Min_Proteins"
        prob += lpSum([products_df.loc[i, 'proteins'] * product_vars[i] for i in products_df.index]) <= proteins_target * (1 + deviation), "Max_Proteins"

        prob += lpSum([products_df.loc[i, 'fats'] * product_vars[i] for i in products_df.index]) >= fats_target * (1 - deviation), "Min_Fats"
        prob += lpSum([products_df.loc[i, 'fats'] * product_vars[i] for i in products_df.index]) <= fats_target * (1 + deviation), "Max_Fats"

        prob += lpSum([products_df.loc[i, 'carbs'] * product_vars[i] for i in products_df.index]) >= carbs_target * (1 - deviation), "Min_Carbs"
        prob += lpSum([products_df.loc[i, 'carbs'] * product_vars[i] for i in products_df.index]) <= carbs_target * (1 + deviation), "Max_Carbs"

        prob += lpSum([products_df.loc[i, 'calories'] * product_vars[i] for i in products_df.index]) >= daily_calories * (1 - deviation), "Min_Calories"
        prob += lpSum([products_df.loc[i, 'calories'] * product_vars[i] for i in products_df.index]) <= daily_calories * (1 + deviation), "Max_Calories"

        # Avoid Rejected Solutions
        for idx, rejected in enumerate(rejected_solutions):
            prob += lpSum([product_vars[i] for i in rejected]) <= len(rejected) - 1, f"Avoid_Solution_{idx}"

        # Solve the problem
        solver = PULP_CBC_CMD(msg=False, timeLimit=10)
        prob.solve(solver)

        if LpStatus[prob.status] == 'Optimal':
            quantities = [int(product_vars[i].varValue) for i in products_df.index]
            products_df['quantity'] = quantities
            total_cost = (products_df['price'] * products_df['quantity']).sum()
            selected_products = products_df[products_df['quantity'] > 0].copy()
            solution_ids = tuple(sorted(selected_products.index.tolist()))

            logger.debug(f"Solution #{len(solutions)+1}: {solution_ids} with total cost {total_cost:.2f}₽")

            if solution_ids in rejected_solutions:
                logger.debug("Solution already rejected. Skipping.")
                attempts += 1
                continue

            # Add the new solution
            solution = {
                'products': selected_products,
                'total_cost': total_cost,
                'quantities': quantities,
                'ids': solution_ids
            }
            solutions.append(solution)
            rejected_solutions.add(solution_ids)
            logger.info(f"Found solution #{len(solutions)} for day {day}.")
        else:
            logger.warning(f"No optimal solution found on attempt {attempts+1} for day {day}.")
            break

        attempts += 1

    if not solutions:
        logger.error(f"No solutions found for day {day} after {attempt_limit} attempts.")
    else:
        logger.info(f"Total solutions found for day {day}: {len(solutions)}")

    return solutions
