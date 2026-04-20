import json
import logging
import time # Added for potential waits
from datetime import datetime, timedelta

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# WebDriver Manager Import (Recommended)
from webdriver_manager.chrome import ChromeDriverManager

# BeautifulSoup still useful for parsing the rendered HTML
from bs4 import BeautifulSoup


# --- Configuration ---
URL = "https://fantasy.freetrail.com/events"
OUTPUT_JSON_FILE = 'races_scraped.json'
# How long Selenium should wait for elements to appear (seconds)
SELENIUM_WAIT_TIMEOUT = 20

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    """Sets up the Selenium WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run without opening a visible browser window
    options.add_argument('--no-sandbox') # Often needed in Linux/Docker environments
    options.add_argument('--disable-dev-shm-usage') # Often needed in Linux/Docker environments
    options.add_argument('--log-level=3') # Suppress unnecessary browser logs
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Set user agent

    try:
        # Use webdriver-manager to automatically handle driver download/update
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        logging.info("ChromeDriver setup via webdriver-manager successful.")
        return driver
    except Exception as e:
        logging.error(f"Error setting up WebDriver: {e}")
        logging.error("Ensure Chrome is installed and webdriver-manager can download the driver.")
        return None


def scrape_freetrail_events_selenium(url, timeout):
    """Scrapes race data from the Freetrail Fantasy events page using Selenium,
       appending distance to name if found."""
    scraped_races = []
    driver = setup_driver()
    if not driver:
        return None

    try:
        logging.info(f"Navigating to {url} with Selenium...")
        driver.get(url)
        logging.info(f"Waiting up to {timeout} seconds for table body to appear...")
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'tbody')))
        logging.info("Table body found. Page should be loaded.")

        # Optional: Add a small fixed delay just in case rendering takes a bit longer
        time.sleep(2)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        table_body = soup.find('tbody')
        if not table_body:
            logging.warning("Could not find the main table body ('tbody').")
            return []

        rows = table_body.find_all('tr')
        if not rows:
            logging.warning("Found table body, but no table rows ('tr') within it.")
            return []

        logging.info(f"Found {len(rows)} table rows in rendered HTML.")

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 4:
                try:
                    # --- Updated Name and Distance Extraction ---
                    name = "Name Not Found" # Default
                    base_name = "Name Not Found"
                    distance_text = ""      # Default

                    # Find the div holding the name link
                    name_holder_div = cells[0].find('div', class_='font-semibold')
                    if name_holder_div:
                        name_link = name_holder_div.find('a')
                        if name_link:
                            base_name = name_link.text.strip()
                            name = base_name # Default name is the base name

                            # Find the immediate next sibling div, which might contain the distance
                            distance_div = name_holder_div.find_next_sibling('div')
                            if distance_div:
                                # Check if this div has the expected classes (optional but safer)
                                # Check classes more carefully if needed: distance_div.get('class', [])
                                potential_distance = distance_div.text.strip()
                                # Append distance if it's not empty
                                if potential_distance:
                                    distance_text = potential_distance
                                    name = f"{base_name} {distance_text}" # Update name to include distance

                    # --- End Updated Extraction ---

                    # Extract Date (from the third cell) - same as before
                    date_str = cells[2].text.strip()

                    # Extract Location (from the fourth cell) - same as before
                    location_div = cells[3].find('div', class_='capitalize')
                    location = location_div.text.strip() if location_div else "Location Not Found"

                    # Check completeness before appending
                    if name == "Name Not Found" or location == "Location Not Found" or not date_str:
                        logging.warning(f"Incomplete data found in row. BaseName='{base_name}', Distance='{distance_text}', Date='{date_str}', Location='{location}'. Skipping.")
                        continue

                    # Append data
                    scraped_races.append({
                        'name': name, # This 'name' now includes the distance if found
                        'scraped_start_date': date_str,
                        'location': location
                    })
                    logging.info(f"Scraped: {name} ({date_str}) at {location}") # Log the potentially updated name

                except AttributeError as e:
                     logging.warning(f"AttributeError while parsing a row (likely missing an expected tag/class): {e}. Skipping row.")
                     continue
                except Exception as e:
                     logging.error(f"Unexpected error processing a row: {e}. Skipping row.", exc_info=True)
                     continue
            else:
                logging.warning(f"Skipping a table row because it has less than 4 cells ({len(cells)} found).")

    except TimeoutException:
        logging.error(f"Timeout Error: The table body did not appear within {timeout} seconds.")
        return None
    except WebDriverException as e:
        logging.error(f"WebDriver Error occurred: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during Selenium scraping: {e}", exc_info=True)
        return None
    finally:
        if driver:
            logging.info("Closing the browser.")
            driver.quit()

    return scraped_races

# --- Keep these functions the same ---
def format_for_calendar_json(scraped_data):
    """Formats scraped data into the structure needed for races.json.
       Parses date, defaults start time to 6 AM, defaults end time to 48hrs later.
       Requires manual timezone entry.
    """
    calendar_races = []
    if not scraped_data:
        return calendar_races

    logging.info("Formatting scraped data for calendar JSON...")

    for race in scraped_data:
        # Initialize variables
        start_datetime_str = ""
        end_datetime_str = "" # Initialize end time string
        dt_with_time = None   # Initialize datetime object
        scraped_date_str = race.get('scraped_start_date', '')

        if scraped_date_str:
            try:
                # Parse the date string (e.g., "Jun 28, 2025")
                parsed_date_obj = datetime.strptime(scraped_date_str, "%b %d, %Y")

                # Combine with default time (6:00 AM) - Naive datetime
                dt_with_time = parsed_date_obj.replace(hour=6, minute=0, second=0, microsecond=0)

                # Format start_dateTime (NO timezone offset)
                start_datetime_str = dt_with_time.strftime('%Y-%m-%dT%H:%M:%S')

                # --- Calculate and Format End DateTime ---
                # Add 48 hours (2 days) to the start datetime
                end_dt = dt_with_time + timedelta(hours=48)
                # Format end_dateTime (NO timezone offset)
                end_datetime_str = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                # --- End Calculation ---

                logging.info(f"Formatted start for '{race.get('name')}': {start_datetime_str}")
                logging.info(f"Defaulted end for '{race.get('name')}': {end_datetime_str}")

            except ValueError:
                logging.warning(f"Could not parse date string: '{scraped_date_str}' for race '{race.get('name')}'. Leaving start/end dateTime blank.")
                start_datetime_str = f"INVALID_DATE_FORMAT [{scraped_date_str}]"
                end_datetime_str = "" # Ensure end is blank if start failed
            except Exception as e:
                logging.error(f"Error processing date '{scraped_date_str}' for race '{race.get('name')}': {e}. Leaving start/end dateTime blank.")
                start_datetime_str = f"DATE_PROCESSING_ERROR [{scraped_date_str}]"
                end_datetime_str = "" # Ensure end is blank if start failed

        # --- Assemble final dictionary ---
        calendar_races.append({
            "name": race.get('name', 'Unknown Race'),
            # --- DATETIME & TIMEZONE REQUIRE MANUAL REVIEW ---
            "start_dateTime": start_datetime_str,   # Format: YYYY-MM-DDTHH:MM:SS (NO OFFSET!)
            "end_dateTime": end_datetime_str,     # Calculated end time (NO OFFSET!)
            "timeZone": "America/Denver", # Placeholder - NEEDS MANUAL UPDATE (IANA format)
            # --- Other fields ---
            "livestream_link": "TBD",                # Placeholder - NEEDS MANUAL UPDATE
            "description": "TBD", # Keep original date for reference
            "location": race.get('location', '')
        })

    return calendar_races

def save_to_json(data, filename):
    """Saves the data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False) # Use indent for readability
        logging.info(f"Successfully saved {len(data)} races to {filename}")
    except IOError as e:
        logging.error(f"Error writing to file {filename}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred saving JSON: {e}")

# --- Main Execution (Updated to call Selenium function) ---
if __name__ == "__main__":
    logging.info("Starting Freetrail Fantasy event scraper using Selenium...")
    # Call the new Selenium-based scraping function
    scraped_data = scrape_freetrail_events_selenium(URL, SELENIUM_WAIT_TIMEOUT)

    if scraped_data is not None: # Check if scraping succeeded (returns None on critical errors)
        if scraped_data: # Check if data was actually extracted
            formatted_data = format_for_calendar_json(scraped_data)
            save_to_json(formatted_data, OUTPUT_JSON_FILE)
        else:
             logging.warning("Scraping process completed, but no race data was extracted (check website structure and selectors).")
    else:
         logging.error("Scraping process failed due to WebDriver or timeout error.")

    logging.info("Scraper finished.")