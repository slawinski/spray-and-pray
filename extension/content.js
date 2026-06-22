(function () {
  function extractFromJsonLd() {
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    for (const script of scripts) {
      try {
        const data = JSON.parse(script.textContent);
        const items = data["@graph"] || [data];
        for (const item of items) {
          if (item["@type"] === "JobPosting" || item.title) {
            const role = item.title;
            const company =
              item.hiringOrganization?.name ||
              item.hiringOrganization?.legalName;
            const jd = item.description || item.jd;
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
        jd: descEl.innerText.trim(),
      };
    },
    "theprotocol.it": () => {
      const titleEl = document.querySelector("h1");

      const companyEl = document.querySelector(
        '[data-test="text-offerEmployer"]',
      );

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

      if (!titleEl || !companyEl || descParts.length === 0) {
        const missing = [];
        if (!titleEl) missing.push("Role");
        if (!companyEl) missing.push("Company");
        if (descParts.length === 0) missing.push("Job Description");
        return { error: `Could not find fields: ${missing.join(", ")}` };
      }

      return {
        role: titleEl.innerText.trim(),
        company: companyEl.innerText.trim().replace(/^Company\s*:\s*/, ""),
        jd: descParts.join("\n\n"),
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
