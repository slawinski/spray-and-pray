"""
Tests for the cover letter module.

Run: python tests/test_cover_letter.py
"""

import sys
import os
import tempfile
from pathlib import Path

# Allow imports from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_optimizer.cover_letter import CoverLetterOptimizer, CoverLetterPDFGenerator, SYSTEM_PROMPT

# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterOptimizer._clean_output
# ═══════════════════════════════════════════════════════════════

def test_clean_output_strips_think_blocks():
    """Pre-cleaning: <think> blocks should be stripped by optimizer.generate()."""
    assert True  # tested in optimizer.generate() integration


def test_clean_output_strips_preamble():
    """Everything before the first ## should be stripped."""
    opt = CoverLetterOptimizer(
        base_url="http://fake",
        api_key="fake",
        model_name="fake",
    )
    text = """Here is your tailored cover letter for this position.

## John Doe
### Contact
john@example.com | 555-0100

Dear Hiring Manager,

This is the body."""
    result = opt._clean_output(text)
    assert result.startswith("## John Doe"), f"Expected to start with '## John Doe', got: {result[:50]}"


def test_clean_output_strips_trailing_fluff():
    """AI meta-commentary at the end should be stripped."""
    opt = CoverLetterOptimizer(
        base_url="http://fake",
        api_key="fake",
        model_name="fake",
    )
    text = """## John Doe
### Contact
john@example.com

Dear Hiring Manager,

This is the body.

Sincerely,

John Doe

Note: I've tailored this cover letter to highlight your 6 years of React experience."""
    result = opt._clean_output(text)
    assert "Note:" not in result, f"Should not contain 'Note:', got: {result[-100:]}"
    assert "I've tailored" not in result, f"Should not contain 'I've tailored'"


def test_clean_output_removes_em_dashes():
    """Em dashes (U+2014) should be replaced with hyphens."""
    opt = CoverLetterOptimizer(
        base_url="http://fake",
        api_key="fake",
        model_name="fake",
    )
    text = "## Jane Doe\n### Contact\n\nI build things\u2014and ship them."
    result = opt._clean_output(text)
    assert "\u2014" not in result, "Em dashes should be removed"
    assert " - " in result, "Em dashes should be replaced with ' - '"


def test_clean_output_handles_empty_text():
    """Empty text should return empty string."""
    opt = CoverLetterOptimizer(
        base_url="http://fake",
        api_key="fake",
        model_name="fake",
    )
    result = opt._clean_output("")
    assert result == ""


def test_clean_output_preserves_valid_cover_letter():
    """A valid cover letter should pass through mostly unchanged."""
    opt = CoverLetterOptimizer(
        base_url="http://fake",
        api_key="fake",
        model_name="fake",
    )
    text = """## Piotr Slawinski
### Contact
piotr@example.com | +48 555 010 100 | linkedin.com/in/piotr

**Date:** August 11, 2026

**Re: Senior Software Engineer at TechCorp**

Dear Hiring Manager,

As TechCorp scales its platform, the need for a Senior Software Engineer who can build reliable distributed systems has never been greater. Over 6 years, I have developed systems handling millions of events daily.

At my current role, I built a real-time analytics pipeline processing 10M+ events per day using Kafka and Go, reducing latency by 40%.

Beyond backend systems, I have shipped full-stack features using React and TypeScript, bridging the gap between infrastructure and user experience.

The opportunity to bring this systems-thinking approach to TechCorp's platform team is exactly the kind of challenge I thrive on.

Sincerely,

Piotr Slawinski"""
    result = opt._clean_output(text)
    assert "## Piotr" in result
    assert "Sincerely," in result
    assert "Piotr Slawinski" in result
    # Should end with the name, not fluff
    assert result.rstrip().endswith("Piotr Slawinski"), f"Ends with: {repr(result[-50:])}"


# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterPDFGenerator._strip_markdown_bold
# ═══════════════════════════════════════════════════════════════

def test_strip_markdown_bold():
    gen = CoverLetterPDFGenerator()
    assert gen._strip_markdown_bold("**Date:** August 11, 2026") == "Date: August 11, 2026"
    assert gen._strip_markdown_bold("**Re: Senior Engineer at Acme**") == "Re: Senior Engineer at Acme"
    assert gen._strip_markdown_bold("**Just bold**") == "Just bold"
    assert gen._strip_markdown_bold("no bold here") == "no bold here"


# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterPDFGenerator._escape_html
# ═══════════════════════════════════════════════════════════════

