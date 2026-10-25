"""Run the injected content script through its public result contract, without npm."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


CONTENT_SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "content.js"
DESCRIPTION = "Build and maintain software with our engineering team."


def extract(*, url="https://jobs.example.test/offer", title="Engineer", company=None,
            jsonld=None, elements=None, site_name="Example Job Portal", role="Engineer"):
    node = shutil.which("node")
    assert node, "Node is required to check browser extension extraction"
    selectors = {"h1": role} if role else {}
    selectors.update(elements or {})
    if company is not None:
        selectors['[itemprop="hiringOrganization"] [itemprop="name"]'] = company
    case = dict(url=url, title=title, jsonld=jsonld or [], elements=selectors,
                meta={"og:site_name": site_name, "og:title": title,
                      "og:description": DESCRIPTION})
    script = r"""
    const fs = require('node:fs'), vm = require('node:vm');
    const data = JSON.parse(process.argv[2]);
    const node = text => ({innerText: text, textContent: text,
                          getAttribute: () => null});
    const elements = Object.fromEntries(Object.entries(data.elements).map(([k,v]) => [k, node(v)]));
    const document = {
      title: data.title,
      querySelectorAll(selector) {
        if (selector === 'script[type="application/ld+json"]') {
          return data.jsonld.map(value => ({textContent: JSON.stringify(value)}));
        }
        return selector.split(/,\s*/).flatMap(s => {
          const meta = s.match(/^meta\[(?:name|property)="(.+)"\]$/);
          if (meta && data.meta[meta[1]] !== undefined) {
            return [{getAttribute: () => data.meta[meta[1]], content: data.meta[meta[1]]}];
          }
          return elements[s] ? [elements[s]] : [];
        });
      },
      querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
      createElement() { return {set innerHTML(value) { this.textContent = value; }}; },
    };
    console.log(JSON.stringify(vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
      document, window: {location: new URL(data.url)}, URL,
    })));
    """
    result = subprocess.run([node, "-e", script, str(CONTENT_SCRIPT), json.dumps(case)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("oid,title,employer", [
    ("5012906", "Programista / Programistka, LUX MED Sp. z o.o., Warszawa", "LUX MED Sp. z o.o."),
    ("4949228", "Inżynier ds. Materiałoznawstwa (współpraca z Baker Hughes), Sieć Badawcza Łukasiewicz – Instytut Lotnictwa, Warszawa", "Sieć Badawcza Łukasiewicz – Instytut Lotnictwa"),
    ("4986261", "Inżynier ds. Analizy Zniszczeń (współpraca z GE Vernova), Sieć Badawcza Łukasiewicz – Instytut Lotnictwa, Warszawa", "Sieć Badawcza Łukasiewicz – Instytut Lotnictwa"),
])
def test_erecruiter_listing_returns_employer_instead_of_platform(oid, title, employer):
    result = extract(url=f"https://skk.erecruiter.pl/Offer.aspx?oid={oid}", title=title,
                     site_name="eRecruiter", role=None)
    assert result["company"] == employer
    assert result["role"] == title.split(", ")[0]


def job_posting(organization):
    return {"@type": "JobPosting", "title": "Engineer", "description": DESCRIPTION,
            "hiringOrganization": organization}


def test_pracuj_string_hiring_organization_preserves_full_employer_name():
    employer = "VIG Polska Sp. z o.o., Vienna Insurance Group"
    result = extract(url="https://www.pracuj.pl/praca/example,oferta,1005164217",
                     site_name="Pracuj.pl", jsonld=[job_posting(employer)])
    assert result["company"] == employer


@pytest.mark.parametrize("shape", ["object", "array", "graph", "type_array"])
def test_structured_employer_survives_common_jsonld_shapes(shape):
    posting = job_posting({"name": "Acme", "legalName": "Acme Ltd"})
    data = posting
    if shape == "array":
        data = [{"@type": "WebSite", "name": "Job Portal"}, posting]
    elif shape == "graph":
        data = {"@graph": [{"@type": "WebSite"}, posting]}
    elif shape == "type_array":
        posting["@type"] = ["Thing", "JobPosting"]
    assert extract(jsonld=[data])["company"] == "Acme"


@pytest.mark.parametrize("portal", ["Pracuj.pl", "Grupa Pracuj S.A.", "eRecruiter", "eRecruiter Sp. z o.o.", "LinkedIn", "Indeed", "Greenhouse", "Just Join IT", "https://jobs.example.com", "jobs.example.com", "Job Portal"])
def test_portal_in_structured_data_continues_to_visible_employer(portal):
    result = extract(jsonld=[job_posting({"name": portal})], company="Real Employer")
    assert result["company"] == "Real Employer"


@pytest.mark.parametrize("organization", [None, {}, {"name": "eRecruiter"}, "Pracuj.pl"])
def test_missing_or_portal_employer_returns_unknown(organization):
    result = extract(jsonld=[job_posting(organization)])
    assert result["company"] == "Unknown"
    assert result["role"] == "Engineer"
    assert result["jd"] == DESCRIPTION


def test_site_name_alone_is_not_employer_evidence():
    assert extract(site_name="An Unrecognized Hosting Platform")["company"] == "Unknown"


@pytest.mark.parametrize("url", ["https://jobs.example.test/offer", "https://justjoin.it/offer", "https://boards.greenhouse.io/company/jobs/123"])
def test_jsonld_role_and_description_survive_when_employer_is_missing(url):
    result = extract(url=url, title="", role=None, jsonld=[job_posting(None)])
    assert result == {"role": "Engineer", "company": "Unknown", "jd": DESCRIPTION}


def test_non_latin_employer_is_preserved():
    assert extract(jsonld=[job_posting({"name": "株式会社テスト"})])["company"] == "株式会社テスト"


def test_title_employer_wins_over_site_name_and_keeps_hyphens():
    result = extract(title="Engineer at Smith-Jones Ltd | Job Board", site_name="Job Board")
    assert result["company"] == "Smith-Jones Ltd"


def test_legal_name_used_when_structured_name_is_portal():
    result = extract(jsonld=[job_posting({"name": "eRecruiter", "legalName": "Acme Ltd"})])
    assert result["company"] == "Acme Ltd"


def test_pracuj_visible_employer_is_available_when_jsonld_is_missing():
    result = extract(url="https://www.pracuj.pl/praca/example",
                     elements={'[data-test="text-employer-name"]': "VIG Polska Sp. z o.o., Vienna Insurance Group"})
    assert result["company"] == "VIG Polska Sp. z o.o., Vienna Insurance Group"


def test_specialized_extractor_validates_portal_and_uses_unknown_for_missing_company():
    for company in [None, "LinkedIn", "Real Recruiting Agency"]:
        elements = {"#job-details": DESCRIPTION}
        if company:
            elements['.job-details-jobs-unified-top-card__company-name a'] = company
        result = extract(url="https://www.linkedin.com/jobs/view/123", elements=elements)
        assert result["company"] == (company if company == "Real Recruiting Agency" else "Unknown")
        assert result["jd"] == DESCRIPTION
