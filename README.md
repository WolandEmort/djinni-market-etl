# Djinni Market Analytics ETL

A data pipeline built in Python to extract, transform, and load (ETL) IT market analytics from the Ukrainian tech hiring platform [Djinni.co](https://djinni.co/). 

This project is designed to collect aggregated market data (job openings, active candidates, salary ranges, and the Djinni Index) across various tech stacks, experience levels, and work formats.

## 🚀 Features

* **Anti-Bot Bypass:** Utilizes `curl_cffi` to impersonate browser TLS fingerprints, effectively bypassing Cloudflare and rate limiters.
* **Dynamic Extraction:** Automatically scrapes the latest available tech categories directly from the platform's hidden DOM elements.
* **Fault Tolerance:** Implements real-time disk flushing. Data is saved to a raw CSV file row-by-row during the scraping process to prevent data loss in case of network failures or interruptions.
* **Data Transformation:** Cleans and formats raw scraped strings (e.g., salary ranges, index dynamics) into structured numeric types using `pandas`.
* **Interactive CLI:** Prompts the user to configure scraping parameters (experience levels and remote/office formats) before execution.

## 🛠️ Tech Stack

* **Language:** Python 3.x
* **HTTP Client:** `curl_cffi`
* **HTML Parsing:** `beautifulsoup4`
* **Data Manipulation:** `pandas`
* **Export:** `csv`, `openpyxl` (Excel)

## 📋 Prerequisites

Make sure you have Python installed. You can install the required dependencies using the following command:

```bash
pip install -r requirements.txt