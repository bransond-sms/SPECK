# SPECK

**Substrate Point Enumeration and Classification Kit**

SPECK is an open-source desktop application for point-count image analysis. It is designed to be organism-list and habitat agnostic. Applicable to any research context where a user needs to classify points overlaid on images and export structured results. Researchers define their own classification codes, enabling use across disciplines and institutions.

## Features

- Load single images or work through a directory of images in sequence
- Define a rectangular or polygon boundary on the image to exclude unwanted regions
- Generate uniform, random, or stratified-random point grids within the boundary
- Persistent code panel with search/filter for rapid classification
- Mouse-wheel zoom for fine-scale point inspection
- Toggle between single active point and all-points display modes
- Session save and resume (.speck files)
- Per-session metadata capture (site, analyst, dates, custom fields) with per-image fields
- Export results to CSV in long format (one row per point per image)
- User-defined code sets stored as portable JSON files
- Undo support for misclassified points

## Installation

The recommended way to install SPECK is with the bundled installer scripts. They set up an isolated Python environment automatically, so there's nothing to install ahead of time.

1. On the [SPECK GitHub page](https://github.com/bransond-sms/SPECK), click **Code → Download ZIP**, then extract it wherever you want the launch shortcut to appear.
2. From inside the extracted folder, run the installer for your platform:
   - **Windows:** double-click `Install_SPECK.bat`
   - **macOS:** double-click `Install_SPECK.command` (first time only, right-click it and choose **Open** instead of double-clicking)
3. Launch SPECK using the shortcut the installer creates next to the folder.

To uninstall, run `Uninstall_SPECK.bat` (Windows) or `Uninstall_SPECK.command` (macOS) from inside the folder — it removes the environment and shortcut, leaving any saved sessions or exports in place.

Full walkthrough and troubleshooting: [docs/SPECK_Installation_Guide.pdf](docs/SPECK_Installation_Guide.pdf).

### For developers

If you'd rather manage your own Python environment instead of using the installer scripts:

```bash
git clone https://github.com/bransond-sms/SPECK.git
cd SPECK
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

Requires Python 3.9 or higher.

## Code Sets

SPECK uses JSON code set files to define classification codes. These files live in the `codesets/` directory and can be created, edited, and shared independently of the application.
An example code set for SMS fouling panel morpho-functional groups is included at `codesets/sms_morphofunctional.json`.
See `docs/codeset_format.md` for the full specification (coming soon).

## Project Structure

```
SPECK/
├── main.py                       # Application entry point
├── requirements.txt
├── environment.yml               # Conda environment spec used by the installers
├── Install_SPECK.bat             # Windows installer
├── Install_SPECK.command         # macOS installer
├── SPECK.bat / SPECK.sh          # Launchers invoked by the installer-created shortcut
├── Uninstall_SPECK.bat           # Windows uninstaller
├── Uninstall_SPECK.command       # macOS uninstaller
├── app/
│   ├── main_window.py            # Main UI and layout
│   ├── image_canvas.py           # Image display, zoom, boundary, point overlay
│   ├── point_manager.py          # Grid generation and classification state
│   ├── session.py                # Session save/resume and metadata
│   └── export.py                 # CSV export
├── codesets/
│   └── sms_morphofunctional.json
├── sessions/                     # Default session save location
└── docs/
    └── SPECK_Installation_Guide.pdf
```

## Contributing

Contributions are welcome. If you maintain a code set for a different research context, consider submitting it as a pull request to the `codesets/` directory so other researchers can use it.

## License

MIT License. See LICENSE for details.

## Acknowledgements

SPECK was developed at the Smithsonian Marine Station at Fort Pierce by researchers David Branson and Dean Janiak.
