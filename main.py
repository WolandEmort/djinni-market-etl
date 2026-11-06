import re
import time
import csv
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

BASE_URL = "https://djinni.co/salaries/"


def get_all_categories(session: requests.Session) -> list:
    response = session.get(BASE_URL, timeout=15)
    if response.status_code != 200:
        raise Exception(f"Не удалось загрузить страницу. Статус: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
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

    # --- 1. Карточка кандидатов (#candidates_card) ---
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

    # --- 2. Карточка вакансий (#jobs_card) ---
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

    # --- 3. Карточка Индекса Djinni (#djinni_index_card) ---
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


def get_user_filters():
    print("=== Настройка параметров парсинга ===")

    # 1. Запрос формата работы
    print("\nВыберите формат работы:")
    print("1 - Любой (без фильтра по удаленке)")
    print("2 - Только Remote (full_remote)")
    print("3 - Оба варианта (сделать запросы и для Remote, и для 'Любой')")
    wf_choice = input("Введите цифру (по умолчанию 3): ").strip()

    if wf_choice == "1":
        work_formats = [""]
    elif wf_choice == "2":
        work_formats = ["full_remote"]
    else:
        work_formats = ["", "full_remote"]

    # 2. Запрос опыта работы
    valid_exps = ["0", "1", "2", "3", "5"]
    print("\nДоступные года опыта:", valid_exps)
    exp_input = input("Введите нужные значения через запятую (или нажмите Enter для всех): ").strip()

    if not exp_input:
        exp_levels = valid_exps
    else:
        # Разбиваем строку по запятой, убираем пробелы и проверяем наличие в valid_exps
        exp_levels = [x.strip() for x in exp_input.split(",") if x.strip() in valid_exps]

        # Защита от некорректного ввода
        if not exp_levels:
            print("Введены некорректные данные. Будут использованы все доступные года опыта.")
            exp_levels = valid_exps

    print(f"\n[INIT] Настройки приняты. Форматы: {work_formats}, Опыт: {exp_levels}\n")
    return work_formats, exp_levels


def main():
    # Получаем настройки от пользователя
    work_formats, exp_levels = get_user_filters()

    results = []
    columns = [
        "Category", "Experience_Years", "Work_Format",
        "candidates_count", "candidates_diff", "candidates_expected_salary", "candidates_avg_pokes",
        "jobs_count", "jobs_diff", "jobs_salary_range", "jobs_avg_applies",
        "djinni_index", "index_diff", "index_applies_total", "index_pokes_total"
    ]

    with open("djinni_analytics_raw.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        with requests.Session(impersonate="chrome120") as session:
            print("Получение списка категорий...")
            try:
                categories = get_all_categories(session)
                print(f"Найдено категорий: {len(categories)}")
            except Exception as e:
                print(e)
                return

            for category in categories:
                for exp in exp_levels:  # Используем введенный список опыта
                    for wf in work_formats:  # Используем введенный список форматов
                        params = {"category": category, "exp": exp}
                        if wf:
                            params["work_format"] = wf

                        try:
                            response = session.get(BASE_URL, params=params, timeout=15)
                            if response.status_code != 200:
                                print(f"[WARN] Ошибка {response.status_code} по URL: {response.url}")
                                continue

                            parsed_data = parse_salaries_page(response.text)

                            row = {
                                "Category": category,
                                "Experience_Years": "< 1" if exp == "0" else ("5+" if exp == "5" else exp),
                                "Work_Format": wf if wf else "All",
                                **parsed_data
                            }

                            writer.writerow(row)
                            f.flush()

                            results.append(row)

                            print(f"[OK] {category} | Exp: {exp} | Format: {wf or 'All'}")

                        except Exception as e:
                            print(f"[ERROR] Сбой парсинга для {category}, exp={exp}: {str(e)}")

                        time.sleep(0.8)

    df = pd.DataFrame(results)

    numeric_cols = [
        "candidates_count", "jobs_count", "candidates_avg_pokes",
        "jobs_avg_applies", "djinni_index", "index_diff",
        "index_applies_total", "index_pokes_total"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_csv("djinni_analytics_clean.csv", index=False, encoding="utf-8-sig")

    # Безопасное сохранение в Excel
    excel_filename = "djinni_analytics.xlsx"
    try:
        df.to_excel(excel_filename, index=False)
        print(f"\nГотово. Данные сохранены в CSV и {excel_filename}")
    except PermissionError:
        fallback_name = f"djinni_analytics_{int(time.time())}.xlsx"
        df.to_excel(fallback_name, index=False)
        print(f"\n[ВНИМАНИЕ] Файл {excel_filename} был открыт. Данные сохранены в {fallback_name}")
    print("\nГотово. Данные сохранены.")


if __name__ == "__main__":
    main()