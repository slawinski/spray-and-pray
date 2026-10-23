"""Version 1 exact label normalization. Raw labels remain in evidence."""

import unicodedata

VERSION = 1


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).split()).casefold() or 'unknown'


def source_key(value):
    key = normalize(value)
    return {'recruiter outreach': 'recruiter', 'employee referral': 'referral',
            'linked in': 'linkedin'}.get(key, key)


def role_key(value):
    key = normalize(value)
    aliases = {s: family for family, forms in {
        'frontend': ['frontend', 'front-end', 'frontend engineer', 'front end engineer'],
        'backend': ['backend', 'back-end', 'backend engineer', 'back end engineer'],
        'fullstack': ['fullstack', 'full-stack', 'full stack', 'full stack engineer'],
    }.items() for s in forms}
    return aliases.get(key, key)
