import argparse
from config import logger
from extract import extract_data
from transform import transform_data
from load import load_data


def parse_args():
    parser = argparse.ArgumentParser(description="Djinni Market ETL Pipeline")
    parser.add_argument("--exp", type=str, default="0,1,2,3,5", help="Роки досвіду (0,1,2,3,5)")
    parser.add_argument("--format", type=str, choices=["all", "remote", "both"], default="both", help="Формат роботи")
    return parser.parse_args()


def get_work_formats(format_arg: str) -> list:
    if format_arg == "all": return [""]
    if format_arg == "remote": return ["full_remote"]
    return ["", "full_remote"]


def main():
    args = parse_args()

    exp_levels = [x.strip() for x in args.exp.split(",") if x.strip() in ["0", "1", "2", "3", "5"]]
    if not exp_levels:
        exp_levels = ["0", "1", "2", "3", "5"]
    work_formats = get_work_formats(args.format)

    logger.info(f"Старт ETL пайплайну. Exp: {exp_levels}, Формати: {work_formats}")

    raw_data = extract_data(exp_levels, work_formats)

    transformed_df = transform_data(raw_data)

    load_data(transformed_df)


if __name__ == "__main__":
    main()