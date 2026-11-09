import re
import time
import csv
import os
import logging
import argparse
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
import numpy as np
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "https://djinni.co/salaries/"


def parse_salary_range(val):
    """
    Перетворює рядок '$400 - $700' на кортеж (400.0, 700.0, 550.0).
    Якщо даних немає або вони нульові, повертає (NaN, NaN, NaN).
    """
    if pd.isna(val) or not val:
        return np.nan, np.nan, np.nan

    # Шукаємо всі числа в рядку
    numbers = re.findall(r'\d+', str(val))
    if not numbers:
        return np.nan, np.nan, np.nan

    numbers = [float(n) for n in numbers]

    # Обробка edge case: $0 - $0 (коли вакансій/кандидатів немає)
    if all(n == 0 for n in numbers):
        return np.nan, np.nan, np.nan

    if len(numbers) >= 2:
        s_min, s_max = numbers[0], numbers[1]
    elif len(numbers) == 1:
        s_min = s_max = numbers[0]
    else:
        return np.nan, np.nan, np.nan

    s_mid = (s_min + s_max) / 2
    return s_min, s_max, s_mid

def parse_args():
    parser = argparse.ArgumentParser(description="Djinni Market ETL Extractor")
    parser.add_argument(
        "--exp",
        type=str,
        default="0,1,2,3,5",
        help="Кома-сепарований список років досвіду (0,1,2,3,5)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["all", "remote", "both"],
        default="both",
        help="Формат роботи: all, remote, both"
    )
    return parser.parse_args()


def get_work_formats(format_arg: str) -> list:
    if format_arg == "all":
        return [""]
    elif format_arg == "remote":
        return ["full_remote"]
    return ["", "full_remote"]


def get_all_categories(session: requests.Session) -> list:
    response = session.get(BASE_URL, timeout=15)
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    soup = BeautifulSoup(response.content, "html.parser")
    categories = []

    select_tag = soup.find("select", {"name": "category"})
    if select_tag:
        for option in select_tag.find_all("option"):
            val = option.get("value")
            if val:
                categories.append(val)

    return categories


def safe_get_text(soup, selector, default=None):
    element = soup.select_one(selector)
    if element:
        return element.get_text(strip=True).replace("\xa0", "").replace(" ", "")
    return default


def parse_salaries_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    cand_card = soup.find("div", id="candidates_card")
    if cand_card:
        data["candidates_count"] = safe_get_text(cand_card, ".fs-1")
        data["candidates_diff"] = safe_get_text(cand_card, ".text-diff")

        expected_salary_label = cand_card.find(lambda tag: tag.name == "small" and "Середні очікування" in tag.text)
        if expected_salary_label:
            data["candidates_expected_salary"] = expected_salary_label.find_parent("div", class_="row").find("div",
                                                                                                             class_="col-auto").get_text(
                strip=True).replace("\xa0", " ")

        avg_pokes_label = cand_card.find(lambda tag: tag.name == "small" and "Пропозицій в середньому" in tag.text)
        if avg_pokes_label:
            data["candidates_avg_pokes"] = avg_pokes_label.find_parent("div", class_="row").find("div",
                                                                                                 class_="col-auto").get_text(
                strip=True)

    jobs_card = soup.find("div", id="jobs_card")
    if jobs_card:
        data["jobs_count"] = safe_get_text(jobs_card, ".fs-1")
        data["jobs_diff"] = safe_get_text(jobs_card, ".text-diff")

        jobs_salary_label = jobs_card.find(lambda tag: tag.name == "small" and "Середня вилка" in tag.text)
        if jobs_salary_label:
            data["jobs_salary_range"] = jobs_salary_label.find_parent("div", class_="row").find("div",
                                                                                                class_="col-auto").get_text(
                strip=True).replace("\xa0", " ")

        avg_applies_label = jobs_card.find(lambda tag: tag.name == "small" and "Відгуків в середньому" in tag.text)
        if avg_applies_label:
            data["jobs_avg_applies"] = avg_applies_label.find_parent("div", class_="row").find("div",
                                                                                               class_="col-auto").get_text(
                strip=True)

    index_card = soup.find("div", id="djinni_index_card")
    if index_card:
        data["djinni_index"] = safe_get_text(index_card, ".fs-1")
        diff_raw = safe_get_text(index_card, ".text-diff")
        if diff_raw:
            data["index_diff"] = diff_raw.replace("↓", "-").replace("↑", "+")

        script_tag = index_card.find("script", type="module")
        if script_tag and script_tag.string:
            applies_match = re.search(r"applies:\s*(\d+)", script_tag.string)
            pokes_match = re.search(r"pokes:\s*(\d+)", script_tag.string)
            data["index_applies_total"] = applies_match.group(1) if applies_match else None
            data["index_pokes_total"] = pokes_match.group(1) if pokes_match else None

    return data


