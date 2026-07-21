(function () {
  function sanitizeJsonLd(raw) {
    // Escape literal control chars inside JSON strings (some sites emit unescaped newlines)
    let result = '';
    let inString = false;
    let escaped = false;
    for (let i = 0; i < raw.length; i++) {
      const ch = raw[i];
      if (escaped) {
        result += ch;
        escaped = false;
        continue;
      }
      if (ch === '\\') {
        result += ch;
        escaped = true;
        continue;
      }
      if (ch === '"') {
        inString = !inString;
        result += ch;
        continue;
      }
      if (inString && ch === '\n') { result += '\\n'; continue; }
      if (inString && ch === '\r') { result += '\\r'; continue; }
      if (inString && ch === '\t') { result += '\\t'; continue; }
      result += ch;
    }
    return result;
  }

  function extractFromJsonLd() {
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    for (const script of scripts) {
      try {
        const data = JSON.parse(sanitizeJsonLd(script.textContent));
        const items = data["@graph"] || [data];
        for (const item of items) {
          if (item["@type"] === "JobPosting" || item.title) {
            const role = item.title;
            const company =
              item.hiringOrganization?.name ||
              item.hiringOrganization?.legalName;
            const rawJd = item.description || item.jd;
            // Strip HTML tags and decode entities from JSON-LD descriptions
            let jd = rawJd;
            if (jd) {
              const temp = document.createElement('div');
              temp.innerHTML = jd;
              jd = temp.textContent || temp.innerText || '';
            }
            if (role && company && jd) {
              return { role, company, jd };
            }
          }
        }
      } catch {
        continue;
      }
    }
    return null;
  }

  const extractors = {
    "linkedin.com": () => {
      // LinkedIn's DOM changes frequently and has multiple layouts (standalone vs split-view)
      const titleEl =
        document.querySelector(
          ".job-details-jobs-unified-top-card__job-title h1",
        ) ||
        document.querySelector(
          ".job-details-jobs-unified-top-card__job-title",
        ) ||
        document.querySelector(".jobs-unified-top-card__job-title") ||
        document.querySelector(".job-view-layout-jobs-details h2") ||
        document.querySelector(".artdeco-entity-lockup__title") ||
        document.querySelector("h1");

      const companyEl =
        document.querySelector(
          ".job-details-jobs-unified-top-card__company-name a",
        ) ||
        document.querySelector(
          ".job-details-jobs-unified-top-card__company-name",
        ) ||
        document.querySelector(".jobs-unified-top-card__company-name") ||
        document.querySelector(
          ".job-details-jobs-unified-top-card__primary-description a",
        ) ||
        document.querySelector(
          ".jobs-unified-top-card__subtitle-primary-grouping a",
        ) ||
        document.querySelector(
          ".job-details-jobs-unified-top-card__primary-description",
        ) ||
        document.querySelector(".artdeco-entity-lockup__subtitle");

      const descEl =
        document.querySelector("#job-details") ||
        document.querySelector(".jobs-description__content") ||
        document.querySelector(".jobs-description-content__text") ||
        document.querySelector("article");

      if (!titleEl || !companyEl || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!companyEl) missing.push("Company");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: companyEl.innerText.trim(),
        jd: descEl.innerText.trim(),
      };
    },
    "justjoin.it": () => {
      // Try JSON-LD first (most stable)
      const jsonld = extractFromJsonLd();
      if (jsonld && jsonld.role && jsonld.company && jsonld.jd) {
        return jsonld;
      }

      const titleEl = document.querySelector("h1");
      const companyEl = document.querySelector('a[href*="companies="] h2');
      const descEl = document.querySelector("div.mui-n1fnon");

      // Extract tech stack keywords
      let techStack = "";
      const techHeading = Array.from(document.querySelectorAll("h3")).find(
        (el) => el.innerText.trim().toLowerCase() === "tech stack"
      );
      if (techHeading) {
        const container = techHeading.closest(".MuiStack-root");
        if (container) {
          const skills = container.querySelectorAll(
            "h4.MuiTypography-subtitle3"
          );
          const levels = container.querySelectorAll(
            "span.MuiTypography-subtitle5"
          );
          techStack = Array.from(skills)
            .map((skill, i) => {
              const level = levels[i] ? levels[i].innerText.trim() : "";
              return level ? `${skill.innerText.trim()} (${level})` : skill.innerText.trim();
            })
            .join(", ");
        }
      }

      if (!titleEl || !companyEl || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!companyEl) missing.push("Company");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: companyEl.innerText.trim(),
        jd: techStack
          ? descEl.innerText.trim() + "\n\nTECH STACK: " + techStack
          : descEl.innerText.trim(),
      };
    },
    "nofluffjobs.com": () => {
      const jsonld = extractFromJsonLd();
      if (jsonld && jsonld.role && jsonld.company && jsonld.jd) {
        return jsonld;
      }

      const titleEl = document.querySelector("common-posting-header h1");
      const companyLink = document.querySelector("#postingCompanyUrl");
      const descEl =
        document.querySelector("#posting-description") ||
        document.querySelector('[data-cy-section="JobOffer_Requirements"]');

      // Extract requirements from the requirements section
      let techStack = "";
      const reqSection = document.querySelector(
        '[data-cy-section="JobOffer_Requirements"]'
      );
      if (reqSection) {
        const reqItems = reqSection.querySelectorAll("ul li");
        techStack = Array.from(reqItems)
          .map((li) => li.innerText.trim())
          .filter((t) => t && !t.match(/^(Oryginalny|Pokaż|What you|Nice to|Substantial|Strong|Hands|Experience|Solid|Commercial|Exposure)/))
          .map((t) => t.replace(/&nbsp;/g, " ").trim())
          .join(", ");
      }

      if (!titleEl || !companyLink || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!companyLink) missing.push("Company");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: companyLink.innerText.trim(),
        jd: techStack
          ? descEl.innerText.trim() + "\n\nREQUIREMENTS: " + techStack
          : descEl.innerText.trim(),
      };
    },
    "theprotocol.it": () => {
      const roleEl = document.querySelector('[data-test="text-offerTitle"]');

      const companyEl = document.querySelector(
        '[data-test="text-offerEmployer"]',
      );
      // Company name is inside the <a>, after the "Firma: " <span> — grab it cleanly.
      const company = (() => {
        if (!companyEl) return null;
        const link = companyEl.querySelector("a");
        if (!link) return companyEl.innerText.trim();
        const clone = link.cloneNode(true);
        const label = clone.querySelector("span");
        if (label) label.remove();
        return clone.innerText.trim();
      })();

      const sectionSelectors = [
        '[data-test="section-about-project"]',
        '[data-test="section-requirements"]',
        '[data-test="section-requirements-expected"]',
        '[data-test="section-responsibilities"]',
        '[data-test="section-offered"]',
        '[data-test="section-benefits"]',
        '[data-test="section-technologies"]',
      ];

      const descParts = [];
      for (const sel of sectionSelectors) {
        const el = document.querySelector(sel);
        if (el) {
          descParts.push(el.innerText.trim());
        }
      }

      if (!roleEl || !company || descParts.length === 0) {
        const missing = [];
        if (!roleEl) missing.push("Role");
        if (!company) missing.push("Company");
        if (descParts.length === 0) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      const role = roleEl.innerText.trim();

      return {
        role: role,
        company: company,
        jd: descParts.join("\n\n"),
      };
    },
    "greenhouse.io": () => {
      const jsonld = extractFromJsonLd();
      if (jsonld && jsonld.role && jsonld.company && jsonld.jd) {
        return jsonld;
      }

      const titleEl =
        document.querySelector("h1.section-header--large") ||
        document.querySelector(".job__title h1");

      let company = "";
      const companyMatch = document.title.match(/at\s+(.+)$/);
      if (companyMatch) {
        company = companyMatch[1].trim();
      } else {
        const logoAlt = document.querySelector(".logo")?.alt || "";
        company = logoAlt.replace(/\s*Logo\s*$/i, "").trim();
      }
      if (!company) {
        const pathParts = window.location.pathname.split("/").filter(Boolean);
        if (pathParts.length > 0) {
          company = pathParts[0]
            .split("-")
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
            .join(" ");
        }
      }

      const descEl = document.querySelector(".job__description");
      const locationEl = document.querySelector(".job__location div");

      let jd = descEl ? descEl.innerText.trim() : "";
      if (locationEl && locationEl.innerText.trim()) {
        jd = "Location: " + locationEl.innerText.trim() + "\n\n" + jd;
      }

      if (!titleEl || !company || !jd) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!company) missing.push("Company");
        if (!jd) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: company,
        jd: jd,
      };
    },
  };

  const hostname = window.location.hostname;
  let extractor = null;

  // Check if the current domain matches any supported extractor strategy
  for (const domain in extractors) {
    if (hostname.includes(domain)) {
      extractor = extractors[domain];
      break;
    }
  }

  if (!extractor) {
    const jsonld = extractFromJsonLd();
    if (jsonld && jsonld.role && jsonld.company && jsonld.jd) {
      return jsonld;
    }
    return { error: "Unsupported Job Board" };
  }

  // Execute the strategy and return the object
  return extractor();
})();
