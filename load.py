import os
import time
from sqlalchemy import create_engine, text
import pandas as pd
from config import logger


def load_data(df: pd.DataFrame):
    """Завантажує трансформований DataFrame в PostgreSQL через UPSERT."""
    if df.empty:
        logger.info("Немає даних для завантаження в базу.")
        return

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_name]):
        logger.error("Відсутні змінні середовища для БД (.env).")
        return

    db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(db_url)

    # Генерація унікального імені для тимчасової таблиці
    temp_table = f"temp_djinni_snapshot_{int(time.time())}"

    try:
        with engine.begin() as conn:
            df.to_sql(temp_table, conn, if_exists="replace", index=False)

            upsert_query = text(f"""
                INSERT INTO djinni_market_snapshot (
                    snapshot_date, category, experience_years, work_format,
                    candidates_count, candidates_diff, candidates_avg_pokes,
                    jobs_count, jobs_diff, jobs_avg_applies,
                    djinni_index, index_diff, index_applies_total, index_pokes_total,
                    cand_salary_min, cand_salary_max, cand_salary_mid,
                    jobs_salary_min, jobs_salary_max, jobs_salary_mid
                )
                SELECT 
                    snapshot_date::date, category, experience_years, work_format,
                    candidates_count, candidates_diff, candidates_avg_pokes,
                    jobs_count, jobs_diff, jobs_avg_applies,
                    djinni_index, index_diff, index_applies_total, index_pokes_total,
                    cand_salary_min, cand_salary_max, cand_salary_mid,
                    jobs_salary_min, jobs_salary_max, jobs_salary_mid
                FROM {temp_table}
                ON CONFLICT (snapshot_date, category, experience_years, work_format) 
                DO UPDATE SET
                    candidates_count = EXCLUDED.candidates_count,
                    candidates_diff = EXCLUDED.candidates_diff,
                    candidates_avg_pokes = EXCLUDED.candidates_avg_pokes,
                    jobs_count = EXCLUDED.jobs_count,
                    jobs_diff = EXCLUDED.jobs_diff,
                    jobs_avg_applies = EXCLUDED.jobs_avg_applies,
                    djinni_index = EXCLUDED.djinni_index,
                    index_diff = EXCLUDED.index_diff,
                    index_applies_total = EXCLUDED.index_applies_total,
                    index_pokes_total = EXCLUDED.index_pokes_total,
                    cand_salary_min = EXCLUDED.cand_salary_min,
                    cand_salary_max = EXCLUDED.cand_salary_max,
                    cand_salary_mid = EXCLUDED.cand_salary_mid,
                    jobs_salary_min = EXCLUDED.jobs_salary_min,
                    jobs_salary_max = EXCLUDED.jobs_salary_max,
                    jobs_salary_mid = EXCLUDED.jobs_salary_mid;
            """)
            conn.execute(upsert_query)
            conn.execute(text(f"DROP TABLE {temp_table};"))

        logger.info(f"ETL процес успішний: оброблено {len(df)} рядків.")

    except Exception as e:
        logger.error("Помилка при виконанні Load-стадії БД.", exc_info=True)