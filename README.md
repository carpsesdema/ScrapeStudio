# Scrape Studio 🪄

Welcome to Scrape Studio! This is a professional visual web scraping tool designed to create high-quality, structured datasets for AI model training, RAG pipelines, and database population.

It combines a powerful, interactive browser with a robust backend scraping engine, allowing you to visually define scraping rules and export them into reusable configurations.



---

## Key Features

*   **Visual Element Targeting:** Click on any element on a webpage to instantly generate CSS selectors. No more "Inspect Element"!
*   **Structured List Detection:** Intelligently identifies repeating items like table rows or list items, letting you define nested data structures with ease.
*   **🪄 Magic Table Detection:** Click one button to automatically detect an entire HTML table's structure, creating rules for all columns instantly.
*   **Project-Based Workflow:** Organize your scraping tasks into projects. All your rules and settings are saved automatically.
*   **"Scrape What I See" Mode:** For dynamic JavaScript-heavy pages, you can click and navigate within the app's browser to get the data you want on-screen, then send the *current* HTML directly to the scraper.
*   **YAML Export:** Export your entire scraping configuration into a clean, human-readable YAML file that can be used by the backend for automated runs.
*   **Direct Database Integration:** Scraped data can be directly inserted into a structured SQLite database based on your schema.

---

## Installation

Setting up Scrape Studio is easy.

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd ScrapeStudio
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download NLP Model:**
    The application uses a small NLP model for some text processing features.
    ```bash
    python -m spacy download en_core_web_sm
    ```

---

## How to Run

*   **To launch the main GUI:**
    ```bash
    python main.py
    ```
*   **To run a scrape from the command line (for automation):**
    ```bash
    python main.py --mode cli --query configs/your_config_file.yaml
    ```

---

## Quick Guide: Scraping a Dynamic Table

This guide shows how to solve a common problem: clicking a link to reveal data, and then scraping that data. We'll use `tennisabstract.com` as our example.

### Step 1: Create Your Project

First, we'll set up a project for this data source.

1.  Launch the app (`python main.py`).
2.  Click **"➕ New Project"**.
3.  Enter the project details:
    *   **Project Name:** `Tennis Abstract ELO`
    *   **Target Websites:** `https://www.tennisabstract.com/` (the home page)
    *   **Output Directory:** Choose a folder on your Desktop for easy access.
4.  Click **"✨ Create Project"**.

### Step 2: Navigate to the Target Data

This is the key step. We will use the app's browser to perform the click for us.

1.  With your new project loaded, click the **"🌐 Load"** button. The Tennis Abstract homepage will appear in the middle panel.
2.  **Inside the Scrape Studio browser**, scroll down to the "Women's Elo Leaders" section.
3.  Click the **"All Women's Elo Ratings"** link at the bottom of that list.
4.  The browser will navigate to a new page showing the full ELO ratings table. **This is the page we will scrape.**

### Step 3: Define the Scraping Rules (The Easy Way)

Now that the correct table is visible, we can use the magic auto-detector.

1.  Click the **"🎯 Target Elements"** button to activate targeting mode.
2.  Click on **any cell** inside the data table (e.g., "Aryna Sabalenka" or her ELO score).
3.  On the right-hand panel, click the **"🪄 Auto-Detect Table"** button.
4.  **Done!** The tool will automatically create a main `table_data` rule (as a `structured_list`) and add sub-rules for every single column it found in the table header. You'll see them all appear in the "Defined Rules" tree.

### Step 4: Run the Scrape!

Because we had to click a link to get here, we must tell the scraper to use the HTML we are currently seeing.

1.  On the right panel, under "Project Actions", check the box that says **"Scrape from current browser view"**.
2.  Click the **"🚀 Run Full Scrape"** button.

The application will now grab the HTML directly from the browser window (the one with the full ELO table) and send it to the backend. The backend will parse it using the rules you just generated and save the clean data directly to your SQLite database in your chosen output folder.

You have successfully scraped a dynamic page without ever leaving the application or using the browser inspector!