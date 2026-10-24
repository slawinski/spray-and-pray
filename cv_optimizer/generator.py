import html
import logging
import fitz
import markdown
import re
from pathlib import Path
from typing import Dict, List

from cv_optimizer.config import settings

logger = logging.getLogger(__name__)

# Combined CSS to match example.pdf precisely
CV_CSS = """
body {
    font-family: Helvetica, Arial, sans-serif;
    color: #333;
    line-height: 1.4;
    margin: 0;
    padding: 0;
}

.header {
    margin-bottom: 25px;
}
.header h1 {
    margin: 0;
    font-size: 32pt;
    color: #000;
    font-weight: bold;
}
.header p {
    margin: 5px 0;
    font-size: 13pt;
    color: #444;
    font-weight: normal;
}

/* Icons for headers */
.icon {
    font-family: "Apple Color Emoji", "Segoe UI Emoji", sans-serif;
    margin-right: 8px;
    font-size: 14pt;
}

/* Main Column Styles */
.main-column {
    font-size: 10.5pt;
    line-height: 1.5;
    color: #333;
}
.main-column p, .main-column li { font-size: 10.5pt; }
.main-column a { color: #0077b5; text-decoration: none; }
.main-column h2 {
    font-size: 15pt;
    color: #000;
    margin-top: 20px;
    margin-bottom: 10px;
    font-weight: bold;
}
.main-column h3 {
    font-size: 11pt;
    margin-top: 15px;
    margin-bottom: 2px;
    font-weight: bold;
    color: #222;
}
.main-column strong {
    color: #666;
    font-weight: bold;
    font-size: 9.5pt;
}
.main-column p { margin: 5px 0; }
.main-column ul { padding-left: 20px; margin-top: 15px; }
.main-column li { margin-bottom: 3px; }

.main-column blockquote { margin: 0; padding: 0; }
.main-column blockquote p {
    margin: 4px 0;
    font-size: 10.5pt;
    line-height: 1.35;
}
.main-column blockquote strong { font-size: 10.5pt; color: #222; }

/* Sidebar Column Styles */
.sidebar-column {
    font-size: 9.5pt;
    line-height: 1.4;
    color: #333;
}
.sidebar-column p, .sidebar-column li { font-size: 9.5pt; }
.sidebar-column h2 { 
    font-size: 13pt; 
    color: #000;
    margin-top: 0;
    margin-bottom: 8px;
    font-weight: bold;
}
.sidebar-column p { margin: 4px 0; }
.sidebar-column a { color: #0077b5; text-decoration: none; }
.sidebar-column ul { list-style-type: none; padding-left: 0; margin-top: 5px; }
.sidebar-column li { margin-bottom: 6px; }

/* Disclaimer */
.disclaimer {
    font-size: 9pt;
    color: #777;
    margin-top: 30px;
}
.disclaimer p { font-size: 9pt; }
"""

