"""Synthetic source/layout evidence, not claims about real-model tailoring accuracy."""

import json
import unicodedata
from copy import deepcopy
from pathlib import Path

import fitz
import pytest

from cv_optimizer.generator import PDFGenerator
from cv_optimizer.profiles import resolve_profile
from test_profile_prompts import FakeClient, writer


def many_role_source():
    source = json.loads((Path(__file__).resolve().parent.parent / "master_cv.example.json").read_text())
    roles = []
    for index in range(12):
        software = index < 7
        roles.append({
            "id": f"role-{index}",
            "title": ("Senior Software Engineer for Distributed Platform Reliability and Developer Productivity"
                      if index == 0 else f"{'Software' if software else 'Mechanical Design'} Engineer {index}"),
            "company": ("Synthetic International Research and Software Infrastructure Corporation"
                        if index == 0 else f"Synthetic Employer {index}"),
            "location": "Remote" if software else "Boston",
            "start_date": str(2025 - index), "end_date": str(2026 - index),
            "achievements": ([f"IT achievement sentinel {index}."] if software else
                             [f"Designed engineering fixture {index}.", f"Tested pump assembly {index}."]),
        })
    source["experience"] = roles
    source["profiles"]["baker"]["roles"] = {
        r["id"]: {"detail": "brief", "achievements": []} for r in roles}
    source["profiles"]["it"]["roles"] = {
        r["id"]: {"detail": "detailed", "achievements": r["achievements"]} for r in roles[:7]}
    policy = source["profiles"]["mechanical_engineering"]
    policy["roles"] = {r["id"]: {"detail": "brief" if i < 7 else "detailed",
                                "achievements": r["achievements"]} for i, r in enumerate(roles)}
    policy["cv_role_detail"] = {r["id"]: "ledger" for r in roles[:7]}
    return source


def source_markdown(context, heading="Experience"):
    """Deterministic source preview following the writer's presentation contract."""
    lines = ["# Synthetic Candidate", "### Mechanical Engineer", "## Summary",
             "Approved engineering introduction.", f"## {heading}"]
    for role in context.facts["experience"]:
        title = role.get("title", role.get("role", ""))
        dates = f'{role["start_date"]} - {role["end_date"]}'
        if context.rules["role_detail"][role["id"]] == "ledger":
            lines.extend([f'> **{title}** | {role["company"]} | {role["location"]} | {dates}', ">"])
        else:
            lines.extend([f"### {title}", f'**{role["company"]}**, *{role["location"]}*, *{dates}*', ""])
            lines.extend(f"- {item}" for item in role["achievements"])
        lines.append("")
    return "\n".join(lines)


def normalized_text(doc):
    return " ".join(unicodedata.normalize("NFKC", " ".join(page.get_text() for page in doc)).split())


def flow_position(doc, text):
    """Distance down the main-column flow (662pt on p1, 762pt thereafter)."""
    for index, page in enumerate(doc):
        matches = page.search_for(text)
        if matches:
            return (0 if index == 0 else 662 + (index - 1) * 762) + matches[0].y0 - (140 if index == 0 else 40)
    raise AssertionError(f"Missing text: {text}")


@pytest.mark.parametrize("heading", ["Experience", "Doświadczenie"])
def test_real_pdf_ledger_preserves_identities_detail_order_and_wraps(tmp_path, heading):
    source = many_role_source()
    context = resolve_profile(source, "mechanical_engineering")
    md = source_markdown(context, heading)
    path = tmp_path / "ledger.pdf"
    PDFGenerator().generate(md, str(path), photo_path="")
    with fitz.open(path) as doc:
        text = normalized_text(doc)
        assert "IT achievement sentinel" not in text
        offsets = []
        for role in source["experience"]:
            offsets.append(text.index(role["title"]))
            for value in (role["company"], role["location"], f'{role["start_date"]} - {role["end_date"]}'):
                assert value in text
        assert offsets == sorted(offsets)
        for role in source["experience"][7:]:
            assert all(item in text for item in role["achievements"])
        spans = [span for page in doc for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        title_spans = [s for s in spans if "Senior Software" in s["text"] or "Developer Productivity" in s["text"]]
        assert len(title_spans) >= 2  # long title wraps, rather than truncates or scales
        assert all(s["size"] == pytest.approx(10.5) for s in title_spans)
        for span in spans:
            if span["bbox"][1] >= 140:  # body, not the full-width header
                assert 40 <= span["bbox"][0] < span["bbox"][2] <= 385


def test_ledger_reduces_measured_pdf_flow_and_it_render_is_unchanged(tmp_path):
    source = many_role_source()
    legacy = deepcopy(source)
    del legacy["profiles"]["mechanical_engineering"]["cv_role_detail"]
    generator = PDFGenerator()
    for label, master in [("baseline", legacy), ("ledger", source)]:
        generator.generate(source_markdown(resolve_profile(master, "mechanical_engineering")),
                           str(tmp_path / f"{label}.pdf"), photo_path="")
    with fitz.open(tmp_path / "baseline.pdf") as baseline, fitz.open(tmp_path / "ledger.pdf") as ledger:
        old = flow_position(baseline, "Mechanical Design Engineer 7")
        new = flow_position(ledger, "Mechanical Design Engineer 7")
        assert new < old - 100  # physical reduction, not just a different Markdown spelling
    it_before = source_markdown(resolve_profile(legacy, "it"))
    it_after = source_markdown(resolve_profile(source, "it"))
    assert it_after == it_before
    generator.generate(it_after, str(tmp_path / "it.pdf"), photo_path="")
    with fitz.open(tmp_path / "it.pdf") as doc:
        assert all(f"IT achievement sentinel {i}." in normalized_text(doc) for i in range(7))
    sections, _ = generator._parse_to_html_sections(it_after)
    assert "<blockquote>" not in sections["Experience"]
    assert sections["Experience"].count("<h3>") == 7


def test_interleaved_roles_stay_in_one_experience_section():
    source = many_role_source()
    source["experience"].insert(1, source["experience"].pop(7))
    md = source_markdown(resolve_profile(source, "mechanical_engineering"))
    sections, _ = PDFGenerator()._parse_to_html_sections(md)
    experience = sections["Experience"]
    assert experience.count("<h3>") == 5
    assert experience.count("<blockquote>") == 2
    assert experience.index("Developer Productivity") < experience.index("Mechanical Design Engineer 7") < experience.index("Software Engineer 1")


@pytest.mark.parametrize("language", ["en", "pl"])
def test_cv_writer_receives_no_ledger_achievements_and_uses_explicit_contract(language):
    context = resolve_profile(many_role_source(), "mechanical_engineering")
    expected = source_markdown(context, "Doświadczenie" if language == "pl" else "Experience")
    client = FakeClient(expected)
    assert writer("cv", client)(context, "Engineering vacancy", language) == expected.strip()
    system, user = [message["content"] for message in client.requests[0]["messages"]]
    assert "IT achievement sentinel" not in user
    assert '"ledger"' in user
    assert "ledger" in system and "blockquote" in system
    assert "no achievement bullets or descriptive prose" in system
    assert "Designed engineering fixture 7." in user
