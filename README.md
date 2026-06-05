# Redemption LackeyCCG Plugin

This repository holds the **Redemption** plugin for [LackeyCCG](https://lackeyccg.com/),
plus a small tool that makes releasing an update easy and safe.

If you just want to **add cards and publish an update**, you're in the right
place. Read the Quick Start below.

---

## Quick Start (for maintainers)

The update tool runs on your own computer in a web browser. It lets you:

1. (Optional) **Crop** raw card scans into the correct image format.
2. **Paste** new card rows copied from Excel.
3. Automatically **merge** them into the card database, **recompute checksums**,
   rewrite the update list, and **bump the version**.

It then stops. **It never commits to git** — you review the changes and commit
them yourself, exactly as before. Nothing is published until you choose to.

### Easiest way to start it

- **macOS:** double-click `tools/updater/Start Update Tool.command`
- **Windows:** double-click `tools/updater/Start Update Tool.bat`

Your browser opens to **http://127.0.0.1:8765**. To stop the tool, close the
black terminal window it opened (or press `Ctrl+C` in it).

### If you prefer the terminal

Open a terminal in this folder and run:

```bash
make run
```

### One-time setup (only if you want image cropping)

The card/version part works out of the box with Python 3. The **image cropping**
step also needs a free library called Pillow. Install it once:

```bash
make setup
```

(That's the same as `python3 -m pip install -r tools/updater/requirements.txt`.)

If a launcher says **"Python is missing,"** install Python 3 from
[python.org/downloads](https://www.python.org/downloads/) and try again.

---

## Using the tool

A step-by-step walkthrough lives in
[`tools/updater/README-for-maintainers.txt`](tools/updater/README-for-maintainers.txt).
In short:

| Step | What you do |
|------|-------------|
| 0 (optional) | Pick a crop preset, choose your folder of raw scans, click **Crop & save**. Cropped images land in `RedemptionQuick/sets/setimages/general/`. Your originals are untouched. |
| 1 | Paste the new card rows (16 columns, **no header row**). |
| 2 | Set the new version number and a short message. |
| 3 | Click **Preview changes** and read the summary. Fix anything shown in red. |
| 4 | Click **Apply**. The files are written. |
| 5 | Review the changes in git, then commit and push as usual. |

**Match key:** a pasted row whose Name + Set already exists *updates* that card;
otherwise it's *added*. **Crop presets:** Printer 2 = regular runs, Printer 1 =
foils/promos/small runs, Pack = pack thumbnail.

---

## For developers

The tool lives in [`tools/updater/`](tools/updater/) and is built on the Python
**standard library** (the only third-party dependency is Pillow, used solely for
image cropping and imported lazily so the rest works without it). No build step.

```bash
make test     # run the full test suite
make run      # launch the local server
make clean    # remove __pycache__ dirs
```

Design and implementation notes are under
[`docs/superpowers/`](docs/superpowers/).

---

## Safety

- The tool **only** writes `carddata.txt`, `updatelist.txt`, `version.txt`,
  `plugininfo.txt`, and cropped images. It never runs git and never publishes.
- Writes are atomic, and after writing it re-checks every checksum against the
  files on disk.
- Because nothing is committed for you, your normal `git diff` / commit review is
  always the final checkpoint.
