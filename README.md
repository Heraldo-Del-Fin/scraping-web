# Web Novel Scraper & Translator

A Python application for extracting, translating, and exporting web novel chapters from multiple sources through a graphical interface.

The project supports multiple web novel sites through configurable scraping profiles, allowing users to scrape chapters starting from an index page or a specific chapter URL, save the extracted content, translate it automatically, and export the results in different formats.

---

## Overview

This tool was created to simplify the process of collecting and translating web novel chapters.
Instead of manually copying content chapter by chapter, the application automates the full workflow:

1. Start from a novel index page or a specific chapter URL.
2. Automatically detect the site and apply the correct scraping profile.
3. Extract chapter content and navigate through subsequent chapters.
4. Save the extracted text in the chosen format.
5. Translate the content using Google Translate (free, no API key required).
6. Export the final result as TXT or PDF.

The project is intended for personal reading, offline archiving, text processing, research, and experimentation with web scraping and translation workflows.

---

## Features

### Chapter Scraping

- Scrape chapter content from multiple web novel sites.
- Start from a novel index page or any valid chapter URL.
- Automatically detect the site and load its scraping profile.
- Follow next chapter links automatically.
- Fall back to URL-based chapter navigation when next links are not detected.
- Configure the number of chapters to extract.
- Force a specific scraping profile when auto-detection is not enough.
- Detect selectors automatically for unknown sites and save the profile.

### Site Profiles

- JSON-based profile system (`perfiles.json`) — editable without touching the code.
- Built-in profiles for NovelBin, Light Novel World, Royal Road, and Scribble Hub.
- Generic fallback profile with common selectors for unsupported sites.
- Auto-detection mode: visits a page, tests selectors, and saves a new profile automatically.
- Profile manager in the GUI: add, edit, activate, deactivate, and delete profiles visually.

### Content Export

- Save extracted content as a single TXT file.
- Save extracted content as JSON (structured, with metadata).
- Save each chapter as a separate TXT file.
- Configurable output folder and file name.

### Translation

- Translate extracted chapters automatically using Google Translate.
- No API key required — uses the free `deep-translator` library.
- Processes previously extracted TXT files, or PDF files as input.
- Detects chapters in a PDF automatically (chapter/section headings, falling back to one chapter per page, then to the whole document as a single block).
- Translates title and body of each chapter independently.
- Handles long chapters by splitting into safe-size chunks automatically.
- Export translated content as TXT.
- Export translated content as a formatted PDF with cover page and justified text.
- Supports 10 languages: Spanish, Portuguese, French, German, Italian, Japanese, Korean, Simplified Chinese, Russian, and Arabic.

### Graphical User Interface

- Dark-themed desktop interface built with Tkinter.
- Three tabs: Download, Translate, and Profiles.
- Real-time progress bar and chapter-by-chapter log.
- Stop button to cancel any running process.
- Folder browser for all output paths.
- Profile selector integrated into the download tab.
- Detect Selectors button for onboarding new sites.
- No terminal required for standard use.

---

## Project Structure

```text
scraping-web/
│
├── main.py                  ← Application entry point. Run this.
├── scraper_cli.py           ← Scraper CLI (called by the GUI as a subprocess)
├── traductor_cli.py         ← Translator CLI (called by the GUI as a subprocess)
├── perfiles.json            ← Site profiles (editable JSON)
│
├── core/
│   ├── perfiles.py          ← Load, search, and persist site profiles
│   ├── scraper.py           ← NovelScraper class (Playwright-based)
│   └── exportar.py          ← Save chapters as TXT, JSON, or separate files
│
├── traductor/
│   ├── traducir.py          ← Translation logic (chunked, with retries)
│   └── exportar_pdf.py      ← PDF and translated TXT generation
│
└── gui/
    ├── app.py               ← Main window and tab assembly
    ├── widgets.py           ← Theme, colors, and reusable components
    ├── tab_scraping.py      ← Download tab
    ├── tab_traduccion.py    ← Translate tab
    └── tab_perfiles.py      ← Profile management tab
```

---

## Workflow

```text
Novel Index URL  ──or──  Chapter URL
          │
          ▼
  Auto-detect Site Profile
  (or use forced profile)
          │
          ▼
     Web Scraper
  (Playwright + profile selectors)
          │
          ▼
  TXT / JSON Output
          │
          ▼
     Translator
  (Google Translate, free)
          │
          ▼
  TXT / PDF Output
```