class PDFGenerator:
    def generate(self, markdown_text: str, output_path: str, photo_path: str | None = None) -> None:
        """Converts Markdown to a two-column PDF matching example.pdf."""
        logger.info(f"Generating two-column PDF to {output_path}...")
        
        try:
            sections, headings = self._parse_to_html_sections(markdown_text)
            
            # Layout Configuration
            margin = 40
            gutter = 30
            header_height = 90
            sidebar_width = 140
            page_width = 595
            page_height = 842
            mediabox = fitz.Rect(0, 0, page_width, page_height)
            
            main_x1 = margin
            main_width = page_width - (2 * margin) - sidebar_width - gutter
            
            # Build main column HTML
            main_keys = ["Summary", "Home Baking Practice", "Workshops", "Experience", "Education", "Community"]
            main_html_parts = []
            for key in main_keys:
                if key in sections:
                    main_html_parts.append(f'<h2>{self._heading(headings, key)}</h2>{sections[key]}')
            
            if "GDPR Disclaimer" in sections:
                main_html_parts.append(f'<div class="disclaimer"><h2>{self._heading(headings, "GDPR Disclaimer")}</h2>{sections["GDPR Disclaimer"]}</div>')
            
            main_html = f'<div class="main-column">{"".join(main_html_parts)}</div>'
            
            # Phase 1: Render main column with Story into a temp PDF
            # so it flows across pages at the correct font size.
            tmp_path = output_path + ".tmp"
            writer = fitz.DocumentWriter(tmp_path)
            story = fitz.Story(html=main_html, user_css=CV_CSS)
            
            page_num = 0
            more_content = True
            while more_content:
                page_num += 1
                device = writer.begin_page(mediabox)
                
                if page_num == 1:
                    main_y1 = margin + header_height + 10
                    main_rect = fitz.Rect(main_x1, main_y1, main_x1 + main_width, page_height - margin)
                else:
                    main_rect = fitz.Rect(main_x1, margin, main_x1 + main_width, page_height - margin)
                
                more_content, _ = story.place(main_rect)
                story.draw(device)
                writer.end_page()
            
            writer.close()
            
            # Phase 2: Open the temp PDF and overlay header + sidebar on page 1
            doc = fitz.open(tmp_path)
            page = doc[0]
            
            # Header (with optional candidate photo, top-left)
            name = sections.get('[Name]', 'Name')
            title = sections.get('[Professional Title]', '')
            header_html = f"""
            <div class="header">
                <h1>{name}</h1>
                <p>{title}</p>
            </div>
            """

            header_text_x1 = margin
            resolved_photo = photo_path if photo_path is not None else settings.candidate_photo_path
            if resolved_photo and Path(resolved_photo).exists():
                try:
                    # Photo height = natural height of the name + title block.
                    # Neutralize the .header container's bottom margin so the measured
                    # height reflects just the two text elements, not trailing whitespace.
                    measure_css = CV_CSS + "\n.header { margin-bottom: 0; }\n"
                    full_rect = fitz.Rect(margin, margin, page_width - margin, margin + header_height)
                    text_height = self._measure_html_height(header_html, measure_css, full_rect, page_width, page_height)
                    photo_w, photo_h = self._image_size(resolved_photo)
                    if photo_h > 0:
                        photo_gap = 12
                        photo_width = text_height * (photo_w / photo_h)
                        photo_rect = fitz.Rect(margin, margin, margin + photo_width, margin + text_height)
                        page.insert_image(photo_rect, filename=resolved_photo, keep_proportion=True)
                        header_text_x1 = margin + photo_width + photo_gap
                except Exception as e:
                    logger.warning("Failed to insert candidate photo: %s", e)

            header_rect = fitz.Rect(header_text_x1, margin, page_width - margin, margin + header_height)
            page.insert_htmlbox(header_rect, header_html, css=CV_CSS)
            
            # Sidebar
            sidebar_x1 = main_x1 + main_width + gutter
            sidebar_rect = fitz.Rect(sidebar_x1, margin + header_height + 10, page_width - margin, page_height - margin)
            sidebar_keys = ["Personal Info", "Portfolio", "Skills", "Languages", "Hobbies"]
            sidebar_html_parts = []
            for key in sidebar_keys:
                if key in sections:
                    sidebar_html_parts.append(f'<h2>{self._heading(headings, key)}</h2>{sections[key]}')
            sidebar_html = f'<div class="sidebar-column">{"".join(sidebar_html_parts)}</div>'
            page.insert_htmlbox(sidebar_rect, sidebar_html, css=CV_CSS)
            
            doc.save(output_path)
            doc.close()
            
            # Clean up temp file
            import os
            os.remove(tmp_path)
            
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            raise

    @staticmethod
    def _image_size(path: str) -> tuple[float, float]:
        """Returns (width, height) of an image in points."""
        doc = fitz.open(path)
        rect = doc[0].rect
        doc.close()
        return rect.width, rect.height

    @staticmethod
    def _measure_html_height(
        html: str, css: str, rect: fitz.Rect, page_width: float, page_height: float
    ) -> float:
        """Renders HTML off-screen and returns the height actually used (in points)."""
        doc = fitz.open()
        page = doc.new_page(width=page_width, height=page_height)
        result = page.insert_htmlbox(rect, html, css=css)
        # PyMuPDF >= 1.26 returns (unused_height, scale); older returns a float
        remaining = result[0] if isinstance(result, tuple) else result
        doc.close()
        return rect.height - remaining

    def _parse_to_html_sections(self, text: str) -> tuple[Dict[str, str], Dict[str, str]]:
        """Parses markdown into canonical sections plus a heading map.

        Returns (sections, headings) where sections maps a canonical key
        (e.g. "Experience") to HTML content, and headings maps that same
        canonical key to the original section heading text (which may be
        Polish, e.g. "Doświadczenie").
        """
        sections: Dict[str, str] = {}
        headings: Dict[str, str] = {}

        lines = text.split("\n")
        current_section = "Header"
        section_lines = []
        
        for line in lines:
            if line.startswith("# "):
                sections["[Name]"] = line[2:].strip()
                continue
            if line.startswith("### ") and "[Name]" in sections and "[Professional Title]" not in sections:
                sections["[Professional Title]"] = line[4:].strip()
                continue
            
            if line.startswith("## "):
                if section_lines:
                    sections[current_section] = self._md_to_html("\n".join(section_lines), current_section)
                raw_heading = line[3:].strip()
                current_section = self._normalize_key(raw_heading)
                headings[current_section] = raw_heading
                section_lines = []
                continue
            
            section_lines.append(line)

        # Flush the final section
        if section_lines:
            sections[current_section] = self._md_to_html("\n".join(section_lines), current_section)

        # Warn if common sections are missing from parsed output
        for expected in ["Summary", "Experience", "Skills", "Community", "GDPR Disclaimer"]:
            if expected not in sections:
                logger.warning("PDF: section '%s' not found in parsed markdown", expected)
            elif not sections[expected].strip():
                logger.warning("PDF: section '%s' is empty after parsing", expected)

        return sections, headings

    @staticmethod
    def _heading(headings: Dict[str, str], key: str) -> str:
        """Returns the (possibly translated) heading text for a canonical key."""
        return html.escape(headings.get(key, key))

    def _md_to_html(self, md_text: str, section_name: str) -> str:
        """Custom MD to HTML conversion to handle specific layout needs."""
        # For Personal Info, convert markdown links to real HTML <a> tags
        if section_name == "Personal Info":
            md_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', md_text)
        
        html = markdown.markdown(md_text)
        
        # In Experience, bold lines (Dates) should be styled as smaller grey text
        if section_name == "Experience":
            # Find <strong> tags that likely contain dates and wrap them in a styled div/span if needed
            # Or just let CSS handle it if they are unique.
            pass
            
        return html

    def _normalize_key(self, key: str) -> str:
        lowered = key.strip().lower()
        baker_headings = {
            "home baking practice": "Home Baking Practice",
            "domowa praktyka piekarska": "Home Baking Practice",
            "workshops": "Workshops", "warsztaty": "Workshops",
            "portfolio": "Portfolio",
            "other employment": "Experience", "pozostałe zatrudnienie": "Experience",
        }
        if lowered in baker_headings:
            return baker_headings[lowered]
        if "experience" in lowered or "employment" in lowered or "work" in lowered: return "Experience"
        if "profile" in lowered or "summary" in lowered or "about" in lowered: return "Summary"
        if "contact" in lowered or "detail" in lowered or "personal" in lowered or "link" in lowered: return "Personal Info"
        if "skill" in lowered or "tech" in lowered: return "Skills"
        if "edu" in lowered or "degree" in lowered or "university" in lowered: return "Education"
        if "community" in lowered or "extracurricular" in lowered or "activities" in lowered or "volunteer" in lowered or "speaker" in lowered: return "Community"
        if "disclaimer" in lowered or "gdpr" in lowered or "consent" in lowered: return "GDPR Disclaimer"
        if "hobby" in lowered or "hobbies" in lowered or "interest" in lowered: return "Hobbies"
        if "language" in lowered: return "Languages"
        # Polish section headings
        if "doświadcz" in lowered or "zatrudnien" in lowered: return "Experience"
        if "podsumow" in lowered or "profil" in lowered or "o mnie" in lowered: return "Summary"
        if "kontakt" in lowered or "dane osobowe" in lowered: return "Personal Info"
        if "umiejętnoś" in lowered or "kompetencj" in lowered or "technologi" in lowered: return "Skills"
        if "wykształ" in lowered: return "Education"
        if "społecz" in lowered or "wolontari" in lowered or "wystąpien" in lowered or "działalnoś" in lowered: return "Community"
        if "rodo" in lowered or "klauzul" in lowered or "zgoda" in lowered: return "GDPR Disclaimer"
        if "zainteresowan" in lowered or "pasj" in lowered: return "Hobbies"
        if "język" in lowered: return "Languages"
        return key
