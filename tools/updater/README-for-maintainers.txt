Redemption Plugin Update Tool
=============================

WHAT IT DOES
  Adds new cards and bumps the plugin version for a release. Optionally crops
  raw card scans into the correct image format. You paste card rows from Excel;
  the tool validates them, merges them into carddata.txt, recomputes all
  checksums, rewrites updatelist.txt, and updates the version files. It then
  stops. It NEVER commits to git — you review and commit yourself, exactly as
  before.

HOW TO RUN
  macOS:    double-click "Start Update Tool.command"
  Windows:  double-click "Start Update Tool.bat"
  Either way it opens http://127.0.0.1:8765 in your browser.
  (If it says Python is missing, install Python 3 from python.org and retry.)

  Image cropping (Step 0) also needs the Pillow library. Install it once with:
      python3 -m pip install -r tools/updater/requirements.txt
  Everything except cropping works without it.

STEPS
  0. (Optional) Crop images: choose a crop preset, pick the folder of raw card
     scans, and click "Crop & save images". Cropped JPEGs land in
     RedemptionQuick/sets/setimages/general/ (your originals are untouched).
     Any cropped name that matches no card is flagged — paste the new card rows
     in Step 1 first so brand-new cards are recognized.
  1. In the tool: paste the card rows (16 columns, NO header row).
  2. Set the new version number and a short message.
  3. Click "Preview changes" and read the summary. Fix any red errors.
  4. Click "Apply". The files are written.
  5. In your git tool, review the diff, then commit and push.

NOTES
  - Crop presets: Printer 2 = regular runs, Printer 1 = foils/promos/small runs,
    Pack = pack/set thumbnail. Cropped card images are 345x495; pack is 207x300.
  - Cropping strips commas from filenames and saves as .jpg.
  - Match key is (Name, Set). A row whose Name+Set already exists updates that
    card; otherwise it is added at the end.
  - "Missing (new cards)" images means you added a card but its .jpg isn't in
    the general/ folder yet. Add it and re-preview.
  - The tool changes only carddata.txt, updatelist.txt, version.txt, and
    plugininfo.txt. Anything else (new packs, decks, setlist) stays manual.
