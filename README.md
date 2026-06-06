# Web Novel Scraper & Translator

A Python application for extracting, translating, and exporting web novel chapters.

The project currently focuses on NovelBin and allows users to scrape multiple chapters starting from a specific chapter URL, save the extracted content, translate it automatically, and export the results in different formats through a graphical interface.

---

## Overview

This tool was created to simplify the process of collecting and translating web novel chapters.

Instead of manually copying content chapter by chapter, the application automates the workflow:

1. Start from a chapter URL.
2. Extract the chapter content.
3. Automatically navigate through subsequent chapters.
4. Save the extracted text.
5. Translate the content.
6. Export the final result.

The project is intended for personal reading, text processing, research, and experimentation with web scraping and translation workflows.

---

## Features

### Chapter Scraping

* Scrape chapter content from NovelBin.
* Start from any valid chapter URL.
* Automatically follow the next chapter links.
* Configure the number of chapters to extract.
* Extract multiple chapters in a single execution.

### Content Export

* Save extracted content as TXT files.
* Save extracted content as JSON files.
* Organize generated files automatically.

### Translation

* Translate extracted chapters automatically.
* Process previously extracted files.
* Save translated versions separately.
* Export translated content to TXT.
* Export translated content to PDF.

### Graphical User Interface

* User-friendly interface.
* Configure output folders.
* Separate management of original and translated novels.
* Custom file naming.
* Simplified workflow without requiring terminal commands.

---

## Project Structure

```text
scraping-web/
│
├── novelas/
│   └── Extracted novel files
│
├── traducidas/
│   └── Translated novel files
│
├── scraper.py
│   └── Novel extraction logic
│
├── traductor.py
│   └── Translation and export logic
│
└── gui.py
    └── Graphical user interface
```

---

## Workflow

```text
Chapter URL
     │
     ▼
Web Scraper
     │
     ▼
TXT / JSON Output
     │
     ▼
Translator
     │
     ▼
TXT / PDF Output
```

---

## Technologies

* Python
* Web Scraping
* Browser Automation
* JSON Processing
* Translation APIs
* PDF Generation
* Desktop GUI

---

## Current Scope

The current implementation is focused on NovelBin.

The long-term goal is to evolve the project into a reusable scraping platform capable of supporting multiple web novel sources through configurable scraping profiles.

---

## Planned Improvements

* Multi-site support.
* Configurable scraping profiles.
* Dynamic selector management.
* Metadata extraction.
* Improved export options.
* Plugin-based architecture.
* Better error handling.
* Batch processing.

---

## Use Cases

* Offline reading.
* Personal archiving.
* Translation workflows.
* Text analysis.
* Dataset generation.
* Learning web scraping techniques.

---

## Disclaimer

This project is provided for educational, research, and personal-use purposes.

Users are responsible for ensuring compliance with copyright laws, website policies, and applicable regulations when accessing or processing third-party content.

---

## Author

Luis Daniel Serrato Príncipe

GitHub:
https://github.com/Heraldo-Del-Fin
