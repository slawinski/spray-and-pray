(function () {
  // These are hosting/recruiting platforms, not evidence of the hiring employer.
  const portalNames = new Set([
    'pracuj', 'pracujpl', 'grupapracuj', 'erecruiter', 'erecruiterpl', 'linkedin', 'indeed',
    'glassdoor', 'justjoinit', 'nofluffjobs', 'theprotocol', 'theprotocolit',
    'greenhouse', 'lever', 'workable', 'smartrecruiters', 'workingnomads',
    'wellfound', 'monster', 'ziprecruiter', 'stepstone', 'jooble', 'adzuna',
  ]);

  function employerName(value) {
    if (typeof value !== 'string') return '';
    const name = value.replace(/\s+/g, ' ').trim();
    const key = name.toLowerCase()
      .replace(/\s+(sp\.?\s*z\.?\s*o\.?\s*o\.?|s\.?a\.?|inc\.?|ltd\.?|llc|limited|corporation)$/i, '')
      .replace(/[^\p{L}\p{N}]/gu, '');
    if (!key || /^(unknown|unknowncompany|na|none|null|confidential|undisclosed)$/.test(key)) return '';
    if (portalNames.has(key) || /\b(job\s*(board|portal|search)|portal pracy|oferty pracy)\b/i.test(name)) return '';
    // A URL or bare domain identifies a website, not an employer name.
    if (/^(https?:\/\/|www\.)/i.test(name) || /^[\w-]+(?:\.[\w-]+)+(?:\/\S*)?$/.test(name)) return '';
    return name;
  }

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
    let fallback = null;
    for (const script of scripts) {
      try {
        const data = JSON.parse(sanitizeJsonLd(script.textContent));
        const items = Array.isArray(data) ? [...data] : [data];
        while (items.length) {
          const item = items.shift();
          if (!item || typeof item !== 'object') continue;
          if (Array.isArray(item['@graph'])) items.push(...item['@graph']);
          const types = Array.isArray(item['@type']) ? item['@type'] : [item['@type']];
          if (types.includes('JobPosting') || (item.title && item.hiringOrganization)) {
            const role = item.title;
            const organization = item.hiringOrganization;
            const company = employerName(organization) ||
              employerName(organization?.name) || employerName(organization?.legalName);
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
            fallback = fallback || { role, company, jd };
          }
        }
      } catch {
        continue;
      }
    }
    return fallback;
  }

  function textOf(el) {
    return el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }

  function titleEmployer() {
    const title = document.querySelector('meta[property="og:title"]')?.getAttribute('content') || document.title;
    // eRecruiter titles are "role, employer, location". Keep employer commas/dashes.
    if (/(^|\.)erecruiter\.pl$/.test(window.location.hostname)) {
      const first = title.indexOf(', '), last = title.lastIndexOf(', ');
      if (first > 0 && last > first) {
        return { role: title.slice(0, first).trim(), company: title.slice(first + 2, last).trim() };
      }
    }
    const at = title.match(/^(.+?)\s+at\s+(.+?)(?:\s+[|•]\s+.*)?$/i);
    return at ? { role: at[1].trim(), company: at[2].trim() } : null;
  }

  function resolveEmployer(candidate) {
    const primary = employerName(candidate) || employerName(extractFromJsonLd()?.company);
    if (primary) return primary;
    for (const selector of [
      '[itemprop="hiringOrganization"] [itemprop="name"]',
      '[itemprop="hiringOrganization"]',
      '[data-test="text-employer-name"]',
      '[data-testid="company-name"]',
      '[data-testid="employer-name"]',
    ]) {
      for (const el of document.querySelectorAll(selector)) {
        const name = employerName(el.getAttribute('content') || textOf(el));
        if (name) return name;
      }
    }
    return employerName(titleEmployer()?.company) || 'Unknown';
  }

  function extractDescriptionText() {
    // Strongly-preferred description containers first.
    const strong = [
      document.querySelector('article'),
      document.querySelector('main'),
      document.querySelector('[class*="description" i]'),
      document.querySelector('[class*="job-description" i]'),
      document.querySelector('[data-testid*="description" i]'),
    ];
    let best = '';
    for (const el of strong) {
      const t = textOf(el);
      if (t.length > best.length) best = t;
    }
    if (best.length >= 120) return best;

    // Fallback: the container with the most paragraph text (skips nav/footer
    // lists, which have few <p> elements).
    let largest = '';
    for (const el of document.querySelectorAll('article, main, section, div')) {
      if (el.querySelectorAll('p').length < 2) continue;
      const t = textOf(el);
      if (t.length > largest.length && t.length < 60000) largest = t;
    }
    return largest.length > best.length ? largest : best;
  }

  function extractGeneric() {
    // 1. Structured data (JSON-LD) is the most reliable source.
    const jsonld = extractFromJsonLd();
    if (jsonld && jsonld.role && jsonld.jd) return jsonld;

    const meta = (sel) => {
      const el = document.querySelector(sel);
      return el ? el.getAttribute('content') || '' : '';
    };
    const ogTitle = meta('meta[property="og:title"]');
    const ogDesc = meta('meta[property="og:description"]');
    const metaDesc = meta('meta[name="description"]');
    const fromTitle = titleEmployer();
    let role = textOf(document.querySelector('h1')) || fromTitle?.role;

    if (ogTitle) {
      if (!role) role = ogTitle.split(/[|\u2022\u2013\u2014-]/)[0].trim();
    }

    const jd = ogDesc || metaDesc || extractDescriptionText();

    if (role && jd) {
      return { role, company: jsonld?.company || '', jd };
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

      if (!titleEl || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: textOf(companyEl),
        jd: descEl.innerText.trim(),
      };
    },
    "justjoin.it": () => {
      // Try JSON-LD first (most stable)
      const jsonld = extractFromJsonLd();
      if (jsonld && jsonld.role && jsonld.jd) {
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

      if (!titleEl || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: textOf(companyEl),
        jd: techStack
          ? descEl.innerText.trim() + "\n\nTECH STACK: " + techStack
          : descEl.innerText.trim(),
      };
    },
    "nofluffjobs.com": () => {
      const jsonld = extractFromJsonLd();
      if (jsonld && jsonld.role && jsonld.jd) {
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

      if (!titleEl || !descEl) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!descEl) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: textOf(companyLink),
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

      if (!roleEl || descParts.length === 0) {
        const missing = [];
        if (!roleEl) missing.push("Role");
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
      if (jsonld && jsonld.role && jsonld.jd) {
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

      const descEl = document.querySelector(".job__description");
      const locationEl = document.querySelector(".job__location div");

      let jd = descEl ? descEl.innerText.trim() : "";
      if (locationEl && locationEl.innerText.trim()) {
        jd = "Location: " + locationEl.innerText.trim() + "\n\n" + jd;
      }

      if (!titleEl || !jd) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!jd) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: company,
        jd: jd,
      };
    },
    "workingnomads.com": () => {
      // Primary: extract from meta description (survives Angular SPA rewrites)
      // Format: "Apply for {Role} at {Company} and..."
      const metaDesc = document.querySelector('meta[name="description"]')?.content || "";
      const metaMatch = metaDesc.match(/Apply for (.+?) at (.+?)\s+and/);
      let role = metaMatch ? metaMatch[1].trim() : "";
      let company = metaMatch ? metaMatch[2].trim() : "";

      // Fallback: try JSON-LD if meta extraction failed (but page is Angular and may strip it)
      if (!role || !company) {
        const jsonld = extractFromJsonLd();
        if (jsonld && jsonld.role && jsonld.company) {
          role = jsonld.role;
          company = jsonld.company;
        }
      }

      const descEl = document.querySelector(".jd-description");
      const jd = descEl ? descEl.innerText.trim() : "";

      if (!role || !jd) {
        const missing = [];
        if (!role) missing.push("Role");
        if (!jd) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return { role, company, jd };
    },
  };

  const hostname = window.location.hostname;
  let extractor = null;

  // Check if the current domain matches any supported extractor strategy
  for (const domain in extractors) {
    if (hostname === domain || hostname.endsWith('.' + domain)) {
      extractor = extractors[domain];
      break;
    }
  }

  const result = extractor ? extractor() : extractGeneric();
  if (!result) {
    return { error: "Could not auto-extract this job. Use manual entry in the popup." };
  }
  if (result.error) return result;
  return { ...result, company: resolveEmployer(result.company) };
})();
