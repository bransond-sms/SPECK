# SPECK
### Substrate Point Enumeration and Classification Kit

SPECK is an open-source desktop application for benthic image point-count analysis. It is designed as a modern, flexible replacement for CPCe (Coral Point Count with Excel extensions), supporting fouling panel analysis, coral reef surveys, and any image-based point-count workflow.

SPECK is built to be organism-list agnostic — researchers define their own classification codes, enabling use across disciplines and institutions.

---

## Features

- Load single images or work through a directory of images in sequence
- Define a rectangular or polygon boundary on the image to exclude frame/mounting hardware
- Generate uniform, random, or stratified-random point grids within the boundary
- Persistent organism code panel with search/filter for rapid classification
- Mouse-wheel zoom for fine-scale point inspection
- Toggle between single active point and all-points display modes
- Session save and resume (`.speck` files)
- Per-session metadata capture (site, panel ID, analyst, dates, custom fields)
- Export results to CSV in long format (one row per organism per image)
- User-defined organism code sets stored as portable JSON files
- Undo support for misclassified points

---

## Requirements

- Python 3.9 or higher
- PyQt6
- See `requirements.txt` for full dependency list

---

## Installation

```bash
# Clone the repository
git clone https://github.com/bransond-sms/SPECK.git
cd SPECK

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

---

## Code Sets

SPECK uses JSON code set files to define organism lists. These files live in the `codesets/` directory and can be created, edited, and shared independently of the application.

An example code set for SMS fouling panel morpho-functional groups is included at `codesets/sms_morphofunctional.json`.

See `docs/codeset_format.md` for the full specification (coming soon).

---

## Project Structure

```
SPECK/
├── main.py                  # Application entry point
├── requirements.txt
├── app/
│   ├── main_window.py       # Main UI and layout
│   ├── image_canvas.py      # Image display, zoom, boundary, point overlay
│   ├── point_manager.py     # Grid generation and classification state
│   ├── session.py           # Session save/resume and metadata
│   └── export.py            # CSV export
├── codesets/
│   └── sms_morphofunctional.json
├── sessions/                # Default session save location
└── docs/
```

---

## Contributing

Contributions are welcome. If you maintain a code set for a different region or organism group, consider submitting it as a pull request to the `codesets/` directory so other researchers can use it.

---

## License

MIT License. See `LICENSE` for details.

---

## Acknowledgements

SPECK was developed at the Smithsonian Marine Station at Fort Pierce as a replacement for CPCe (Coral Point Count with Excel extensions), originally developed by Kevin Kohler and Richard Gill. The CPCe project is no longer maintained following the passing of its authors.
