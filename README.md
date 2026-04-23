# Gridfinity Label Generator

A web-based tool for designing and exporting 3D-printable labels for [Gridfinity](https://gridfinity.xyz/) storage bins. Configure your labels in the browser, preview them in real-time 3D, and download STEP or STL files ready for your slicer.

## Overview

The app is a FastAPI backend that uses [build123d](https://github.com/gumyr/build123d) to generate parametric CAD geometry, paired with a vanilla JS frontend using Three.js for live 3D preview.

**Key features:**

- **Multiple base types** — Pred, Pred Box, Plain, Cullenect, Modern, or no base at all
- **Label styles** — Embossed (raised), Debossed (recessed), or Embedded (flush pocket)
- **Multi-material support** — splits geometry into separate body + text files for AMS/MMU two-color printing, with four split modes (Text, Face Split, Background, Background Filled)
- **Fragment picker** — insert icons and special symbols into label content from a categorized picker panel
- **Divisions** — split one label into multiple equal sections with independent content
- **Batch generation** — queue multiple labels and download them all as a ZIP archive
- **Session import/export** — save your full label queue to JSON and restore it later
- **STEP and STL output** — STEP is recommended for smaller files and cleaner boolean results

## Installation

**Requirements:** Python 3.10+

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd label_website
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running

```bash
python app.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

For development with auto-reload:
```bash
uvicorn app:app --reload
```

## Usage

1. Click **Add Label** to create a new label entry
2. Set the **Width** in Gridfinity units (`u`) or millimeters
3. Type your label content, or use the **Fragment Picker** to insert icons
4. Click **Preview 3D** to render a live 3D view
5. Click **Download All** to export all queued labels as a ZIP

Use **Export JSON** in the header to save your session, and **Import JSON** to restore it.

## API

The backend exposes a small REST API:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/preview` | Generate STL for 3D preview (returns binary STL or base64 JSON for multi-material) |
| `POST` | `/api/generate` | Generate all label configs and return a ZIP archive |
| `POST` | `/api/generate/single` | Generate a single label and return the file directly |
| `GET`  | `/api/fragments` | List all available fragment types with descriptions and examples |

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `build123d` | Parametric CAD geometry generation |
| `pint` | Unit conversion (Gridfinity units ↔ mm) |
| `python-multipart` | Multipart form support |
