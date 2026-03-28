"""TIFF stack loader for real microscopy data.

Supports loading multi-frame TIFF stacks as 3D numpy arrays suitable
for SOFI processing. Uses tifffile when available, with Pillow as
a fallback.
"""

import numpy as np


def load_tiff_stack(filepath: str) -> np.ndarray:
    """Load a multi-frame TIFF stack as a 3D numpy array.

    Attempts to use tifffile for best compatibility with scientific
    TIFF formats (BigTIFF, OME-TIFF, ImageJ stacks). Falls back to
    Pillow if tifffile is not installed.

    Args:
        filepath: Path to .tif/.tiff file.

    Returns:
        (T, H, W) float64 array of frames.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be read as a TIFF stack.
    """
    try:
        import tifffile
        stack = tifffile.imread(filepath)
    except ImportError:
        # Fallback to PIL/Pillow
        from PIL import Image
        img = Image.open(filepath)
        frames = []
        try:
            while True:
                frames.append(np.array(img, dtype=np.float64))
                img.seek(img.tell() + 1)
        except EOFError:
            pass
        if not frames:
            raise ValueError(f"No frames found in TIFF file: {filepath}")
        stack = np.array(frames)

    if stack.ndim == 2:
        stack = stack[np.newaxis, :, :]

    return stack.astype(np.float64)