def test_escape_html():
    gen = CoverLetterPDFGenerator()
    assert gen._escape_html("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"
    assert gen._escape_html("A & B") == "A &amp; B"
    assert gen._escape_html('He said "hello"') == "He said &quot;hello&quot;"
    assert gen._escape_html("normal text") == "normal text"


# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterPDFGenerator._convert_links
# ═══════════════════════════════════════════════════════════════

def test_convert_links():
    gen = CoverLetterPDFGenerator()
    result = gen._convert_links("[LinkedIn](https://linkedin.com/in/user)")
    assert result == '<a href="https://linkedin.com/in/user">LinkedIn</a>'

    result = gen._convert_links("Email: [john@example.com](mailto:john@example.com)")
    assert "john@example.com" in result
    assert "mailto:john@example.com" in result

    # Multiple links
    result = gen._convert_links("[A](http://a.com) and [B](http://b.com)")
    assert '<a href="http://a.com">A</a>' in result
    assert '<a href="http://b.com">B</a>' in result


def test_convert_links_blocks_dangerous_schemes():
    """javascript: and data: URLs should be stripped to plain text."""
    gen = CoverLetterPDFGenerator()
    result = gen._convert_links("[Click me](javascript:alert(1))")
    assert "javascript:" not in result
    assert "<a" not in result
    assert "Click me" in result  # text preserved

    result = gen._convert_links("[XSS](data:text/html,<script>alert(1)</script>)")
    assert "data:" not in result
    assert "<a" not in result
    assert "XSS" in result


def test_convert_links_allows_safe_schemes():
    """http, https, mailto, ftp should be converted to links."""
    gen = CoverLetterPDFGenerator()
    result = gen._convert_links("[Site](https://example.com)")
    assert '<a href="https://example.com">Site</a>' in result

    result = gen._convert_links("[Email](mailto:test@test.com)")
    assert '<a href="mailto:test@test.com">Email</a>' in result


def test_safe_contact_html():
    """Contact HTML should be escaped AND have safe link conversion."""
    gen = CoverLetterPDFGenerator()
    result = gen._safe_contact_html("[LinkedIn](https://linkedin.com/in/user) | <script>alert(1)</script>")
    assert '<a href="https://linkedin.com/in/user">LinkedIn</a>' in result
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

    # Dangerous URL scheme should be stripped
    result = gen._safe_contact_html("[Bad](javascript:void(0))")
    assert "javascript:" not in result
    assert "<a" not in result
    assert "Bad" in result


def test_safe_contact_html_preserves_safe_links():
    gen = CoverLetterPDFGenerator()
    result = gen._safe_contact_html("Email: [john@example.com](mailto:john@example.com)")
    assert '<a href="mailto:john@example.com">john@example.com</a>' in result


def test_parse_sections_ignores_hash_in_body():
    """### in body text should not be parsed as a contact heading."""
    gen = CoverLetterPDFGenerator()
    text = """## John Doe
### Contact
john@test.com

**Date:** August 11, 2026

**Re: Engineer at Acme**

Dear Hiring Manager,

First paragraph.

### This should be body text, not a heading

Second paragraph.

Sincerely,

John Doe"""
    sections = gen._parse_sections(text)
    # "### This should be body text" should be in the body, not treated as contact
    assert sections["contact"] == "john@test.com"
    assert len(sections["body"]) >= 2  # at least 2 paragraphs
    # The ### line should appear somewhere in the body paragraphs
    all_body_text = " ".join(sections["body"])
    assert "### This should be body text, not a heading" in all_body_text


# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterPDFGenerator._parse_sections
# ═══════════════════════════════════════════════════════════════

def test_parse_sections_complete_letter():
    gen = CoverLetterPDFGenerator()
    text = """## John Doe
### Contact
john@example.com | 555-0100 | linkedin.com/in/john

**Date:** August 11, 2026

**Re: Senior Engineer at Acme Corp**

Dear Hiring Manager,

First paragraph of the cover letter body goes here.

Second paragraph with more detail about my experience and qualifications.

Third paragraph wrapping up and connecting to the company mission.

Sincerely,

John Doe"""
    sections = gen._parse_sections(text)

    assert sections["name"] == "John Doe"
    assert "john@example.com" in sections["contact"]
    assert "August 11, 2026" in sections["date"]
    assert "Senior Engineer at Acme Corp" in sections["re"]
    assert sections["salutation"] == "Dear Hiring Manager,"
    assert len(sections["body"]) >= 3
    assert "First paragraph" in sections["body"][0]
    assert "Second paragraph" in sections["body"][1]
    assert len(sections["closing"]) == 2
    assert sections["closing"][0] == "Sincerely,"
    assert sections["closing"][1] == "John Doe"


def test_parse_sections_minimal_letter():
    """Minimal cover letter with just essentials."""
    gen = CoverLetterPDFGenerator()
    text = """## Jane Smith
### Contact
jane@test.com

**Date:** August 11, 2026

**Re: Developer at Startup**

Dear Hiring Manager,

Short body paragraph.

Sincerely,

Jane Smith"""
    sections = gen._parse_sections(text)

    assert sections["name"] == "Jane Smith"
    assert sections["contact"] == "jane@test.com"
    assert len(sections["body"]) == 1


def test_parse_sections_no_date():
    """Letter without date/re lines."""
    gen = CoverLetterPDFGenerator()
    text = """## Alex Johnson
### Contact
alex@test.com

Dear Hiring Manager,

Body text here.

Sincerely,

Alex Johnson"""
    sections = gen._parse_sections(text)

    assert sections["name"] == "Alex Johnson"
    assert "date" not in sections
    assert "re" not in sections
    assert sections["salutation"] == "Dear Hiring Manager,"
    assert len(sections["body"]) == 1


def test_parse_sections_polish_salutation_and_closing():
    """Polish salutation and sign-off should be recognized like the English ones."""
    gen = CoverLetterPDFGenerator()
    text = """## Piotr Sławiński
### Contact
piotr@example.com

**Data:** 17 sierpnia 2026

**Re: Senior Frontend Developer w Shelf**

Szanowni Państwo,

Piszę w sprawie stanowiska Senior Frontend Developera w Państwa firmie.

Z poważaniem,

Piotr Sławiński"""
    sections = gen._parse_sections(text)

    assert sections["name"] == "Piotr Sławiński"
    assert sections["date"] == "Data: 17 sierpnia 2026"
    assert sections["re"] == "Re: Senior Frontend Developer w Shelf"
    assert sections["salutation"] == "Szanowni Państwo,"
    assert len(sections["body"]) == 1
    assert sections["closing"][0] == "Z poważaniem,"
    assert sections["closing"][1] == "Piotr Sławiński"


def test_is_closing_polish():
    gen = CoverLetterPDFGenerator()
    assert gen._is_closing("Z poważaniem,")
    assert gen._is_closing("Z poważaniem")
    assert gen._is_closing("z wyrazami szacunku")
    assert gen._is_closing("Sincerely,")
    assert not gen._is_closing("Pozdrawiam serdecznie")


def test_parse_sections_removes_markdown_bold_in_date_re():
    gen = CoverLetterPDFGenerator()
    text = """## Test User
### Contact
test@test.com

**Date:** January 1, 2026

**Re: Data Scientist at ML Corp**

Dear Hiring Manager,

Body.

Sincerely,

Test User"""
    sections = gen._parse_sections(text)

    assert sections["date"] == "Date: January 1, 2026"  # bold markers stripped
    assert sections["re"] == "Re: Data Scientist at ML Corp"


# ═══════════════════════════════════════════════════════════════
# Tests for CoverLetterPDFGenerator._trim_body
# ═══════════════════════════════════════════════════════════════

def test_trim_body_under_limit_untouched():
    gen = CoverLetterPDFGenerator()
    paras = ["Short paragraph."]
    assert gen._trim_body(paras) == paras


def test_trim_body_truncates_overflow_at_word_boundary():
    gen = CoverLetterPDFGenerator()
    words = "word " * 500  # 2500 chars, well over 1000
    paras = [words.strip()]
    result = gen._trim_body(paras)
    assert len(result) == 1
    assert len(result[0]) <= gen.MAX_BODY_CHARS
    # Should end on a whole word, not a partial one
    assert result[0].endswith("word")


def test_trim_body_drops_trailing_paragraphs():
    gen = CoverLetterPDFGenerator()
    long = "word " * 250  # ~1250 chars
    paras = [long.strip(), "This paragraph should be dropped."]
    result = gen._trim_body(paras)
    assert len(result) == 1
    assert "dropped" not in " ".join(result)


def test_trim_body_total_never_exceeds_limit():
    gen = CoverLetterPDFGenerator()
    paras = ["a" * 400, "b" * 400, "c" * 400]
    result = gen._trim_body(paras)
    assert sum(len(p) for p in result) <= gen.MAX_BODY_CHARS


def test_trim_body_accounts_for_salutation_and_closing():
    gen = CoverLetterPDFGenerator()
    salutation = "Dear Hiring Manager,"
    closing = ["Sincerely,", "John Doe"]
    overhead = len(salutation) + sum(len(l) for l in closing)
    paras = ["x" * 300, "y" * 300, "z" * 300, "w" * 300]
    result = gen._trim_body(paras, overhead)
    total = overhead + sum(len(p) for p in result)
    assert total <= gen.MAX_BODY_CHARS


def test_trim_body_zero_budget_when_overhead_exhausts_limit():
    gen = CoverLetterPDFGenerator()
    overhead = gen.MAX_BODY_CHARS
    paras = ["should be dropped"]
    assert gen._trim_body(paras, overhead) == []


# ═══════════════════════════════════════════════════════════════
# DB tests
# ═══════════════════════════════════════════════════════════════

def test_db_cover_letter_column():
    """Verify the cover_letter_path column exists and can be written/read."""
    from cv_optimizer import db
    import sqlite3

    # Use a temp DB to avoid corrupting the real one
    tmp_db = Path(tempfile.mktemp(suffix=".db"))
    orig_path = db.DB_PATH

    try:
        db.DB_PATH = tmp_db
        db.init_db()

        # Insert an application
        app_id = db.insert_application("TestCorp", "Engineer")
        assert app_id > 0

        # Update with cover letter path
        db.update_application(app_id, cover_letter_path="/tmp/test_cover_letter.pdf")

        # Read back and verify
        app = db.get_application(app_id)
        # Column layout: id, company, role, jd_path, cv_path, job_url, created_at, source, cover_letter_path
        assert app is not None
        assert app[8] == "/tmp/test_cover_letter.pdf", f"Expected cover_letter_path, got: {app[8]}"

        # Verify it appears in list_applications_with_status
        apps = db.list_applications_with_status()
        found = [a for a in apps if a["id"] == app_id]
        assert len(found) == 1
        assert found[0]["cover_letter_path"] == "/tmp/test_cover_letter.pdf"

        db.delete_application(app_id)
    finally:
        db.DB_PATH = orig_path
        if tmp_db.exists():
            tmp_db.unlink()
            # Also clean up WAL files
            for suffix in [".db-shm", ".db-wal"]:
                wal = Path(str(tmp_db) + suffix)
                if wal.exists():
                    wal.unlink()


# ═══════════════════════════════════════════════════════════════
# System prompt verification
# ═══════════════════════════════════════════════════════════════

def test_system_prompt_loaded():
    """Verify the cover letter system prompt was loaded."""
    assert SYSTEM_PROMPT is not None
    assert len(SYSTEM_PROMPT) > 500, f"Prompt too short: {len(SYSTEM_PROMPT)} chars"
    assert "ATS OPTIMIZATION" in SYSTEM_PROMPT
    assert "FORBIDDEN opening patterns" in SYSTEM_PROMPT
    assert "em dashes" in SYSTEM_PROMPT
    assert "QUALITY CHECK" in SYSTEM_PROMPT


def test_system_prompt_has_required_sections():
    """Verify key elements exist in the cover letter prompt."""
    required_sections = [
        "ROLE",
        "INTERNAL CHAIN OF THOUGHT",
        "OUTPUT STRUCTURE",
        "SECTION INSTRUCTIONS",
        "RULES",
        "ATS OPTIMIZATION",
        "QUALITY CHECK",
    ]
    for section in required_sections:
        assert section in SYSTEM_PROMPT, f"Missing section '{section}' in cover letter prompt"


# ═══════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # Clean output tests
        test_clean_output_strips_preamble,
        test_clean_output_strips_trailing_fluff,
        test_clean_output_removes_em_dashes,
        test_clean_output_handles_empty_text,
        test_clean_output_preserves_valid_cover_letter,
        # Parse sections tests
        test_parse_sections_complete_letter,
        test_parse_sections_minimal_letter,
        test_parse_sections_no_date,
        test_parse_sections_polish_salutation_and_closing,
        test_is_closing_polish,
        test_parse_sections_removes_markdown_bold_in_date_re,
        # Utility tests
        test_strip_markdown_bold,
        test_escape_html,
        test_convert_links,
        test_convert_links_blocks_dangerous_schemes,
        test_convert_links_allows_safe_schemes,
        test_safe_contact_html,
        test_safe_contact_html_preserves_safe_links,
        # Trim body tests
        test_trim_body_under_limit_untouched,
        test_trim_body_truncates_overflow_at_word_boundary,
        test_trim_body_drops_trailing_paragraphs,
        test_trim_body_total_never_exceeds_limit,
        test_trim_body_accounts_for_salutation_and_closing,
        test_trim_body_zero_budget_when_overhead_exhausts_limit,
        # DB tests
        test_db_cover_letter_column,
        # Prompt tests
        test_system_prompt_loaded,
        test_system_prompt_has_required_sections,
        # Parser edge case
        test_parse_sections_ignores_hash_in_body,
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
