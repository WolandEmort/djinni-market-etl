import re
import pandas as pd
import numpy as np


def parse_salary_range(val):
    if pd.isna(val) or not val:
        return np.nan, np.nan, np.nan

    numbers = re.findall(r'\d+', str(val))
    if not numbers:
        return np.nan, np.nan, np.nan

    numbers = [float(n) for n in numbers]

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


def transform_data(raw_data: list[dict]) -> pd.DataFrame:
    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)

    numeric_cols = [
        "candidates_count", "jobs_count", "candidates_avg_pokes",
        "jobs_avg_applies", "djinni_index", "index_diff",
        "index_applies_total", "index_pokes_total"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "jobs_count" in df.columns:
        df.loc[df["jobs_count"] == 0, "jobs_count"] = np.nan
    if "candidates_count" in df.columns:
        df.loc[df["candidates_count"] == 0, "candidates_count"] = np.nan

    if "candidates_expected_salary" in df.columns:
        df[["cand_salary_min", "cand_salary_max", "cand_salary_mid"]] = (
            df["candidates_expected_salary"].apply(parse_salary_range).apply(pd.Series)
        )
        df.drop(columns=["candidates_expected_salary"], inplace=True)

    if "jobs_salary_range" in df.columns:
        df[["jobs_salary_min", "jobs_salary_max", "jobs_salary_mid"]] = (
            df["jobs_salary_range"].apply(parse_salary_range).apply(pd.Series)
        )
        df.drop(columns=["jobs_salary_range"], inplace=True)

    df.columns = [col.lower() for col in df.columns]

    return df