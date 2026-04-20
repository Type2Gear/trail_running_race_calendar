# Trail Running Race Calendar

## Overview

This project provides an automated way to populate and maintain a Google Calendar with upcoming trail running race schedules. It reads race data from a simple JSON file and uses the Google Calendar API to keep a designated "master" calendar synchronized. End-users can then easily subscribe to this public calendar to stay informed about race dates, times, and livestream links.

The script is designed to be run periodically (e.g., monthly or weekly) via an automated scheduler like Google Cloud Scheduler, potentially hosted on Google Cloud Functions or another serverless platform.

## Core Functionality

* **Data Source:** Reads race information (name, start/end date & time, timezone, location, livestream URL, description) from a configurable `races.json` file.
* **Google Calendar Integration:** Uses the Google Calendar API v3 via the `google-api-python-client` library.
* **Service Account Authentication:** Authenticates using a Google Cloud Service Account, allowing the script to run without user interaction.
* **Event Synchronization:**
    * **Creates:** Adds new races from the JSON file as events to the target Google Calendar.
    * **Updates:** Modifies existing events in the calendar if their details (time, description, location, etc.) change in the JSON file.
    * **Deletes:** Removes events from the calendar if the corresponding race is no longer present in the `races.json` file ("orphaned" events).
* **Idempotency:** Generates unique, predictable event IDs based on race details and a defined prefix (`trailcal`). This prevents duplicate events and allows the script to reliably find and update/delete specific events across multiple runs.
* **Error Handling:** Includes basic error handling for API calls, file loading, and data parsing.
* **Logging:** Provides informative logs about the synchronization process.

## How it Works

1.  The Python script authenticates with the Google Calendar API using Service Account credentials.
2.  It loads the list of races from the specified `races.json` file.
3.  It fetches a list of existing events from the target Google Calendar that were previously created by this script (identified by the `EVENT_ID_PREFIX`).
4.  It generates a unique ID for each race in the JSON file.
5.  It iterates through the races from the JSON file:
    * If an event with the generated ID already exists in the calendar, it compares the details and updates the calendar event if necessary.
    * If no event with the generated ID exists, it creates a new event in the calendar.
6.  After processing all races from the JSON, it compares the list of existing calendar event IDs with the IDs generated from the current JSON file.
7.  Any event ID present in the calendar but *not* generated from the current JSON file is considered "orphaned" and is deleted from the calendar (with a safety check to typically avoid deleting past events).

## User Subscription

The target Google Calendar (specified by `CALENDAR_ID`) should be made public in its settings. Users can then subscribe via:

* The **Public URL** (easily added to their own Google Calendar).
* The **iCal feed URL** (compatible with most other calendar applications like Outlook, Apple Calendar, etc.).

Links to these URLs would typically be provided on a simple informational landing page.

## Technology Stack

* Python 3.x
* Google API Client Library for Python (`google-api-python-client`)
* Google Authentication Library (`google-auth`)
* Google Calendar API v3
* (Optional/Deployment) Google Cloud Functions, Google Cloud Scheduler

## Setup & Configuration (High Level)

1.  **Google Cloud Project:** Set up a GCP project and enable the Google Calendar API.
2.  **Service Account:** Create a Service Account, download its JSON key file, and store it securely.
3.  **Google Calendar:** Create a new Google Calendar to hold the race events.
4.  **Share Calendar:** Share the Google Calendar with the Service Account's email address, granting it "Make changes to events" permission.
5.  **Make Calendar Public:** Configure the calendar's access permissions to be "Make available to public" for user subscriptions.
6.  **JSON Data:** Create and maintain the `races.json` file with race details.
7.  **Configuration:** Set environment variables or update the script configuration section for `SERVICE_ACCOUNT_FILE`, `CALENDAR_ID`, and `JSON_DATA_FILE`.
8.  **Dependencies:** Install required Python packages using `pip install -r requirements.txt`.

