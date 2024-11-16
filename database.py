import aiosqlite
import pandas as pd
from datetime import datetime, timedelta
import logging

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    proteins REAL,
                    fats REAL,
                    carbs REAL,
                    calories REAL,
                    weight REAL,
                    price REAL,
                    last_updated DATE
                )
            """)
            await db.commit()
            logger.info("Database initialized.")

    async def load_products(self) -> pd.DataFrame:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM products") as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                products_df = pd.DataFrame(rows, columns=columns)
                logger.info("Products loaded from database.")
        return products_df

    async def save_products(self, products_df: pd.DataFrame):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM products")
            products_df['last_updated'] = datetime.now().date().isoformat()
            await db.executemany(
                """
                INSERT INTO products 
                (name, proteins, fats, carbs, calories, weight, price, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                products_df[['name', 'proteins', 'fats', 'carbs', 'calories', 'weight', 'price', 'last_updated']].itertuples(index=False, name=None)
            )
            await db.commit()
            logger.info("Products saved to database.")

    async def needs_update(self) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT MAX(last_updated) FROM products") as cursor:
                result = await cursor.fetchone()
                if result and result[0]:
                    last_updated = datetime.strptime(result[0], '%Y-%m-%d').date()
                    needs = (datetime.now().date() - last_updated) > timedelta(days=7)
                    logger.info(f"Database needs update: {needs}")
                    return needs
                logger.info("Database needs update: True (no records found).")
                return True
