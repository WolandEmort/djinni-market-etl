import sys
import logging
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://djinni.co/salaries/"

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("djinni_etl")