"""
Verify the path resolution logic in callout_detector._build_page_image_index
matches what save_page_images stores.
"""
from pathlib import Path

# Simulate what save_page_images would produce
output_dir = Path('outputs/Art-and-Culture-Print-Friendly-Sample')  # example output dir
images_dir = output_dir / 'page_images'
img_path = images_dir / 'page_001.png'

# What gets stored in image_meta['path']:
stored_path = str(img_path.relative_to(output_dir.parent))
print(f"stored path: {stored_path!r}")
# Should be: 'Art-and-Culture-Print-Friendly-Sample/page_images/page_001.png'

# What _build_page_image_index resolves it to:
# abs_path = output_dir.parent / rel_path
resolved = output_dir.parent / stored_path
print(f"resolved:    {resolved}")
print(f"matches:     {resolved == img_path.resolve() or str(resolved) == str(img_path)}")

# For the extracted JSON case (no subdir, just outputs/ as output_dir):
output_dir2 = Path('outputs')
images_dir2 = output_dir2 / 'page_images'
img_path2 = images_dir2 / 'page_001.png'
stored_path2 = str(img_path2.relative_to(output_dir2.parent))
print(f"\n[flat case] stored: {stored_path2!r}")
resolved2 = output_dir2.parent / stored_path2
print(f"resolved:   {resolved2}")
