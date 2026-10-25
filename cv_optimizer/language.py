"""Automatic language selection for generated CVs and cover letters.

The application generates documents in English by default. The only
alternative path is Polish: when a job description is detected as
predominantly Polish, both the CV and the cover letter are generated in
Polish. Every other language (or an uncertain result) falls back to English.

Detection is intentionally narrow — the sole question we answer is:

    Is this job description predominantly Polish?

A full multilingual detection system is out of scope. The heuristic focuses
on natural-language prose (Polish diacritics and function words) while
discounting technical vocabulary, product/framework names, URLs, and code.
"""

import re
import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

ApplicationLanguage = Literal["en", "pl"]

# Conservative: when unsure, keep English. This is the confidence the Polish
# signal must reach before we switch the generation language.
POLISH_LANGUAGE_THRESHOLD = 0.7

# Polish diacritics are a near-unambiguous signal: English prose essentially
# never contains them, while genuine Polish prose is dense with them.
POLISH_DIACRITICS = set("ąćęłńóśźż")

# Weight given to a single word containing a Polish diacritic.
DIACRITIC_WEIGHT = 3
# Weight given to a Polish function/prose word without diacritics.
PL_STOP_WEIGHT = 2
# Weight given to an English function/prose word.
EN_STOP_WEIGHT = 1
# Minimum number of distinct Polish evidence words (diacritic + stop words)
# required before we will even consider Polish. Guards against a single stray
# Polish proper noun (company/city name) flipping a short English JD.
MIN_POLISH_SIGNALS = 2

# Polish function words / prose markers commonly found in job descriptions.
# Deliberately multi-letter to avoid collisions with English or code tokens.
# Diacritic-bearing words are caught separately, so these focus on the many
# common Polish words that happen to contain no diacritics (e.g. "pracy",
# "wymagania", "oferujemy", "naszego").
POLISH_STOPWORDS = {
    "nie", "oraz", "dla", "jest", "jesteśmy", "jesteś", "są", "będzie", "będą",
    "będziesz", "jako", "czy", "ale", "także", "również", "bardzo", "mile",
    "widziane", "widziany", "widziana", "dobra", "dobrze", "dobry", "lat", "roku",
    "pracy", "praca", "pracę", "zdalna", "zdalnie", "zdalnej", "hybrydowa",
    "hybrydowo", "wynagrodzenie", "benefity", "rekrutacja", "stanowisko",
    "stanowisku", "firma", "firmy", "branży", "branża", "oferujemy", "oferuje",
    "oferta", "szukamy", "poszukujemy", "poszukuje", "obowiązki", "wymagania",
    "wymagane", "wymagamy", "naszego", "naszej", "naszym", "nasz", "nasze",
    "zespół", "zespołu", "zespołem", "zespole", "doświadczenie", "doświadczenia",
    "doświadczeniem", "doświadczonego", "doświadczony", "znajomość", "znajomości",
    "znajomością", "aplikacji", "aplikacje", "aplikacjach", "aplikacją", "rozwój",
    "rozwoju", "technologie", "technologii", "technologiach", "narzędzia",
    "narzędzi", "umiejętności", "umiejętność", "język", "języku", "zakres",
    "zadań", "zadania", "obecnie", "pracujemy", "nasi", "naszych", "kandydata",
    "kandydat", "kandydatów", "osoby", "osoba", "poziom", "środowisku",
    "środowisko", "międzynarodowym", "zespołach", "projektach", "projektów",
    "realizacja", "codzienna", "codziennej", "wdrażanie", "utrzymanie",
    "tworzenie", "budowanie", "pisanie", "testowanie", "współpraca", "dołącz",
    "dołączysz", "poszukuje", "preferujemy", "kupujemy",
}

