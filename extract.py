import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from config import BASE_URL, logger


def safe_get_text(soup, selector, default=None):
    element = soup.select_one(selector)
    if element:
        return element.get_text(strip=True).replace("\xa0", "").replace(" ", "")
    return default


def fetch_with_retry(session, url, params=None, max_retries=3, delay=1.5):
    for attempt in range(max_retries):
        try:
            response = session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response
            logger.warning(f"HTTP {response.status_code} для {response.url} (Спроба {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"Мережева помилка: {e} (Спроба {attempt + 1}/{max_retries})")
        time.sleep(delay)
    return None


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


def extract_data(exp_levels: list, work_formats: list) -> list[dict]:
    snapshot_date = datetime.now().date().isoformat()
    results = []

    with requests.Session(impersonate="chrome120") as session:
        response = fetch_with_retry(session, BASE_URL)
        if not response:
            logger.error("Критична помилка: не вдалося завантажити базову сторінку категорій.")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        categories = [opt.get("value") for opt in soup.find("select", {"name": "category"}).find_all("option") if
                      opt.get("value")]
        logger.info(f"Знайдено категорій: {len(categories)}")

        for category in categories:
            for exp in exp_levels:
                for wf in work_formats:
                    params = {"category": category, "exp": exp}
                    if wf: params["work_format"] = wf

                    resp = fetch_with_retry(session, BASE_URL, params=params)
                    if not resp:
                        logger.error(f"Пропущено сторінку: {category}, exp={exp}, wf={wf}")
                        continue

                    parsed_data = parse_salaries_page(resp.content)

                    row = {
                        "snapshot_date": snapshot_date,
                        "Category": category,
                        "Experience_Years": "< 1" if exp == "0" else ("5+" if exp == "5" else exp),
                        "Work_Format": wf if wf else "All",
                        **parsed_data
                    }
                    results.append(row)
                    logger.info(f"Зібрано: {category} | Exp: {exp} | Format: {wf or 'All'}")
                    time.sleep(0.8)

    return results