def main():
    args = parse_args()

    exp_levels = [x.strip() for x in args.exp.split(",") if x.strip() in ["0", "1", "2", "3", "5"]]
    if not exp_levels:
        logger.warning("Некоректні параметри досвіду. Використовуються дефолтні.")
        exp_levels = ["0", "1", "2", "3", "5"]

    work_formats = get_work_formats(args.format)
    snapshot_date = datetime.now().date().isoformat()

    logger.info(f"Ініціалізація екстракції. Snapshot: {snapshot_date}, Exp: {exp_levels}, Formats: {work_formats}")

    columns = [
        "snapshot_date", "Category", "Experience_Years", "Work_Format",
        "candidates_count", "candidates_diff", "candidates_expected_salary", "candidates_avg_pokes",
        "jobs_count", "jobs_diff", "jobs_salary_range", "jobs_avg_applies",
        "djinni_index", "index_diff", "index_applies_total", "index_pokes_total"
    ]

    raw_file = "djinni_analytics_raw.csv"
    file_exists = os.path.isfile(raw_file)

    results = []

    with open(raw_file, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()

        with requests.Session(impersonate="chrome120") as session:
            try:
                categories = get_all_categories(session)
                logger.info(f"Знайдено категорій: {len(categories)}")
            except Exception as e:
                # ЗМІНЕНО: exc_info=True покаже реальну причину блокування
                logger.error("Критична мережева помилка отримання категорій", exc_info=True)
                return

            for category in categories:
                for exp in exp_levels:
                    for wf in work_formats:
                        params = {"category": category, "exp": exp}
                        if wf:
                            params["work_format"] = wf

                        try:
                            response = session.get(BASE_URL, params=params, timeout=15)
                            if response.status_code != 200:
                                logger.warning(f"HTTP {response.status_code} для {response.url}")
                                continue

                            parsed_data = parse_salaries_page(response.content)

                            row = {
                                "snapshot_date": snapshot_date,
                                "Category": category,
                                "Experience_Years": "< 1" if exp == "0" else ("5+" if exp == "5" else exp),
                                "Work_Format": wf if wf else "All",
                                **parsed_data
                            }

                            writer.writerow(row)
                            f.flush()
                            results.append(row)

                            logger.info(f"Зібрано: {category} | Exp: {exp} | Format: {wf or 'All'}")

                        except Exception as e:
                            logger.error(f"Сбой парсингу {category}, exp={exp}: {e}")

                        time.sleep(0.8)

    # Трансформація даних (базова типізація)
    if not results:
        logger.info("Нових даних не зібрано.")
        return

    df_new = pd.DataFrame(results)

    # 1. Конвертація звичайних числових колонок
    numeric_cols = [
        "candidates_count", "jobs_count", "candidates_avg_pokes",
        "jobs_avg_applies", "djinni_index", "index_diff",
        "index_applies_total", "index_pokes_total"
    ]

    for col in numeric_cols:
        if col in df_new.columns:
            df_new[col] = pd.to_numeric(df_new[col], errors="coerce")

    # 2. Якщо jobs_count або candidates_count дорівнює 0, замінюємо на NaN
    # Це важливо, щоб не псувати статистику нулями там, де даних просто немає
    if "jobs_count" in df_new.columns:
        df_new.loc[df_new["jobs_count"] == 0, "jobs_count"] = np.nan
    if "candidates_count" in df_new.columns:
        df_new.loc[df_new["candidates_count"] == 0, "candidates_count"] = np.nan

    # 3. Розбивка зарплатних вилок на min, max, mid
    if "candidates_expected_salary" in df_new.columns:
        df_new[["cand_salary_min", "cand_salary_max", "cand_salary_mid"]] = (
            df_new["candidates_expected_salary"].apply(parse_salary_range).apply(pd.Series)
        )
        df_new.drop(columns=["candidates_expected_salary"], inplace=True)

    if "jobs_salary_range" in df_new.columns:
        df_new[["jobs_salary_min", "jobs_salary_max", "jobs_salary_mid"]] = (
            df_new["jobs_salary_range"].apply(parse_salary_range).apply(pd.Series)
        )
        df_new.drop(columns=["jobs_salary_range"], inplace=True)

    # Перезаписуємо clean-файл повністю
    df_new.columns = [col.lower() for col in df_new.columns]

    # 2. Налаштування підключення (заміни на свої дані)
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_name]):
        logger.error("Не знайдено змінні середовища для підключення до БД (.env).")
        return

    db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            # 3. Зберігаємо дані у тимчасову таблицю
            temp_table = "temp_djinni_snapshot"
            df_new.to_sql(temp_table, conn, if_exists="replace", index=False)

            # 4. Робимо UPSERT (INSERT ... ON CONFLICT DO UPDATE)
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

            # Очищуємо тимчасову таблицю
            conn.execute(text(f"DROP TABLE {temp_table};"))

        logger.info("ETL процес завершено. Дані успішно завантажені в PostgreSQL.")

    except Exception as e:
        logger.error("Помилка при завантаженні даних у базу", exc_info=True)


if __name__ == "__main__":
    main()