# English function/prose words. Focused on high-frequency prose vocabulary
# (rather than technical nouns) so that Polish JDs containing English section
# headers ("Responsibilities", "Requirements") and technical terms don't get
# misclassified as English.
ENGLISH_STOPWORDS = {
    "the", "and", "with", "for", "are", "you", "our", "we", "will", "your",
    "that", "this", "they", "them", "their", "from", "have", "has", "had",
    "was", "were", "been", "being", "would", "should", "could", "must", "about",
    "into", "over", "under", "such", "these", "those", "what", "when", "where",
    "which", "while", "who", "whom", "whose", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "only", "than", "very",
    "just", "also", "not", "but", "because", "since", "until", "though",
    "although", "whether", "rather", "either", "neither", "join", "looking",
    "hiring", "seeking", "team", "experience", "requirements", "responsibilities",
    "skills", "benefits", "work", "role", "required", "require", "include",
    "including", "plus", "bonus", "using", "build", "building", "develop",
    "developing", "maintain", "strong", "knowledge", "relevant", "remote",
    "office", "based", "located", "years", "degree", "environment", "hybrid",
    "collaboration", "growth", "culture", "well", "great", "opportunity",
    "flexible", "working", "hours", "communication", "salary", "competitive",
    "apply", "please", "candidate", "ideal", "profile", "forward",
}


@dataclass(frozen=True)
class LanguageDetectionResult:
    """The outcome of language detection for a job description."""

    # Resolved generation language: "en" or "pl".
    language: ApplicationLanguage
    # What the detector observed: "pl" when Polish signals dominate, otherwise
    # "other" (we deliberately do not identify specific non-Polish languages).
    detected_job_language: str
    # Confidence in the detected (Polish vs non-Polish) signal, in [0, 1].
    confidence: float


def resolve_application_language(
    detected_language: str | None,
    confidence: float | None,
) -> ApplicationLanguage:
    """Maps a detected language + confidence to an application language.

    English is always the fallback. Only a confident Polish detection switches
    the generation path to Polish.
    """
    if detected_language == "pl" and (confidence or 0.0) >= POLISH_LANGUAGE_THRESHOLD:
        return "pl"
    return "en"


