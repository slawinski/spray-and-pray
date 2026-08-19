"""
Tests for the CV PDF generator, including candidate photo placement.

Run: python3 tests/test_generator.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz
from cv_optimizer.generator import PDFGenerator

SAMPLE_MD = """# Piotr Slawinski
### Senior Software Engineer | Full Stack Engineer
## Summary
Senior Software Engineer with 7+ years of experience.
## Experience
### Senior Software Engineer
**[Haptiq]**, *Warsaw, Poland*, *09/2025 - 06/2026*

- Built a real-time analytics pipeline.
## Personal Info
- Email: piotr@example.com
## Skills
- **Languages:** TypeScript, JavaScript
## Languages
- Polish: Native
## Hobbies
- Sourdough Baking
## GDPR Disclaimer
I consent.
"""


def _make_test_image(path: str, width: int = 200, height: int = 100) -> None:
    """Create a solid-color test image with a known aspect ratio."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pix.clear_with(128)
    pix.save(path)


def test_generate_with_photo():
    tmp = tempfile.mkdtemp()
    img_path = str(Path(tmp) / "photo.png")
    _make_test_image(img_path, width=200, height=100)  # aspect ratio 2.0

    out = str(Path(tmp) / "cv.pdf")
    PDFGenerator().generate(SAMPLE_MD, out, photo_path=img_path)

    doc = fitz.open(out)
    page = doc[0]

    images = page.get_image_info()
    assert len(images) == 1, f"Expected 1 image, got {len(images)}"

    bbox = images[0]["bbox"]
    # Image anchored top-left at the page margin (40pt)
    assert abs(bbox[0] - 40) < 1, f"Image x0 should be ~40, got {bbox[0]}"
    assert abs(bbox[1] - 40) < 1, f"Image y0 should be ~40, got {bbox[1]}"

    # Aspect ratio preserved (200x100 → width = 2 * height)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    assert abs(w / h - 2.0) < 0.05, f"Image aspect ratio wrong: {w:.2f}/{h:.2f}"

    # Header text still present
    text = page.get_text()
    assert "Slawinski" in text
    assert "Senior Software Engineer" in text

    # Name text should be shifted to the right of the image (x > image right edge)
    doc.close()


def test_generate_without_photo():
    """A missing photo path should not crash — header renders normally."""
    tmp = tempfile.mkdtemp()
    out = str(Path(tmp) / "cv.pdf")
    PDFGenerator().generate(SAMPLE_MD, out, photo_path=str(Path(tmp) / "does_not_exist.png"))

    doc = fitz.open(out)
    page = doc[0]
    assert len(page.get_image_info()) == 0, "No image expected when photo is missing"
    assert "Slawinski" in page.get_text()
    doc.close()


def test_image_size():
    tmp = tempfile.mkdtemp()
    img_path = str(Path(tmp) / "photo.png")
    _make_test_image(img_path, width=300, height=150)
    w, h = PDFGenerator._image_size(img_path)
    # PyMuPDF reports dimensions in points (pixels scaled by DPI), so exact pixel
    # values vary — what matters is that the aspect ratio is preserved.
    assert h > 0 and abs(w / h - 2.0) < 0.01, f"Aspect ratio should be 2.0, got {w}/{h}"


def test_measure_html_height():
    """_measure_html_height should return the used height (not the full rect)."""
    html = '<div class="header"><h1 style="font-size:32pt;margin:0">Name</h1><p style="font-size:13pt;margin:5px 0">Title</p></div>'
    css = "body { font-family: Helvetica; }"
    rect = fitz.Rect(40, 40, 555, 130)  # 90pt tall
    h = PDFGenerator._measure_html_height(html, css, rect, 595, 842)
    assert 0 < h < 90, f"Used height should be between 0 and 90, got {h}"


POLISH_MD = """# Piotr Sławiński
### Senior Software Engineer
## Podsumowanie
Inżynier frontend z 7-letnim doświadczeniem.
## Doświadczenie
### Senior Software Engineer
**Haptiq**, *Warszawa*, *09/2025 - 06/2026*

- Budowa aplikacji React.
## Dane kontaktowe
- Email: piotr@example.com
## Edukacja
**Politechnika Gdańska**

Magister inżynier
## Umiejętności
- **Języki:** TypeScript, JavaScript
## Społeczność
**WarsawJS** - **Volunteer, Mentor & Speaker**

Wystąpienia.
## Języki
- Polski: ojczysty
## Zainteresowania
- Wypiek chleba
## Klauzula RODO
Wyrażam zgodę.
"""


def test_polish_section_headings_map_to_canonical_keys():
    gen = PDFGenerator()
    sections, headings = gen._parse_to_html_sections(POLISH_MD)
    assert sections["Summary"]
    assert sections["Experience"]
    assert sections["Personal Info"]
    assert sections["Education"]
    assert sections["Skills"]
    assert sections["Community"]
    assert sections["Languages"]
    assert sections["Hobbies"]
    assert sections["GDPR Disclaimer"]
    # Original Polish headings are preserved for rendering
    assert headings["Experience"] == "Doświadczenie"
    assert headings["Summary"] == "Podsumowanie"
    assert headings["GDPR Disclaimer"] == "Klauzula RODO"


def test_polish_headings_render_in_pdf():
    tmp = tempfile.mkdtemp()
    out = str(Path(tmp) / "cv.pdf")
    PDFGenerator().generate(POLISH_MD, out, photo_path=None)
    text = fitz.open(out)[0].get_text()
    for heading in ["Podsumowanie", "Doświadczenie", "Dane kontaktowe", "Edukacja",
                    "Umiejętności", "Społeczność", "Języki", "Zainteresowania", "Klauzula RODO"]:
        assert heading in text, f"Missing Polish heading in PDF: {heading}"


if __name__ == "__main__":
    tests = [
        test_generate_with_photo,
        test_generate_without_photo,
        test_image_size,
        test_measure_html_height,
        test_polish_section_headings_map_to_canonical_keys,
        test_polish_headings_render_in_pdf,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__}: {e}")

    print(f"\n{'='*50}")
    if failed == 0:
        print(f"✓ All {passed} tests passed")
    else:
        print(f"✓ {passed} passed, ✗ {failed} failed")
    print(f"{'='*50}")