---

## Built-in Site Profiles

| ID               | Site                  | Notes                                      |
|------------------|-----------------------|--------------------------------------------|
| `novelbin`       | novelbin.me           | Large catalog of web novels in English     |
| `lightnovelworld`| lightnovelworld.org   | Active domain is `.org` (`.co` was closed) |
| `royalroad`      | royalroad.com         | Original English web fiction platform      |
| `scribblehub`    | scribblehub.com       | Original fiction and manga community       |
| `generico`       | Any site              | Fallback with common selectors             |

New profiles can be added from the **Profiles** tab in the GUI or by editing `perfiles.json` directly.

---

## Technologies

| Area               | Library / Tool              |
|--------------------|-----------------------------|
| Web scraping       | Playwright (Chromium)       |
| HTML parsing       | Playwright selectors        |
| Translation        | deep-translator (Google)    |
| PDF generation     | ReportLab                   |
| PDF text extraction| pypdf                       |
| Desktop GUI        | Tkinter (stdlib)            |
| Data persistence   | JSON                        |
| Language           | Python 3.10+                |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Heraldo-Del-Fin/web-novel-scraper
cd web-novel-scraper

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install the Chromium browser for Playwright
playwright install chromium

# 4. Launch the application
python main.py
```

---

## CLI Usage

Both the scraper and translator can also be used directly from the terminal without the GUI.

```bash
# Scrape 20 chapters from a novel index
python scraper_cli.py https://novelbin.me/novel-book/supreme-magus --capitulos 20

# Scrape from a specific chapter using a forced profile
python scraper_cli.py https://royalroad.com/fiction/.../chapter/... --sitio royalroad

# Detect selectors for an unknown site and save the profile
python scraper_cli.py https://some-novel-site.com/novel/title/chapter/1 --detectar

# List all available profiles
python scraper_cli.py --listar-perfiles

# Translate and export as PDF
python traductor_cli.py novelas/my-novel.txt --idioma es --formato-salida pdf

# Translate and export as TXT
python traductor_cli.py novelas/my-novel.txt --idioma pt --formato-salida txt

# Translate directly from a PDF (chapters are auto-detected)
python traductor_cli.py novelas/my-novel.pdf --idioma es --formato-salida pdf

# List available translation languages
python traductor_cli.py --listar-idiomas
```

---

## Current Scope

The application currently supports multiple web novel sites through a profile-based system.
Each profile defines the CSS selectors and navigation rules for a specific site, allowing the scraper to adapt without modifying the core code.

The long-term goal is to evolve the project into a fully open-source tool for the web novel reading community, distributed as a standalone executable with no Python installation required.

---

## Planned Improvements

- **Standalone executable** — package as a `.exe` using PyInstaller or Nuitka for Windows distribution, no Python required.
- **More built-in profiles** — expand support for additional popular novel sites.
- **Optional paid translation APIs** — integrate DeepL and OpenAI as higher-quality alternatives to Google Translate, selectable from the GUI.
- **Metadata extraction** — capture author, genre, tags, and novel description alongside chapter content.
- **EPUB export** — generate standard eBook files compatible with readers like Calibre and Kindle.
- **Batch processing** — queue multiple novels for unattended overnight scraping.
- **Chapter deduplication** — detect and skip already downloaded chapters when resuming.
- **Improved anti-bot handling** — rotating user agents, human-like delays, and proxy support.

---

## Use Cases

- Offline reading of web novels in your preferred language.
- Personal archiving of ongoing series.
- Translation workflows for communities and fan translations.
- Text analysis and NLP dataset generation.
- Learning web scraping, browser automation, and GUI development in Python.

---

## Disclaimer

This project is provided for educational, research, and personal-use purposes only.
Users are solely responsible for ensuring compliance with copyright laws, website terms of service, and applicable regulations when accessing or processing third-party content.
The authors do not condone or encourage any unauthorized reproduction or distribution of copyrighted material.

---

## Author

Luis Daniel Serrato Príncipe  
GitHub: [Heraldo-Del-Fin](https://github.com/Heraldo-Del-Fin)