def _strip_noise(text: str) -> str:
    """Removes URLs, emails, fenced code blocks, and inline code."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"www\.\S+", " ", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", " ", text)
    # Fenced code blocks
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # Inline code
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def _tokenize(text: str) -> list[str]:
    """Lowercases and splits into words, preserving Polish diacritics."""
    return re.findall(r"[a-ząćęłńóśźż]+", text.lower())


def _detect(text: str) -> tuple[str, float]:
    """Returns (detected_job_language, confidence) for the given text."""
    words = _tokenize(_strip_noise(text))

    diacritic = 0
    pl_stop = 0
    en_stop = 0

    for word in words:
        if any(ch in POLISH_DIACRITICS for ch in word):
            diacritic += 1
        elif word in POLISH_STOPWORDS:
            pl_stop += 1
        elif word in ENGLISH_STOPWORDS:
            en_stop += 1

    polish_vote = diacritic * DIACRITIC_WEIGHT + pl_stop * PL_STOP_WEIGHT
    english_vote = en_stop * EN_STOP_WEIGHT

    signal_count = diacritic + pl_stop
    if polish_vote <= 0 or signal_count < MIN_POLISH_SIGNALS:
        # No (or too little) Polish evidence → not Polish.
        return "other", 0.0

    confidence = polish_vote / (polish_vote + english_vote)
    detected = "pl" if confidence >= POLISH_LANGUAGE_THRESHOLD else "other"
    return detected, confidence


def detect_job_description_language(jd: str) -> LanguageDetectionResult:
    """Detects whether a job description is predominantly Polish.

    Returns a result whose `language` field is the resolved generation language
    ("en" by default, "pl" only for a confident Polish detection).
    """
    detected, confidence = _detect(jd or "")
    language = resolve_application_language(detected, confidence)
    logger.debug(
        "JD language detection: detected=%s confidence=%.2f -> %s",
        detected, confidence, language,
    )
    return LanguageDetectionResult(
        language=language,
        detected_job_language=detected,
        confidence=round(confidence, 4),
    )


def build_language_instruction(language: ApplicationLanguage) -> str:
    """Returns the generation instruction to append for the resolved language."""
    if language == "pl":
        return (
            "TARGET LANGUAGE: Polish\n\n"
            "Generate the document in natural, professional Polish.\n"
            "Preserve technology names, framework names, programming languages, "
            "product names and established English technical terminology where appropriate.\n"
            "Prefer ATS-relevant terminology used in the job description when it "
            "accurately represents the candidate's real experience.\n"
            "Do not translate technical keywords unnecessarily.\n"
            "Keep technical job titles in their established English form "
            "(e.g. \"Senior Frontend Developer\"), unless the candidate data already "
            "uses a Polish form.\n"
            "Do not invent skills or experience for keyword matching."
        )
    return (
        "TARGET LANGUAGE: English\n\n"
        "Generate the document in professional, natural English.\n"
        "Prefer terminology used in the job description when it accurately "
        "represents the candidate's actual experience.\n"
        "Do not invent experience or skills for keyword matching."
    )


def build_cv_heading_instruction(language: ApplicationLanguage, profile: str = "it") -> str:
    """Returns CV-specific heading guidance (Polish section headings for 'pl')."""
    if language == "pl":
        if profile == "baker":
            return (
                'For Baker use exactly these Polish headings in this order: '
                '"## O mnie", "## Domowy wypiek chleba", "## Warsztaty", '
                '"## Dotychczasowa praca zawodowa", "## Wykształcenie", "## Dane kontaktowe", '
                '"## Portfolio", "## Umiejętności", "## Języki", "## Klauzula RODO". '
                'Skip sections without selected data. Translate the approved aspiring-baker '
                'headline concisely as "Początkujący piekarz", not a long '
                '"Kandydat na stanowisko..." label; this is entry-level positioning, '
                'never a qualification.\n\n'
                'Write directly for a Polish bakery, not as a literal translation of an '
                'English corporate CV. Prefer short, concrete sentences and a consistent '
                'first-person voice for the introduction, practice and career paragraph. '
                'Open with hobby bread baking and the application goal, not the unnatural '
                'label "piekarz domowy". Keep O mnie to two short sentences about the '
                'hobby and job target. Put counts and start dates in the baking section '
                'and previous career details in the career section, without repeating '
                'them in the introduction. '
                'Use "Mam za sobą ponad N wypieków" for a selected bake count, not '
                '"sesje wypiekowe"; preserve the selected number and qualifier. '
                'Translate country loaves as "chleby wiejskie", not "wiejskie bochenki". '
                'Prefer "prowadzenie zakwasu", "formowanie bochenków" and '
                '"nawodnienie ciasta" to literal English calques. Describe a guided bake '
                'flow as "instrukcje krok po kroku", never "prowadzony przepływ wypieku". '
                'Translate descriptive portfolio labels into Polish while preserving app '
                'names and URLs; a home baking portfolio can be labeled "Moje wypieki". '
                'Include any supplied app description rather than dropping it; if none '
                'is selected, keep the link alone and do not infer features from its URL. '
                'Translate language proficiency labels idiomatically; '
                '"Full professional proficiency" can be "biegła znajomość", not '
                '"pełna znajomość zawodowa". '
                'Do not invent CEFR levels. Education must also read naturally in Polish. '
                'Use the supplied Polish university name rather than repeating its English '
                'translation; for a bilingual name use the Polish form only. Translate the '
                'selected degree level and subject descriptively: for example, an MSc in '
                'Mechanical Engineering is "Studia magisterskie: inżynieria mechaniczna". '
                'This describes the supplied qualification, not a newly asserted official '
                'programme or professional title. Do not invent a different programme, '
                'specialization or the formal title "magister inżynier" unless selected '
                'facts establish it. Do not leave a whole degree line in English merely '
                'because an official Polish diploma title is unavailable.\n\n'
                'Identify home baking as a hobby once clearly, then describe the facts '
                'without repeated disclaimers such as "nie była to działalność zarobkowa" '
                'or "a nie zawodowa". These are truthfulness constraints, not text to '
                'repeat in the CV. Do not turn private baking into professional experience. '
                'Summarize the previous career plainly without repeating the introduction '
                'or the application target, retaining every career field named in '
                'career_summary rather than dropping one for brevity. Style improvements '
                'must not remove selected app descriptions or career fields. '
                'Examples illustrate wording only; never add '
                'facts, activities or app features absent from the selected data.'
            )
        return (
            "Translate the CV section headings into Polish using exactly these headings: "
            "\"## Podsumowanie\", \"## Doświadczenie\", \"## Dane kontaktowe\", "
            "\"## Edukacja\", \"## Umiejętności\", \"## Społeczność\", \"## Języki\", "
            "\"## Zainteresowania\", \"## Klauzula RODO\". "
            "Keep the name heading (# ...) and the professional title (### ...) unchanged."
        )
    return ""
