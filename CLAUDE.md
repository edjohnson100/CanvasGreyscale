# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**CanvasGreyscale** is a single-file Autodesk Fusion script (code name: Armadillo). It runs inside Fusion's Python environment via `Shift+S` → Scripts and Add-Ins → Run. There is no build step, no package manager, and no test suite — the script runs directly inside Fusion.

## How to Run / Debug

- **Run:** In Fusion 360, press `Shift+S`, find `CanvasGreyscale` in the Scripts list, click Run.
- **Debug:** The `.vscode/launch.json` configures a Python Attach debugger on `localhost:9000`. Fusion must be launched with the debugger port open before attaching.
- **Logging:** `log_msg()` writes to Fusion's Text Commands palette. All `log_msg` calls in `run()` are currently commented out — uncomment them to trace execution.

## Architecture

Everything lives in `CanvasGreyscale.py`. The script has a linear flow:

1. **`_to_greyscale(input, output)`** — platform-dispatched image conversion:
   - **Windows**: spawns a temporary PowerShell script that uses `.NET System.Drawing` + a `ColorMatrix` (NTSC luminance weights) to convert to greyscale RGB PNG. No installation of any kind required.
   - **Mac**: uses Pillow (`PIL`), auto-installed to a local `lib/` folder via `pip install --target` if absent. `importlib.invalidate_caches()` is called before the post-install import so Python re-scans the newly populated directory.
2. **`run(context)`** — Fusion's entry point. Sequential steps:
   - Entity selection (planar faces / construction planes only via `ui.selectEntity`)
   - File dialog (`.png`, `.jpg`, `.jpeg`, `.bmp`)
   - Image conversion: `PIL Image → 'L' → 'RGB'` (greyscale via luminance, back to RGB for Fusion texture engine compatibility)
   - Saves output as `<original_name>_greyscale.png` alongside the source file
   - Creates a `CanvasInput` with `isSymmetric=True`, `opacity=50`, adds it to the active component
   - **Assembly proxy fix:** if inside a sub-component (`design.activeOccurrence`), calls `canvas.createForAssemblyContext()` to get the proxy object before selecting it — this is the key workaround for Fusion's assembly context selection model.

## Key Constraints

- **No dependency on Pillow on Windows** — the Windows path uses PowerShell + `System.Drawing`, which is always present. The `lib/` folder (gitignored) is only used on Mac for Pillow.
- **Canvas must be PNG** — the output is always forced to `.png` regardless of input format, for Fusion canvas compatibility.
- **`adsk.doEvents()`** — called after `canvases.add()` to flush Fusion's UI event queue before attempting to select the new canvas. Do not remove.
- **Manifest** — `CanvasGreyscale.manifest` declares this as a `"type": "script"` for Fusion. The `id` GUID must remain stable.
