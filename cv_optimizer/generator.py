import logging
import fitz
import markdown
import re
from typing import Dict, List

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
    display: flex;
    align-items: center;
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
    font-size: 8pt;
    color: #777;
    margin-top: 30px;
}
.disclaimer p { font-size: 8pt; }
"""

class PDFGenerator:
    def generate(self, markdown_text: str, output_path: str) -> None:
        """Converts Markdown to a two-column PDF matching example.pdf."""
        logger.info(f"Generating two-column PDF to {output_path}...")
        
        try:
            sections = self._parse_to_html_sections(markdown_text)
            
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
            main_keys = ["Summary", "Experience", "Education", "Community"]
            main_html_parts = []
            for key in main_keys:
                if key in sections:
                    main_html_parts.append(f'<h2>{key}</h2>{sections[key]}')
            
            if "GDPR Disclaimer" in sections:
                main_html_parts.append(f'<div class="disclaimer"><h2>GDPR Disclaimer</h2>{sections["GDPR Disclaimer"]}</div>')
            
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
            
            # Header
            header_rect = fitz.Rect(margin, margin, page_width - margin, margin + header_height)
            header_html = f"""
            <div class="header">
                <h1>{sections.get('[Name]', 'Name')}</h1>
                <p>{sections.get('[Professional Title]', '')}</p>
            </div>
            """
            page.insert_htmlbox(header_rect, header_html, css=CV_CSS)
            
            # Sidebar
            sidebar_x1 = main_x1 + main_width + gutter
            sidebar_rect = fitz.Rect(sidebar_x1, margin + header_height + 10, page_width - margin, page_height - margin)
            sidebar_keys = ["Personal Info", "Skills", "Languages", "Hobbies"]
            sidebar_html_parts = []
            for key in sidebar_keys:
                if key in sections:
                    sidebar_html_parts.append(f'<h2>{key}</h2>{sections[key]}')
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

    def _parse_to_html_sections(self, text: str) -> Dict[str, str]:
        sections = {}
        # Remove any Markdown link syntax [text](url) -> <a href="url">text</a> for sidebar links
        # But for main column, we might want just text. Let's keep it simple first.
        
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
                current_section = self._normalize_key(line[3:].strip())
                section_lines = []
                continue
            
            section_lines.append(line)
            
        if section_lines:
            sections[current_section] = self._md_to_html("\n".join(section_lines), current_section)
            
        return sections

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
        lowered = key.lower()
        if "experience" in lowered or "employment" in lowered: return "Experience"
        if "profile" in lowered or "summary" in lowered: return "Summary"
        if "contact" in lowered or "detail" in lowered or "personal" in lowered or "link" in lowered: return "Personal Info"
        if "skill" in lowered: return "Skills"
        if "edu" in lowered: return "Education"
        if "extracurricular" in lowered or "community" in lowered or "activities" in lowered: return "Community"
        if "disclaimer" in lowered or "gdpr" in lowered: return "GDPR Disclaimer"
        if "hobby" in lowered or "hobbies" in lowered: return "Hobbies"
        if "language" in lowered: return "Languages"
        return key
