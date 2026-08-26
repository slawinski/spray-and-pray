"""PDFExtractor behavior: PDFs via pymupdf, non-PDF files as plain text."""

import pymupdf

from cv_optimizer.extractor import PDFExtractor


def test_markdown_jd_read_as_text(tmp_path):
    jd = tmp_path / "job_description.md"
    content = "# Role\n\nCompany: X\n\n---\n\n" + "We need a frontend engineer. " * 10
    jd.write_text(content, encoding="utf-8")
    extracted = PDFExtractor.extract_text(str(jd))
    assert "We need a frontend engineer" in extracted
    assert "# Role" in extracted


def test_txt_jd_read_as_text(tmp_path):
    jd = tmp_path / "jd.txt"
    content = "Plain text JD from the browser extension. " * 10
    jd.write_text(content, encoding="utf-8")
    assert PDFExtractor.extract_text(str(jd)) == content


def test_real_pdf_still_extracted(tmp_path):
    pdf = tmp_path / "jd.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Senior Frontend Engineer - React PDF JD")
    doc.save(str(pdf))
    doc.close()

    extracted = PDFExtractor.extract_text(str(pdf))
    assert "Senior Frontend Engineer" in extracted
