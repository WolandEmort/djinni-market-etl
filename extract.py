import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from config import BASE_URL, logger

SESSION_KWARGS = {
    "impersonate": "chrome120",
    "headers": {"Accept-Language": "uk-UA,uk;q=0.9"},
    "cookies": {"django_language": "uk"},
}


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

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else delay * (2 ** (attempt + 1)) + random.uniform(0.5, 1.5)
                )
                logger.warning(
                    f"HTTP 429 для {response.url}. Пауза {wait_time:.1f}с (Спроба {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                continue

            logger.warning(f"HTTP {response.status_code} для {response.url} (Спроба {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"Мережева помилка: {e} (Спроба {attempt + 1}/{max_retries})")

        time.sleep(delay * (attempt + 1))
    return None


def parse_salaries_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "candidates_count": None,
        "candidates_diff": None,
        "candidates_expected_salary": None,
        "candidates_avg_pokes": None,
        "jobs_count": None,
        "jobs_diff": None,
        "jobs_salary_range": None,
        "jobs_avg_applies": None,
        "djinni_index": None,
        "index_diff": None,
        "index_applies_total": None,
        "index_pokes_total": None,
    }

    cand_card = soup.find("div", id="candidates_card")
    if cand_card:
        data["candidates_count"] = safe_get_text(cand_card, ".fs-1")
        data["candidates_diff"] = safe_get_text(cand_card, ".text-diff")

        expected_salary_label = cand_card.find(lambda tag: tag.name == "small" and "Середні очікування" in tag.text)
        if expected_salary_label:
            data["candidates_expected_salary"] = (
                expected_salary_label.find_parent("div", class_="row")
                .find("div", class_="col-auto")
                .get_text(strip=True)
                .replace("\xa0", " ")
            )

        avg_pokes_label = cand_card.find(lambda tag: tag.name == "small" and "Пропозицій в середньому" in tag.text)
        if avg_pokes_label:
            data["candidates_avg_pokes"] = (
                avg_pokes_label.find_parent("div", class_="row")
                .find("div", class_="col-auto")
                .get_text(strip=True)
            )

    jobs_card = soup.find("div", id="jobs_card")
    if jobs_card:
        data["jobs_count"] = safe_get_text(jobs_card, ".fs-1")
        data["jobs_diff"] = safe_get_text(jobs_card, ".text-diff")

        jobs_salary_label = jobs_card.find(lambda tag: tag.name == "small" and "Середня вилка" in tag.text)
        if jobs_salary_label:
            data["jobs_salary_range"] = (
                jobs_salary_label.find_parent("div", class_="row")
                .find("div", class_="col-auto")
                .get_text(strip=True)
                .replace("\xa0", " ")
            )

        avg_applies_label = jobs_card.find(lambda tag: tag.name == "small" and "Відгуків в середньому" in tag.text)
        if avg_applies_label:
            data["jobs_avg_applies"] = (
                avg_applies_label.find_parent("div", class_="row")
                .find("div", class_="col-auto")
                .get_text(strip=True)
            )

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


def extract_data(exp_levels: list, work_formats: list, max_workers: int = 4) -> list[dict]:
    snapshot_date = datetime.now().date().isoformat()

    with requests.Session(**SESSION_KWARGS) as init_session:
        response = fetch_with_retry(init_session, BASE_URL)
        if not response:
            raise RuntimeError("Критична помилка: не вдалося завантажити базову сторінку категорій після всіх спроб.")

        if "Пропозицій в середньому" not in response.text:
            raise RuntimeError(
                "Критична помилка: сторінка повернулася не українською мовою або змінилася HTML-розмітка Djinni."
            )

        soup = BeautifulSoup(response.content, "html.parser")
        category_select = soup.find("select", {"name": "category"})
        if not category_select:
            raise RuntimeError("Критична помилка: не знайдено список категорій у HTML-розмітці.")

        categories = [opt.get("value") for opt in category_select.find_all("option") if opt.get("value")]
        if not categories:
            raise RuntimeError("Критична помилка: список категорій порожній.")

    tasks = [
        (category, exp, wf)
        for category in categories
        for exp in exp_levels
        for wf in work_formats
    ]
    total = len(tasks)
    logger.info(
        f"Знайдено категорій: {len(categories)}. Очікувана кількість сторінок: {total} (потоків: {max_workers})"
    )

    thread_local = threading.local()
    created_sessions = []
    sessions_lock = threading.Lock()

    def get_thread_session():
        if not hasattr(thread_local, "session"):
            session = requests.Session(**SESSION_KWARGS)
            thread_local.session = session
            with sessions_lock:
                created_sessions.append(session)
        return thread_local.session

    def process_task(task: tuple) -> tuple[dict | None, str, str, str]:
        category, exp, wf = task
        params = {"category": category, "exp": exp}
        if wf:
            params["work_format"] = wf

        session = get_thread_session()
        resp = fetch_with_retry(session, BASE_URL, params=params)
        time.sleep(random.uniform(0.4, 0.8))

        if not resp:
            return None, category, exp, wf

        parsed_data = parse_salaries_page(resp.content)
        row = {
            "snapshot_date": snapshot_date,
            "Category": category,
            "Experience_Years": "< 1" if exp == "0" else ("5+" if exp == "5" else exp),
            "Work_Format": wf if wf else "All",
            **parsed_data,
        }
        return row, category, exp, wf

    results = []
    skipped = 0
    completed = 0

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_task, task) for task in tasks]

            for future in as_completed(futures):
                completed += 1
                row, category, exp, wf = future.result()

                if row is None:
                    skipped += 1
                    logger.error(
                        f"Пропущено сторінку після всіх спроб ({skipped}/{total}): {category}, exp={exp}, wf={wf}"
                    )
                    continue

                results.append(row)
                logger.info(f"[{completed}/{total}] Зібрано: {category} | Exp: {exp} | Format: {wf or 'All'}")
    finally:
        for session in created_sessions:
            session.close()

    if total > 0 and (skipped / total) > 0.05:
        raise RuntimeError(f"Incomplete snapshot: {skipped}/{total} pages failed (>5% threshold)")

    logger.info(f"Збір завершено успішно. Отримано {len(results)}/{total} сторінок (пропущено: {skipped}).")
    return results