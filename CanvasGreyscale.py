"""
CanvasGreyscale: Because Project Salvador shouldn't have to guess
High-Contrast Canvas Pre-Processing Utility
Last update: 2026-06-04

- features:
    - Workflow: Native Entity Selection (Planar Only) -> Local File Dialog
    - Engine: PowerShell/System.Drawing (Windows) or Pillow (Mac) desaturation
    - Output: 50% Opacity Greyscale Canvas (Optimized for Salvador Tracing)
"""

import adsk.core, adsk.fusion, traceback
import os
import subprocess
import sys
import platform

# ---------------------------------------------------------------------------
# Tunable defaults
#   contrast   >1.0 = more contrast, <1.0 = flatter (try 1.2–1.8 for Salvador)
#   brightness  0.0 = unchanged, +0.1 = brighter midtones, -0.1 = darker
#
# These are the values used when the user accepts the dialog without changes.
# ---------------------------------------------------------------------------
DEFAULT_CONTRAST   = 1.3
DEFAULT_BRIGHTNESS = 0.0

# ---------------------------------------------------------------------------
# Greyscale conversion — platform-dispatched
# Windows: PowerShell + .NET System.Drawing (zero install, always available)
# Mac:     Pillow, auto-installed to a local lib/ folder if missing
# ---------------------------------------------------------------------------

_script_dir = os.path.dirname(os.path.abspath(__file__))
_lib_dir    = os.path.join(_script_dir, "lib")


def _to_greyscale_windows(input_path, output_path, contrast, brightness):
    """Converts to greyscale PNG via PowerShell + System.Drawing. No install needed.

    ColorMatrix math (contrast C, brightness B):
      luminance  = R*0.299 + G*0.587 + B*0.114
      output_ch  = luminance * C + (0.5*(1-C) + B)   for each of R', G', B'
    This keeps mid-grey (0.5) anchored when brightness=0, spreading darks/lights apart.
    """
    import tempfile

    # Compute the nine identical channel weights and the shared offset in Python
    # so the values are plain literals in the .ps1 — avoids locale decimal-separator issues.
    w_r  = 0.299 * contrast
    w_g  = 0.587 * contrast
    w_b  = 0.114 * contrast
    off  = 0.5 * (1.0 - contrast) + brightness

    ps_script = f"""\
param($In, $Out)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile($In)
$bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, `
    [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$cm = New-Object System.Drawing.Imaging.ColorMatrix
$cm.Matrix00={w_r}; $cm.Matrix01={w_r}; $cm.Matrix02={w_r}
$cm.Matrix10={w_g}; $cm.Matrix11={w_g}; $cm.Matrix12={w_g}
$cm.Matrix20={w_b}; $cm.Matrix21={w_b}; $cm.Matrix22={w_b}
$cm.Matrix33=1.0;   $cm.Matrix44=1.0
$cm.Matrix40={off}; $cm.Matrix41={off}; $cm.Matrix42={off}
$ia = New-Object System.Drawing.Imaging.ImageAttributes
$ia.SetColorMatrix($cm)
$r = New-Object System.Drawing.Rectangle(0, 0, $src.Width, $src.Height)
$g.DrawImage($src, $r, 0, 0, $src.Width, $src.Height, `
    [System.Drawing.GraphicsUnit]::Pixel, $ia)
$g.Dispose()
$src.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"""
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.ps1', delete=False, encoding='utf-8'
    )
    try:
        tmp.write(ps_script)
        tmp.close()
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-NonInteractive',
             '-File', tmp.name, '-In', input_path, '-Out', output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _to_greyscale_mac(input_path, output_path, contrast, brightness):
    """Converts to greyscale PNG on macOS via Pillow (auto-installed to lib/ if absent)."""
    import importlib

    if _lib_dir not in sys.path:
        sys.path.insert(0, _lib_dir)

    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        os.makedirs(_lib_dir, exist_ok=True)
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'Pillow',
             '--target', _lib_dir, '--quiet'],
            capture_output=True
        )
        importlib.invalidate_caches()
        from PIL import Image, ImageEnhance  # raises ImportError with real message if still missing

    img = Image.open(input_path).convert('L').convert('RGB')
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if brightness != 0.0:
        img = ImageEnhance.Brightness(img).enhance(1.0 + brightness * 2.0)
    img.save(output_path, format='PNG')


