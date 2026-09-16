import os
import re

MIN_BODY_MATCHES = 2


def _load_list(filename, defaults):
    filepath = os.path.join(os.path.dirname(__file__), '..', filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"WARNING: {filename} not found! Using default filters.")
        return defaults


def load_greenflags():
    return _load_list('greenflags.txt', ["IT", "java", "c#", "software", "web"])


def load_greyflags():
    return _load_list('greyflags.txt', [])


def build_pattern(phrases):
    if not phrases:
        return None
    escaped = [re.escape(p) for p in phrases]
    return re.compile(r'(?i)(?<![a-z])(' + '|'.join(escaped) + r')(?![a-z])')


def _strip_greyflags(text, greyflag_pattern):
    if not text or not greyflag_pattern:
        return text
    return greyflag_pattern.sub(' ', text)


def is_relevant(pattern, title, raw_details, greyflag_pattern=None):
    """
    A job is relevant if a keyword appears in the title (reliable signal on its own),
    or if at least MIN_BODY_MATCHES distinct keyword hits appear in the body
    (a single incidental mention, e.g. "Microsoft Software" in a perks list, isn't enough).

    greyflag_pattern (from greyflags.txt) is stripped out of the text first, so a keyword
    that only ever appears inside a grey-flagged phrase (e.g. "fachliche Entwicklung")
    never counts as a match — it doesn't exclude the job, it just isn't treated as evidence.
    """
    title = _strip_greyflags(title, greyflag_pattern)
    raw_details = _strip_greyflags(raw_details, greyflag_pattern)

    if title and pattern.search(title):
        return True
    if not raw_details:
        return False
    return len(pattern.findall(raw_details)) >= MIN_BODY_MATCHES
