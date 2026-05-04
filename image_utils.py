import uuid     # Prevents image overwrite conflicts
from io import BytesIO    # Incoming image (bytes) → file-like object → PIL can read it
from pathlib import Path  # Better than os.path (cleaner + safer)

from PIL import Image, ImageOps   # Pillow (PIL fork) for image processing 
                                        # Image → open/save images
                                        # ImageOps → utilities (resize, rotate, etc.)

PROFILE_PICS_DIR = Path("media/profile_pics")


def process_profile_image(content : bytes) -> str:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original) # Fixes the image orientation (Without this → images may appear rotated)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS) # Makes image: exactly 300×300, crops if needed, keeps good quality # LANCZOS = high-quality resizing

        if img.mode in ("RGBA", "LA", "P"): # Converts to standard RGB
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg" # Generate unique names for image file to avoid collsions and ensure security
        filepath = PROFILE_PICS_DIR / filename # media/profile_pics + filename

        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True) # Creates folder if not exists => parents=True → create full path, exist_ok=True → no error if already exists

        img.save(filepath, "JPEG", quality=85, optimize=True) # Saves optimized JPEG => quality=85 → good balance size/quality, optimize=True → compress better

    return filename # Storing filename in DB not filepath


def delete_profile_image(filename : str | None) -> None:
    if filename is None:
        return
    
    filepath = PROFILE_PICS_DIR / filename

    if filepath.exists():
        filepath.unlink()