def _to_greyscale(input_path, output_path, contrast, brightness):
    if platform.system() == 'Windows':
        _to_greyscale_windows(input_path, output_path, contrast, brightness)
    else:
        _to_greyscale_mac(input_path, output_path, contrast, brightness)


# ---------------------------------------------------------------------------
# Fusion globals
# ---------------------------------------------------------------------------

app = adsk.core.Application.get()
ui  = app.userInterface


def log_msg(msg):
    """Writes a debug message to Fusion's Text Command Palette."""
    try:
        palettes = ui.palettes
        textPalette = palettes.itemById('TextCommands')
        if textPalette:
            textPalette.writeText(f'CanvasGreyscale: {msg}')
    except:
        pass


def _ask_conversion_settings():
    """Shows a two-step dialog for contrast and brightness. Returns (contrast, brightness)
    using defaults if the user cancels either step."""
    contrast   = DEFAULT_CONTRAST
    brightness = DEFAULT_BRIGHTNESS

    val, cancelled = ui.inputBox(
        'Contrast  (1.0 = flat  |  1.3 = richer  |  1.6 = punchy  |  2.0 = high)\n'
        'Higher values give Salvador cleaner edges on soft or colourful images.',
        'Conversion Settings — Contrast',
        str(DEFAULT_CONTRAST)
    )
    if not cancelled:
        try:
            contrast = max(0.1, min(4.0, float(val)))
        except ValueError:
            pass

    val, cancelled = ui.inputBox(
        'Brightness offset  (0.0 = unchanged  |  +0.1 = brighter  |  -0.1 = darker)',
        'Conversion Settings — Brightness',
        str(DEFAULT_BRIGHTNESS)
    )
    if not cancelled:
        try:
            brightness = max(-0.9, min(0.9, float(val)))
        except ValueError:
            pass

    return contrast, brightness


def run(context):
    try:
        design = app.activeProduct
        if not design:
            ui.messageBox('Please open a design before running this script.', 'No Active Design')
            return

        # 1. Prompt the user to select a plane or planar face
        try:
            selection = ui.selectEntity(
                'Select a Plane or Face for the Canvas', 'PlanarFaces,ConstructionPlanes'
            )
            target_plane = selection.entity
        except:
            return

        # 2. Prompt the user to select an image
        fileDialog = ui.createFileDialog()
        fileDialog.isMultiSelectEnabled = False
        fileDialog.title  = 'Select Image to Desaturate'
        fileDialog.filter = 'Image Files (*.png *.jpg *.bmp *.jpeg)'
        if fileDialog.showOpen() != adsk.core.DialogResults.DialogOK:
            return

        original_image_path = fileDialog.filename

        # 3. Ask for conversion settings
        contrast, brightness = _ask_conversion_settings()

        # 4. Convert to greyscale and save alongside the original
        orig_dir  = os.path.dirname(original_image_path)
        name_only = os.path.splitext(os.path.basename(original_image_path))[0]
        new_path  = os.path.join(orig_dir, f'{name_only}_greyscale.png')

        try:
            _to_greyscale(original_image_path, new_path, contrast, brightness)
        except Exception as e:
            ui.messageBox(f'Error processing image:\n\n{e}')
            return

        # 5. Bring the new image into Fusion as a Canvas
        activeComp  = design.activeComponent
        canvasInput = activeComp.canvases.createInput(new_path, target_plane)
        canvasInput.isSymmetric = True
        canvasInput.opacity     = 50
        canvas = activeComp.canvases.add(canvasInput)

        if canvas:
            # Force Fusion to process pending UI changes so the canvas exists in the tree
            adsk.doEvents()

            # Assembly proxy fix: inside a sub-component we must select the proxy, not the native object
            canvas_to_select = canvas
            if design.activeOccurrence:
                try:
                    canvas_to_select = canvas.createForAssemblyContext(design.activeOccurrence)
                except:
                    pass

            try:
                ui.activeSelections.clear()
                ui.activeSelections.add(canvas_to_select)
            except:
                pass

            ui.messageBox(
                f'Success! Greyscale canvas inserted.\n\n'
                f'Settings used:  contrast={contrast}  brightness={brightness}\n\n'
                f'Permanent file saved to:\n{new_path}\n\n'
                f"To adjust it, dismiss this box, right-click the canvas in the browser "
                f"tree, and choose 'Edit Canvas'.",
                'CanvasGreyscale Complete'
            )

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
