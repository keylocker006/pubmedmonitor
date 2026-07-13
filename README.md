# PubMed Research Monitor

A mobile Android app built with **Kivy** that monitors recent PubMed publications for specific medical/research keywords, fetches metadata, and automatically downloads open-access PDFs to your device's Downloads folder.

## Features

- **PubMed Search**: Search by keywords (e.g., "leukemia", "hematology", "cancer").
- **Metadata Collection**: Pulls titles, authors, abstracts, DOIs, and PMC IDs.
- **PDF Download**: Automatically downloads available open-access PDFs and exports them to public storage.
- **Persistent CSV Database**: Tracks downloaded papers in `collection.csv` to avoid duplicates.
- **User-Friendly Interface**: Simple mobile UI with logging and progress feedback.
- **Android-Optimized**: Uses `androidstorage4kivy` for safe access to shared storage (Downloads folder).

## Project Structure

```
.
├── main.py                  # Main Kivy Android application
├── pubmed_monitor.py        # Core PubMed API logic and utilities
├── collection.csv           # Generated: Tracks all papers (created on first run)
└── papers/                  # Generated: Downloaded PDFs (sandboxed)
```

## How It Works

1. Enter a search term and optional max results count.
2. The app searches PubMed for recent articles (configurable `DAYS_BACK`).
3. Filters out already-processed PMIDs.
4. Fetches detailed metadata.
5. For articles with PMC IDs, checks for and downloads PDFs via NCBI's Open Access API.
6. Saves everything to a local CSV and exports PDFs to your Downloads folder.

## Configuration

Edit `pubmed_monitor.py` for defaults:
- `SEARCH_TERMS`: Default keywords.
- `DAYS_BACK`: How far back to search (default: 120 days).
- `MAX_RESULTS`: Max articles per search.

## Requirements

### For Development / Running on Desktop
- Python 3.8+
- Kivy (`pip install kivy`)
- Requests, etc. (see `pubmed_monitor.py` imports)
- For full Android features, run on an Android device/emulator.

### For Android Build
- Buildozer
- Kivy
- Java JDK
- Android SDK / NDK (handled by Buildozer)

## Building the APK

### Step-by-Step Instructions (Using Buildozer)

1. **Install Buildozer**:
   ```bash
   pip install buildozer
   ```

2. **Initialize Buildozer** (in the project directory):
   ```bash
   buildozer init
   ```

3. **Edit `buildozer.spec`** (key settings):
   ```ini
   [app]
   title = PubMed Research Monitor
   package.name = pubmedmonitor
   package.domain = org.test
   source.dir = .
   source.include_exts = py,png,jpg,kv,atlas
   version = 1.0
   requirements = python3, kivy, requests, urllib3, openssl, androidstorage4kivy
   orientation = portrait, landscape
   fullscreen = 0

   # Android permissions (for storage)
   android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
   android.api = 36
   android.minapi = 30
   ```

   

4. **Build the APK**:
   ```bash
   buildozer -v android debug
   ```

   - First build may take 10-30+ minutes (downloads SDKs).
   - Output APK will be in `bin/` folder (e.g., `pubmedmonitor-1.0-debug.apk`).

5. **Deploy to Device**:
   - Connect your Android device via USB (enable USB debugging).
   - ```bash
     buildozer android deploy run
     ```
   - Or manually install the APK using `adb install bin/*.apk`.

### Troubleshooting Build Issues
- **Permission Errors**: Ensure `INTERNET` permission is declared.
- **Storage Access**: `androidstorage4kivy` handles scoped storage on Android 10+.
- **Large Downloads**: PDFs can be big; test with small `MAX_RESULTS`.
- **API Rate Limits**: NCBI has usage guidelines—avoid excessive requests.
- **Clean build:** `buildozer android clean` then rebuild.

For full Buildozer documentation: [https://buildozer.readthedocs.io/]

## Running the App

- On desktop (for testing): `python main.py`
- On Android: Install the built APK.

## Notes & Limitations

- Requires internet connection.
- Only downloads **open-access** PDFs available via PMC.
- PDF URLs use NCBI's HTTPS mirrors (handles deprecated FTP paths).
- Tested with Kivy on Android; may need tweaks for specific devices.
- Respect PubMed/NCBI terms of use for automated scraping.

## License

This project is for personal/research use. 

---

**Happy Researching!** 🧬
