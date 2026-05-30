Redemption Plugin Update Tool
=============================

WHAT IT DOES
  Adds new cards and bumps the plugin version for a release. You paste card
  rows from Excel; the tool validates them, merges them into carddata.txt,
  recomputes all checksums, rewrites updatelist.txt, and updates the version
  files. It then stops. It NEVER commits to git — you review and commit
  yourself, exactly as before.

HOW TO RUN
  macOS:    double-click "Start Update Tool.command"
  Windows:  double-click "Start Update Tool.bat"
  Either way it opens http://127.0.0.1:8765 in your browser.
  (If it says Python is missing, install Python 3 from python.org and retry.)

STEPS
  1. Drop any new card images (.jpg) into
     RedemptionQuick/sets/setimages/general/  first.
  2. In the tool: paste the card rows (16 columns, NO header row).
  3. Set the new version number and a short message.
  4. Click "Preview changes" and read the summary. Fix any red errors.
  5. Click "Apply". The files are written.
  6. In your git tool, review the diff, then commit and push.

NOTES
  - Match key is (Name, Set). A row whose Name+Set already exists updates that
    card; otherwise it is added at the end.
  - "Missing (new cards)" images means you added a card but its .jpg isn't in
    the general/ folder yet. Add it and re-preview.
  - The tool changes only carddata.txt, updatelist.txt, version.txt, and
    plugininfo.txt. Anything else (new packs, decks, setlist) stays manual.
