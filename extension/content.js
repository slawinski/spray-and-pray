(function() {
    const extractors = {
        "linkedin.com": () => {
            // LinkedIn's DOM changes frequently and has multiple layouts (standalone vs split-view)
            const titleEl = document.querySelector('.job-details-jobs-unified-top-card__job-title h1') 
                         || document.querySelector('.job-details-jobs-unified-top-card__job-title') 
                         || document.querySelector('.jobs-unified-top-card__job-title') 
                         || document.querySelector('.job-view-layout-jobs-details h2')
                         || document.querySelector('.artdeco-entity-lockup__title')
                         || document.querySelector('h1');
                         
            const companyEl = document.querySelector('.job-details-jobs-unified-top-card__company-name a') 
                           || document.querySelector('.job-details-jobs-unified-top-card__company-name') 
                           || document.querySelector('.jobs-unified-top-card__company-name') 
                           || document.querySelector('.job-details-jobs-unified-top-card__primary-description a')
                           || document.querySelector('.jobs-unified-top-card__subtitle-primary-grouping a')
                           || document.querySelector('.job-details-jobs-unified-top-card__primary-description')
                           || document.querySelector('.artdeco-entity-lockup__subtitle');
                           
            const descEl = document.querySelector('#job-details') 
                        || document.querySelector('.jobs-description__content')
                        || document.querySelector('.jobs-description-content__text')
                        || document.querySelector('article');

            if (!titleEl || !companyEl || !descEl) {
                const missing = [];
                if (!titleEl) missing.push('Role');
                if (!companyEl) missing.push('Company');
                if (!descEl) missing.push('Job Description');
                return { error: `Could not find fields: ${missing.join(', ')}` };
            }

            return {
                role: titleEl.innerText.trim(),
                company: companyEl.innerText.trim(),
                jd: descEl.innerText.trim()
            };
        }
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
        return { error: "Unsupported Job Board" };
    }

    // Execute the strategy and return the object
    return extractor();
})();
