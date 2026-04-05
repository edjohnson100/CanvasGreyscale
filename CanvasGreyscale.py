"""
CanvasGreyscale: Because Project Salvador shouldn't have to guess
High-Contrast Canvas Pre-Processing Utility
Last update: 2026-04-05 03:22 PM

- features:
    - Workflow: Native Entity Selection (Planar Only) -> Local File Dialog
    - Engine: Python Pillow ('L' to 'RGB' Desaturation) -> Permanent Local Save
    - Output: 50% Opacity Greyscale Canvas (Optimized for Salvador Tracing)
"""

import adsk.core, adsk.fusion, traceback
import os
import subprocess
import sys
import platform

# Auto-install Pillow if it's not present in Fusion's environment
try:
    from PIL import Image
except ImportError:
    app = adsk.core.Application.get()
    ui = app.userInterface
    ui.messageBox('Pillow library not found. Installing now... this might take a few seconds.')
    
    fusion_dir = os.path.dirname(sys.executable)
    if platform.system() == "Windows":
        python_path = os.path.join(fusion_dir, "Python", "python.exe")
    else:
        python_path = os.path.join(fusion_dir, "..", "Frameworks", "Python.framework", "Versions", "Current", "bin", "python3")
        
    try:
        subprocess.check_call([python_path, "-m", "pip", "install", "Pillow"])
        from PIL import Image
    except Exception as e:
        ui.messageBox(f'Failed to install Pillow.\nError: {e}')

# Global variables for logging
app = adsk.core.Application.get()
ui  = app.userInterface

def log_msg(msg):
    """Writes a debug message to Fusion's Text Command Palette."""
    try:
        palettes = ui.palettes
        textPalette = palettes.itemById('TextCommands')
        if textPalette:
            textPalette.writeText(f"CanvasGreyscale: {msg}")
    except:
        pass

def run(context):
    try:
        # log_msg("--- Script Started ---")
        design = app.activeProduct

        if not design:
            # log_msg("ERROR: No active design found.")
            ui.messageBox('Please open a design before running this script.', 'No Active Design')
            return

        # 1. Prompt the user to select a plane or planar face FIRST
        # log_msg("Prompting user to select a plane...")
        try:
            selection = ui.selectEntity('Select a Plane or Face for the Canvas', 'PlanarFaces,ConstructionPlanes')
            target_plane = selection.entity
            # log_msg("Target plane selected successfully.")
        except:
            # log_msg("User canceled plane selection. Exiting.")
            return

        # 2. Prompt the user to select an image
        # log_msg("Prompting user to select an image file...")
        fileDialog = ui.createFileDialog()
        fileDialog.isMultiSelectEnabled = False
        fileDialog.title = "Select Image to Desaturate"
        fileDialog.filter = 'Image Files (*.png *.jpg *.bmp *.jpeg)'
        dialogResult = fileDialog.showOpen()

        if dialogResult == adsk.core.DialogResults.DialogOK:
            original_image_path = fileDialog.filename
            # log_msg(f"Original image selected: {original_image_path}")
        else:
            # log_msg("User canceled image selection. Exiting.")
            return

        # 3. Desaturate the image using Pillow and save locally
        # log_msg("Processing image with Pillow...")
        try:
            img = Image.open(original_image_path)
            
            # Convert to Luminance (desaturate), then back to RGB to satisfy Fusion's texture engine requirements
            gray_img = img.convert('L').convert('RGB') 
            # log_msg("Image converted to Greyscale RGB.")

            # Construct the new permanent file path
            orig_dir = os.path.dirname(original_image_path)
            orig_name = os.path.basename(original_image_path)
            name_only, ext = os.path.splitext(orig_name)
            
            # Force .png format for the output to ensure maximum compatibility with Fusion Canvases
            new_filename = f"{name_only}_greyscale.png"
            new_path = os.path.join(orig_dir, new_filename)
            
            gray_img.save(new_path, format="PNG")
            # log_msg(f"Greyscale image saved permanently to: {new_path}")
            
        except Exception as e:
            # log_msg(f"ERROR processing image: {str(e)}")
            ui.messageBox(f'Error processing image:\n\n{str(e)}')
            return

        # 4. Bring the new image into Fusion as a Canvas
        # log_msg("Creating canvas input data...")
        activeComp = design.activeComponent
        
        canvasInput = activeComp.canvases.createInput(new_path, target_plane)
        canvasInput.isSymmetric = True
        canvasInput.opacity = 50 

        canvas = activeComp.canvases.add(canvasInput)
        
        if canvas:
            # Force Fusion to process pending UI changes so the canvas exists in the tree
            adsk.doEvents() 
            
            # The Magic Proxy Fix
            canvas_to_select = canvas
            if design.activeOccurrence:
                # We are inside a subcomponent. We must select the "Proxy" hologram, not the native object.
                try:
                    canvas_to_select = canvas.createForAssemblyContext(design.activeOccurrence)
                except:
                    pass
            
            try:
                ui.activeSelections.clear()
                ui.activeSelections.add(canvas_to_select)
            except:
                pass # Absolute last resort fallback
            
            # Display final success and instruction dialog
            success_msg = (
                f"Success! Greyscale canvas inserted.\n\n"
                f"Permanent file saved to:\n{new_path}\n\n"
                f"To adjust it, dismiss this box, right-click the canvas in the browser tree, and choose 'Edit Canvas'."
            )
            ui.messageBox(success_msg, 'CanvasGreyscale Complete')
            
        else:
            pass
            # log_msg("--- WARNING: Command executed, but canvas object was not returned. ---")

    except:
        err_msg = traceback.format_exc()
        # log_msg(f"CRITICAL EXCEPTION:\n{err_msg}")
        if ui:
            ui.messageBox('Failed:\n{}'.format(err_msg))