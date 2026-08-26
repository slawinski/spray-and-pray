"""Dedupe helper tests: URL normalization, fingerprints, description similarity."""

from cv_optimizer.discovery.dedupe import (
    descriptions_match,
    fingerprint,
    normalize_company,
    normalize_location,
    normalize_title,
    normalize_url,
)

JD_A = (
    "We are looking for a Senior Frontend Engineer to build complex user "
    "interfaces with React and TypeScript. Strong product collaboration and "
    "accessibility experience required. Hybrid in Warsaw."
)


def test_url_normalization_strips_tracking_params():
    url = (
        "https://Jobs.Example.com/jobs/123?utm_source=google&gh_src=xyz"
        "&utm_medium=cpc&fbclid=abc#fragment"
    )
    normalized = normalize_url(url)
    assert normalized == "https://jobs.example.com/jobs/123"


def test_url_normalization_preserves_job_identifiers():
    url = "https://boards.greenhouse.io/acme/jobs/424242"
    assert normalize_url(url) == "https://boards.greenhouse.io/acme/jobs/424242"


def test_url_normalization_trailing_slash_and_www():
    assert normalize_url("https://www.example.com/jobs/1/") == "https://example.com/jobs/1"


def test_url_normalization_sorts_query():
    a = "https://example.com/jobs/5?b=2&a=1"
    b = "https://example.com/jobs/5?a=1&b=2"
    assert normalize_url(a) == normalize_url(b)


def test_url_normalization_keeps_gh_jid():
    assert "gh_jid" in normalize_url("https://example.com/jobs?gh_jid=99")


def test_url_normalization_rejects_non_http():
    assert normalize_url("") is None
    assert normalize_url(None) is None
    assert normalize_url("ftp://example.com/x") is None


def test_company_normalization():
    assert normalize_company("N-iX") == "n ix"
    assert normalize_company("Example Corp.") == "example corp"
    assert normalize_company(" Dash0 ") == "dash0"


def test_title_normalization():
    assert normalize_title("Senior Front-End Engineer") == "senior frontend engineer"
    assert normalize_title("Full-Stack Engineer") == "fullstack engineer"
    assert normalize_title("  Product   Engineer ") == "product engineer"


def test_location_normalization():
    assert normalize_location("Warsaw, Poland") == "warsaw poland"
    assert normalize_location(None) == ""


def test_fingerprint_components():
    assert fingerprint("Dash0", "Senior Frontend Engineer", "Warsaw, Poland") == (
        "dash0",
        "senior frontend engineer",
        "warsaw poland",
    )


def test_descriptions_match_exact():
    assert descriptions_match(JD_A, JD_A)


def test_descriptions_match_containment():
    long_jd = "Some extra context about the company. " + JD_A + " Additional benefits info."
    assert descriptions_match(JD_A, long_jd)


def test_descriptions_match_similar_wording():
    jd_b = JD_A.replace("Strong product collaboration", "Strong cross-functional collaboration")
    assert descriptions_match(JD_A, jd_b)


def test_descriptions_differ_for_different_vacancies():
    jd_b = (
        "We are looking for a Frontend Engineer on the Payments team to "
        "build checkout flows with Vue and Nuxt. Fintech experience is a "
        "plus. Hybrid in Warsaw with a different stack and different team."
    )
    assert not descriptions_match(JD_A, jd_b)


def test_different_locations_never_merge_by_fingerprint():
    warsaw = fingerprint("Dash0", "Senior Frontend Engineer", "Warsaw, Poland")
    berlin = fingerprint("Dash0", "Senior Frontend Engineer", "Berlin, Germany")
    assert warsaw != berlin
