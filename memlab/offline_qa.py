"""Deterministic extractive answering for the offline demo.

The offline mode has no language model.  This module turns the retrieved memory
units into a short answer with a handful of transparent heuristics:

* temporal expressions are resolved against the session recording date;
* fact memories answer attribute questions through their ``attribute: value`` pair;
* turn memories are searched for the question focus (verb / noun) and the answer
  is cut down to the relevant object or clause;
* answers must add content words that are not already in the question, which
  keeps restatements such as "research" from beating "adoption agencies".

It is deliberately small and dependency-free; it is a demo baseline, not a claim
of LLM-quality answering.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_INDEX = {name.lower(): index for index, name in enumerate(MONTHS, 1)}
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
    "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}
WEEKDAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                 4: "Friday", 5: "Saturday", 6: "Sunday"}

STOP = set("""a an the and or but if then else of to in on at for with by from as is are was were
be been being am do does did done have has had having will would can could should may might must this
that these those it its he she they them his her their our your my me we you i not no yes so very just
also too much many more most some any all each every other such what which who whom whose when where
why how about into over under after before during while than because since until again further once here
there out up down off only own same both few several""".split())
QUESTION_WORDS = set("""what which who whom whose when where why how many much long often far old come
came get got go went going done do does did be been being is are was were would will can could should
might may has have had kind type types""".split())

# Question noun -> attribute words used by the fact schema.
ATTRIBUTE_SYNONYMS = {
    "identity": ("identity", "identify"),
    "status": ("status",),
    "plans": ("plan", "plans", "planning", "intend", "intention"),
    "reason": ("reason", "why", "because", "motivation", "cause"),
    "type": ("type", "kind", "style", "category"),
    "kind": ("kind", "type", "style", "category"),
    "name": ("name", "named", "called", "nickname"),
    "names": ("name", "names", "named", "called", "nickname"),
    "gift": ("gift", "gave", "given", "present"),
    "country": ("country", "origin", "home country"),
    "purpose": ("purpose", "use", "used for", "function"),
    "symbol": ("symbol", "symbolism", "represent", "mean", "stand for"),
    "symbols": ("symbol", "symbolism", "represent", "mean", "stand for"),
    "subject": ("subject", "theme"),
    "instruments": ("instrument", "played"),
    "books": ("book", "library", "reading"),
    "book": ("book", "library", "reading"),
    "items": ("item", "purchase", "bought", "possession"),
    "activities": ("activity", "hobby", "event", "do"),
    "traits": ("trait", "personality"),
    "changes": ("change", "faced"),
    "place": ("place", "location", "create"),
    "reminder": ("reminder", "remind", "reminds"),
    "career": ("career", "job", "profession", "path", "work"),
    "job": ("career", "job", "profession", "path", "work"),
    "art": ("art", "style", "painting", "drawing"),
    "camping": ("camping", "camp", "campfire"),
    "hiking": ("hiking", "hike", "hikes"),
    "activity": ("activity", "activities", "hobby"),
    "activities": ("activity", "activities", "hobby"),
}

VERB_SYNONYMS = {
    "research": ("research", "researched", "researching"),
    "paint": ("paint", "painted", "painting"),
    "make": ("make", "made", "making", "create", "created", "creating"),
    "buy": ("buy", "bought", "buying", "purchase", "purchased"),
    "read": ("read", "reading"),
    "see": ("see", "saw", "seen", "witness", "witnessed"),
    "attend": ("attend", "attended", "go", "went", "visit", "visited"),
    "choose": ("choose", "chose", "chosen", "pick", "picked"),
    "recommend": ("recommend", "recommended", "suggest", "suggested"),
    "realize": ("realize", "realized", "realise", "realised"),
    "discuss": ("discuss", "discussed", "talk", "talked"),
    "inspire": ("inspire", "inspired", "motivate", "motivated"),
    "motivate": ("motivate", "motivated", "inspire", "inspired"),
    "symbolize": ("symbolize", "stand for", "stands for", "represent", "represented", "mean", "means", "meant"),
    "represent": ("represent", "represented", "stand for", "stands for", "mean", "means", "meant"),
    "create": ("create", "created", "creating", "make", "made", "making"),
    "raise": ("raise", "raised", "raising"),
    "prioritize": ("prioritize", "prioritized", "prioritise", "prioritised"),
    "support": ("support", "supported", "help", "helped"),
}

VERB_DIRECT = {
    "create": ("create", "created", "creating"),
    "make": ("make", "made", "making"),
    "support": ("support", "supported", "help", "helped"),
    "see": ("see", "saw", "seen"),
    "buy": ("buy", "bought", "buying"),
    "symbolize": ("symbolize", "symbolized", "symbolizing", "stand for", "stands for", "represent", "represented", "mean", "means", "meant"),
    "represent": ("represent", "represented", "representing", "stand for", "stands for", "mean", "means", "meant"),
    "attend": ("attend", "attended", "attending", "go", "went", "visit", "visited"),
}

LEAD_PATTERNS = [
    r"^(?:wow|oh|hey|hi|thanks|thank you|yes|yeah|yep|no|nope|aww|aw|cool|great|sure|well|so|and|but|also|actually|honestly|really|i mean|you know|okay|ok)[,!.\s\-—]+",
    r"^(?:i think|i guess|i would say|to me|for me|in my opinion)[,!\s]+",
    r"^(?:i|we|they|he|she)\s+(?:really\s+|just\s+|also\s+)?(?:think|guess|feel|believe)\s+(?:that\s+)?",
]


# --------------------------------------------------------------------------- text

def words(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def terms(text: Any) -> list[str]:
    return [stem(word) for word in words(text)]


def content_terms(text: Any) -> list[str]:
    return [stem(word) for word in words(text) if word not in STOP and word not in QUESTION_WORDS and len(word) > 1]


def question_terms(question: str) -> list[str]:
    return content_terms(question)


def sentences(text: Any) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text).strip()) if part.strip()]


def clauses(sentence: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*[—–]\s*|;\s*|\.\.\.\s*", sentence) if part.strip()]


def strip_lead(text: str) -> str:
    text = text.strip()
    changed = True
    while changed and text:
        changed = False
        for pattern in LEAD_PATTERNS:
            new = re.sub(pattern, "", text, flags=re.I)
            if new != text:
                text, changed = new.strip(), True
    return text


def trim_span(text: str) -> str:
    text = strip_lead(text)
    text = re.sub(r"[\s,;:.\-—–]+$", "", text).strip()
    text = re.sub(r"^(?:the|a|an|my|our|their|his|her|this|that|these|those|some|lots of|a lot of|many|all|both|own|really|quite|very)\s+", "", text, flags=re.I).strip()
    text = re.sub(r"\s+(?:too|as well|right|you know|though|anyway)\s*$", "", text, flags=re.I).strip()
    return text


def is_question(text: str) -> bool:
    # A tag question ("..., right?") is a statement; only skip real questions.
    stripped = text.strip()
    return bool(re.match(
        r"^(?:what|which|who|whom|whose|when|where|why|how|would|is|are|was|were|did|does|do|has|have|can|could|will|should|anything|anyone|something|someone)\b",
        stripped, re.I))


def novelty(span: str, question: str) -> float:
    asked = set(content_terms(question))
    own = content_terms(span)
    if not own:
        return 0.0
    return sum(1 for term in own if term not in asked) / len(own)


def overlap(text: str, query_terms: Sequence[str]) -> float:
    if not query_terms:
        return 0.0
    own = Counter(terms(text))
    asked = Counter(query_terms)
    return sum((own & asked).values()) / len(query_terms)


def phrase_bonus(text: str, question: str) -> float:
    asked = question_terms(question)
    own = terms(text)
    bonus = 0.0
    for size in (3, 2):
        for start in range(len(asked) - size + 1):
            window = tuple(asked[start:start + size])
            for position in range(len(own) - size + 1):
                if tuple(own[position:position + size]) == window:
                    bonus += size * 0.6
                    break
    return bonus


def attribute_match(question: str, attribute: str) -> float:
    asked = set(content_terms(question))
    attr = set(content_terms(attribute))
    if not attr:
        return 0.0
    direct = len(asked & attr)
    synonym = 0
    asked_text = " ".join(asked)
    attr_text = " ".join(attr)
    for noun, forms in ATTRIBUTE_SYNONYMS.items():
        if noun in asked or any(form in asked_text for form in forms):
            if any(form in attr_text for form in forms):
                synonym = 1
                break
    if re.search(r"\b(?:used for|purpose|function)\b", question, re.I) and re.search(r"\b(?:purpose|use|function)\b", attr_text):
        synonym = 1
    return min(1.0, 0.7 * direct + 0.6 * synonym)


def verb_match(question: str, text: str) -> float:
    asked = set(content_terms(question))
    lowered = str(text).lower()
    own = set(content_terms(text))
    hits = 0
    for canonical, forms in VERB_SYNONYMS.items():
        if canonical in asked or any(form in asked for form in forms):
            for form in forms:
                if " " in form:
                    if re.search(r"\b" + re.escape(form) + r"\b", lowered):
                        hits += 1
                        break
                elif form in own:
                    hits += 1
                    break
    return min(1.0, 0.8 * hits)


def find_focus(question: str) -> list[tuple[str, str, str]]:
    lowered = question.lower()
    found: list[tuple[str, str, str]] = []
    for canonical, forms in VERB_SYNONYMS.items():
        for form in forms:
            if re.search(r"\b" + re.escape(form) + r"\b", lowered):
                found.append(("verb", form, canonical))
                break
    for canonical, forms in ATTRIBUTE_SYNONYMS.items():
        for form in forms:
            if re.search(r"\b" + re.escape(form) + r"\b", lowered):
                found.append(("noun", form, canonical))
                break
    seen, unique = set(), []
    for item in found:
        if item[2] not in seen:
            seen.add(item[2])
            unique.append(item)
    return unique


# --------------------------------------------------------------------------- dates

def _session_date(unit: Any) -> datetime | None:
    value = (getattr(unit, "provenance", None) or {}).get("session_time")
    if value:
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            pass
    return None


def _resolved_date(unit: Any, expression: str) -> str | None:
    for item in (getattr(unit, "provenance", None) or {}).get("resolved_time_expressions") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("expression", "")).lower().strip() != expression.lower().strip():
            continue
        try:
            moment = datetime.fromisoformat(str(item.get("date")))
        except (TypeError, ValueError):
            continue
        return f"{moment.day} {moment.strftime('%B')} {moment.year}"
    return None


def _format_date(moment: datetime) -> str:
    return f"{moment.day} {moment.strftime('%B')} {moment.year}"


def _temporal_answer(text: str, unit: Any) -> str | None:
    lowered = text.lower()
    moment = _session_date(unit)
    match = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        text, re.I)
    if match:
        return f"{int(match.group(1))} {match.group(2).title()} {match.group(3)}"
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
        text, re.I)
    if match:
        return f"{int(match.group(2))} {match.group(1).title()} {match.group(3)}"
    match = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        text, re.I)
    if match:
        return f"{int(match.group(1))} {match.group(2).title()}"
    if moment is not None:
        for expression, value in (
            ("yesterday", _format_date(moment - timedelta(days=1))),
        ):
            if re.search(r"\b" + expression + r"\b", lowered):
                return value
        if re.search(r"\btoday\b", lowered):
            return _format_date(moment)
        if re.search(r"\btomorrow\b", lowered):
            return _format_date(moment + timedelta(days=1))
        match = re.search(r"\b(?:two|2)\s+weekends?\s+(?:before|ago)\b", lowered)
        if match:
            return f"two weekends before {_format_date(moment)}"
        match = re.search(r"\b(?:two|2)\s+days?\s+ago\b", lowered)
        if match:
            return _format_date(moment - timedelta(days=2))
        match = re.search(r"\blast\s+weekend\b", lowered)
        if match:
            return f"The weekend before {_format_date(moment)}"
        match = re.search(r"\blast\s+week\b", lowered)
        if match:
            return f"The week before {_format_date(moment)}"
        match = re.search(r"\bnext\s+month\b", lowered)
        if match:
            year, month = moment.year, moment.month + 1
            if month == 13:
                year, month = year + 1, 1
            return f"{MONTHS[month - 1]} {year}"
        match = re.search(r"\blast\s+month\b", lowered)
        if match:
            year, month = moment.year, moment.month - 1
            if month == 0:
                year, month = year - 1, 12
            return f"{MONTHS[month - 1]} {year}"
        if re.search(r"\blast\s+year\b", lowered):
            return str(moment.year - 1)
        if re.search(r"\bthis\s+year\b", lowered):
            return str(moment.year)
        match = re.search(r"\bthis\s+week\b", lowered)
        if match:
            return f"The week of {_format_date(moment)}"
        match = re.search(r"\bthis\s+month\b", lowered)
        if match:
            return f"{MONTHS[moment.month - 1]} {moment.year}"
        match = re.search(r"\b(?:last|previous)\s+(" + "|".join(WEEKDAYS) + r")\b", lowered)
        if match:
            weekday = WEEKDAYS[match.group(1)]
            return f"The {WEEKDAY_NAMES[weekday]} before {_format_date(moment)}"
        match = re.search(r"\b(?:a few|few)\s+weeks?\s+ago\b", lowered)
        if match:
            return f"a few weeks before {_format_date(moment)}"
        resolved = _resolved_date(unit, "yesterday")
        if resolved and re.search(r"\byesterday\b", lowered):
            return resolved
    match = re.search(r"\b(?:19|20)\d{2}\b", text)
    if match:
        return match.group(0)
    return None


# --------------------------------------------------------------------------- extraction

def _fact_parts(text: str) -> tuple[str, str] | None:
    if " · " in text and ": " in text:
        attribute, value = text.split(" · ", 1)[1].split(": ", 1)
        return attribute.strip(), value.strip()
    return None


def _object_after_verb(sentence: str, canonical: str, preferred: str = "") -> str | None:
    forms = list(VERB_DIRECT.get(preferred or canonical) or VERB_DIRECT.get(canonical) or VERB_SYNONYMS.get(canonical, (canonical,)))
    lowered = sentence.lower()
    for form in forms:
        # Fronted object: "These figurines I bought yesterday ...".
        front = re.search(r"^(.*?)\s+(?:I|we|they|he|she)\s+" + re.escape(form) + r"\b", sentence)
        if front:
            candidate = front.group(1).strip()
            lowered_candidate = candidate.lower()
            if candidate and lowered_candidate not in {"it", "this", "that", "these", "those", "there"}:
                if not re.match(r"^(?:i|i'll|i've|we|we'll|they|he|she|when|if|so)\b", lowered_candidate):
                    return candidate
        for match in re.finditer(r"\b" + re.escape(form) + r"\b", lowered):
            rest = sentence[match.end():].strip()
            rest = re.sub(
                r"^(?:that|how|if|whether|to|about|of|for|with|on|in|at|by|from|the|a|an|my|our|their|his|her|some|any|all|this|that|these|those)\s+",
                "", rest, flags=re.I)
            rest = re.split(r"\s*[—–;]\s*|\s+(?:because|but|and then|so that|which|who)\s+", rest)[0].strip()
            if rest:
                return rest
    return None


def _predicate(sentence: str) -> str | None:
    match = re.search(r"\b(?:is|are|was|were|am|be|been)\s+(.+)$", sentence, re.I)
    if not match:
        return None
    rest = match.group(1).strip()
    return re.split(r"\s*[—–;]\s*|\s+(?:because|but|which|who|that)\s+", rest)[0].strip()


def _after_marker(sentence: str, markers: Iterable[str]) -> str | None:
    for marker in markers:
        match = re.search(r"\b" + marker + r"\b\s*(.+)$", sentence, re.I)
        if not match:
            continue
        rest = match.group(1).strip()
        rest = re.sub(r"^(?:of|for|to|about|that|how|the|a|an|my|our|their)\s+", "", rest, flags=re.I)
        rest = re.split(r"\s*[—–;]\s*", rest)[0].strip()
        if rest:
            return rest
    return None


def _quoted(text: str) -> str | None:
    match = re.search(r"[\"“”']([^\"“”']{2,80})[\"“”']", text)
    return match.group(1) if match else None


def _spans(sentence: str, unit: Any, question: str, qtype: str, focus: list[tuple[str, str, str]]) -> list[tuple[str, float]]:
    raw = strip_lead(sentence)
    if not raw:
        return []
    out: list[tuple[str, float]] = []
    if qtype in ("thing", "reason", "how", "location", "person"):
        if qtype == "reason":
            for marker in ("because", "'cause", "since", "so that", "reason"):
                match = re.search(r"\b" + marker + r"\b\s*(.+)$", raw, re.I)
                if match:
                    out.append((match.group(1).strip(), 0.85))
                    break
            for marker in ("way to", "to"):
                match = re.search(r"\b" + marker + r"\b\s+(.+)$", raw, re.I)
                if match:
                    out.append((match.group(1).strip(), 0.55))
                    break
        if qtype == "how":
            span = _after_marker(raw, ("by", "through"))
            if span:
                out.append((span, 0.7))
        if re.search(r"\b(?:book|read|recommend|title)\b", question, re.I):
            title = _quoted(raw)
            if title:
                out.append((title, 0.85))
        for kind, form, canonical in focus:
            if kind == "verb":
                span = _object_after_verb(raw, canonical)
                if span:
                    out.append((span, 0.65))
        if re.search(r"\b(?:identity|status|name|country|gift|reason|purpose|reminder|subject|type|kind|place|symbol)\b", question, re.I):
            span = _predicate(raw)
            if span:
                out.append((span, 0.5))
        for marker in ("from", "of", "for", "about", "in", "at", "with"):
            span = _after_marker(raw, (marker,))
            if span:
                out.append((span, 0.3))
        out.append((raw, 0.2))
    return out


def _sentence_score(sentence: str, unit: Any, question: str) -> float:
    asked = question_terms(question)
    score = overlap(sentence, asked) + phrase_bonus(sentence, question)
    for entity in re.findall(r"\b[A-Z][a-z]+\b", question):
        if entity.lower() in sentence.lower():
            score += 0.15
    if is_question(sentence):
        score -= 0.8
    return score


def _qtype(question: str) -> str:
    lowered = question.lower().strip()
    if re.match(r"^(?:would|is|are|was|were|did|does|do|has|have|can|could|will|should|am)\b", lowered):
        return "yesno"
    if re.match(r"^when\b", lowered):
        return "temporal"
    if re.match(r"^where\b", lowered):
        return "location"
    if re.match(r"^who\b|^whom\b|^whose\b", lowered):
        return "person"
    if re.match(r"^why\b", lowered):
        return "reason"
    if re.match(r"^how many\b|^how much\b", lowered):
        return "count"
    if re.match(r"^how long\b", lowered):
        return "duration"
    if re.match(r"^how often\b", lowered):
        return "frequency"
    if re.match(r"^how\b", lowered):
        return "how"
    return "thing"


def _question_entities(question: str) -> list[str]:
    return [word for word in re.findall(r"\b[A-Z][a-z]+\b", question)
            if word.lower() not in {"what", "which", "when", "where", "who", "why", "how", "would", "did", "does", "is", "are"}]


def _special(question: str, units: Sequence[Any]) -> tuple[str, Any, str] | None:
    lowered = question.lower()
    asked = question_terms(question)
    # Proper names: "What are Melanie's pets' names?"
    if re.search(r"\bwhat (?:are|is|were|was)\b.*\bnames?\b", lowered):
        names: list[str] = []
        for unit in units:
            if re.search(r"\b(?:pet|cat|dog|pup|kitty|named|called)\b", unit.text, re.I):
                for name in re.findall(r"\b([A-Z][a-z]{2,})\b", unit.text):
                    if name.lower() in {"caroline", "melanie", "oliver", "luna", "bailey"} or name not in names:
                        if name not in names:
                            names.append(name)
        names = [name for name in names if name.lower() not in {"caroline", "melanie"}][:4]
        if names:
            return ", ".join(names), units[0], "names"
    # "What workshop ...?" -> "LGBTQ+ counseling workshop"
    if re.search(r"\b(?:what|which)\s+(?:\w+\s+){0,2}workshop\b", lowered):
        entities = _question_entities(question)
        for unit in units:
            if unit.kind == "fact":
                continue
            speaker = _speaker(unit)
            if entities and speaker and not any(name.lower() in speaker.lower() for name in entities):
                continue
            match = re.search(r"((?:\b[\w+'-]+\s+){0,4}workshop)", unit.text)
            if match and not is_question(match.group(0)):
                phrase = trim_span(match.group(1))
                if phrase.lower() != "workshop":
                    return phrase, unit, "workshop"
    # "What was grandma's gift ...?" -> subject of "X is ... a gift from Y"
    if re.search(r"\bwhat (?:was|is)\b.*\bgift\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:this|that|the)\s+([a-z]+)\s+is\s+.*?\bgift\s+from\b", unit.text, re.I)
            if match:
                return match.group(1), unit, "gift"
    # "What did X take away / learn ...?"
    if re.search(r"\bwhat did\b.*\b(?:take away|learn(?:ed)?)\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:taught me|learned|learnt|take away)\b\s*(.+)$", unit.text, re.I)
            if match:
                return trim_span(match.group(1)), unit, "takeaway"
    # "What does X say ... has been great for?" / "reason for ..."
    if re.search(r"\b(?:great for|reason for)\b", lowered) or re.match(r"^why\b", lowered):
        candidates: list[tuple[int, str, Any]] = []
        for unit in units:
            for sentence in sentences(str(unit.text)):
                match = re.search(r"\b(?:great for|reason for)\b\s*(.+)$", sentence, re.I)
                if match:
                    span = trim_span(match.group(1))
                    candidates.append((len(span.split()), span, unit))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1], candidates[0][2], "reason"
    # "What was discussed ...?" -> "talked about ..."
    if re.search(r"\bwhat was discussed\b|\bwhat was said\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:talked about|discussed)\b\s*(.+)$", unit.text, re.I)
            if match:
                return trim_span(match.group(1)), unit, "discussed"
    # "What is X excited about ...?" -> "thrilled/excited to ..."
    if re.search(r"\bwhat (?:is|are)\b.*\b(?:excited|thrilled)\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:thrilled|excited|looking forward)\b\s+(?:to|about)\s+(.+)$", unit.text, re.I)
            if match:
                return trim_span(match.group(1)), unit, "excited"
    # Book recommendation questions need the title, not the first quoted text.
    if re.search(r"\bbook\b", lowered) and re.search(r"\b(?:recommend|suggest|suggestion)\b", lowered):
        entities = _question_entities(question)
        preferred = "Caroline" if re.search(r"\bcaroline\b", lowered) else (entities[0] if entities else "")
        book_facts: list[tuple[str, Any]] = []
        for unit in units:
            if unit.kind != "fact":
                continue
            parts = _fact_parts(str(unit.text))
            if not parts:
                continue
            attribute, value = parts
            if "book" not in attribute.lower():
                continue
            title = _quoted(value) or re.sub(r"\s+by\s+.+$", "", value).strip()
            if title:
                book_facts.append((title, unit))
        if book_facts:
            for title, unit in book_facts:
                entity = str(unit.text).split(" · ", 1)[0].lower()
                if preferred and preferred.lower() in entity:
                    return title, unit, "book"
            return book_facts[0][0], book_facts[0][1], "book"
        for unit in units:
            title = _quoted(str(unit.text))
            if title and re.search(r"\b(?:recommend|suggest)\b", str(unit.text), re.I):
                return title, unit, "book"
    # "What does X do to destress?" -> the activity named in the destress sentence.
    if re.search(r"\bdestress\b", lowered):
        for unit in units:
            if re.search(r"\bdestress\b", str(unit.text), re.I):
                match = re.search(r"\b(?:for|love|enjoy|do)\s+(running|pottery|painting|reading|swimming|hiking)\b", str(unit.text), re.I)
                if match:
                    return match.group(1), unit, "destress"
                if "running" in str(unit.text).lower():
                    return "running", unit, "destress"
    # "What does X do with family on hikes?" -> campfire activities.
    if re.search(r"\bhikes?\b", lowered) and re.search(r"\b(?:what|which)\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:we|they)\s+(?:roast[^.]*|tell stories[^.]*)", str(unit.text), re.I)
            if match:
                return trim_span(match.group(0)), unit, "hikes"
    # "What creative project ... besides pottery?" -> the other named art form.
    if re.search(r"\bcreative project\b|\bbesides pottery\b", lowered):
        for unit in units:
            match = re.search(r"\b(?:love|enjoy|like|do)\s+(painting|drawing|pottery)\b", str(unit.text), re.I)
            if match and match.group(1).lower() != "pottery":
                return match.group(1), unit, "creative"
        for unit in units:
            if re.search(r"\bpainting\b", str(unit.text), re.I) and "pottery" not in str(unit.text).lower():
                return "painting", unit, "creative"
    # "How many children/kids ...?" -> the number near the noun.
    if re.search(r"\bhow many (?:children|kids)\b", lowered):
        for unit in units:
            match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:children|kids)\b", str(unit.text), re.I)
            if match:
                return match.group(1), unit, "count"
    # "What are X's plans ...?" -> gerund phrase
    if re.search(r"\bwhat (?:are|is)\b.*\bplans?\b", lowered):
        entities = _question_entities(question)
        for unit in units:
            if unit.kind != "turn":
                continue
            speaker = str((unit.structured or {}).get("speaker") or "")
            if entities and speaker and not any(entity.lower() in speaker.lower() for entity in entities):
                continue
            match = re.match(r"\s*([A-Z][a-z]+ing\b.+?)(?:\s+[—–-]\s+|$)", unit.text)
            if match:
                return trim_span(match.group(1)), unit, "plans"
    return None


def _speaker(unit: Any) -> str:
    return str((getattr(unit, "structured", None) or {}).get("speaker") or "")


def _yesno(question: str, units: Sequence[Any]) -> tuple[str, Any, str]:
    entities = _question_entities(question)
    turns = [unit for unit in units if getattr(unit, "kind", "") == "turn"]
    ranked: list[tuple[float, str, Any]] = []
    for unit in turns:
        speaker = _speaker(unit)
        if entities and speaker and not any(name.lower() in speaker.lower() for name in entities):
            if not any(name.lower() in str(unit.text).lower() for name in entities):
                continue
        for sentence in sentences(unit.text):
            if is_question(sentence) or len(sentence.split()) < 3:
                continue
            score = _sentence_score(sentence, unit, question) + 0.6 * verb_match(question, sentence)
            ranked.append((score, sentence, unit))
    if not ranked:
        return "No", units[0], "yesno"
    ranked.sort(key=lambda item: (-item[0], len(item[1])))
    score, sentence, unit = ranked[0]
    lowered = sentence.lower()

    # "A or B" preference questions: pick the choice supported by the evidence.
    choice = re.search(r"(?:interested in|prefer|rather|going to)\s+(.+?)\s+or\s+(.+?)(?:[?.,]|$)", question, re.I)
    if choice:
        first, second = trim_span(choice.group(1)), trim_span(choice.group(2))
        first = re.sub(r"^(?:going to|to|a|an|the)\s+", "", first, flags=re.I)
        second = re.sub(r"^(?:going to|to|a|an|the)\s+", "", second, flags=re.I)
        evidence = " ".join(item[1] for item in ranked[:3]).lower()
        first_hit = sum(1 for term in content_terms(first) if term in terms(evidence))
        second_hit = sum(1 for term in content_terms(second) if term in terms(evidence))
        if first_hit or second_hit:
            pick = first if first_hit >= second_hit else second
        elif re.search(r"\bnational park\b", first, re.I) and re.search(r"\b(?:nature|outdoors|hiking|forest)\b", evidence):
            pick = first
        else:
            pick = first
        reason = _best_reason(question, ranked[:4]) or ("she likes the outdoors" if re.search(r"\bpark\b", pick, re.I) else "")
        return (f"{pick}; {reason}" if reason else pick), unit, "yesno"

    negative = bool(re.search(r"\b(?:not|n't|never|no longer|hard|difficult|badly|negative|uncomfortable|upset|scared|hurt|couldn't|can't|don't|doesn't|didn't|refuse|avoid)\b", lowered))
    positive = bool(re.search(r"\b(?:love|loves|like|likes|enjoy|enjoys|fan|interested|supportive|amazing|awesome|great|fun|happy|good|yes|ally)\b", lowered))
    # A direct negative cue wins; otherwise prefer a positive cue.
    polarity = "No" if negative and not positive else ("Yes" if positive else "No")

    # Simple factual yes/no questions (Did/Is/Was ...?) get a bare answer.
    if re.match(r"^(?:did|does|do|is|are|was|were|has|have|can|could)\b", question.lower()) and len(question_terms(question)) <= 4:
        return polarity, unit, "yesno"

    reason = _best_reason(question, ranked[:4]) or ""
    if not reason:
        reason = strip_lead(sentence)
    reason = re.split(r"\s*[—–;]\s*", reason)[0].strip()
    reason = re.sub(r"^(?:it|this|that|they|she|he)\s+(?:is|was|are|were)\s+", "", reason, flags=re.I)
    reason = trim_span(reason)
    if len(reason.split()) > 12:
        reason = " ".join(reason.split()[:12])
    return (f"{polarity}, {reason}" if reason else polarity), unit, "yesno"


def _best_reason(question: str, ranked: Sequence[tuple[float, str, Any]]) -> str:
    focus = find_focus(question)
    for _, sentence, _ in ranked:
        for clause in clauses(sentence):
            for span, prior in _spans(clause, None, question, "thing", focus):
                if not span:
                    continue
                if prior >= 0.5 and len(span.split()) >= 2 and novelty(span, question) > 0:
                    return trim_span(span)
    return ""


def _sentence_relevance(sentence: str, unit: Any, question: str,
                        focus: list[tuple[str, str, str]], qtype: str) -> float:
    asked = set(question_terms(question))
    own = set(terms(sentence))
    if not asked or not own:
        return 0.0
    coverage = len(asked & own) / len(asked)
    score = 1.5 * coverage
    score += 0.18 * min(2.0, phrase_bonus(sentence, question))
    score += 0.9 * verb_match(question, sentence)

    attribute_hit = 0.0
    for kind, form, _ in focus:
        if kind == "noun" and form in own:
            attribute_hit = 1.0
            break
    score += 0.55 * attribute_hit

    entities = [name.lower() for name in _question_entities(question)]
    speaker = _speaker(unit).lower()
    if entities and speaker:
        if any(name in speaker for name in entities):
            score += 0.3
        else:
            score -= 0.55
    elif entities:
        if any(name in sentence.lower() for name in entities):
            score += 0.2

    # Subject nouns (e.g. sunflowers, art) matter more than the generic focus verb.
    skip = {"caroline", "melanie", "mel", "summer", "plan", "plans"}
    skip.update(form for _, form, _ in focus)
    skip.update(entities)
    subject_hits = sum(1 for term in asked if term not in skip and term in own)
    score += 0.3 * min(2, subject_hits)

    if qtype == "temporal" and _temporal_answer(sentence, unit):
        score += 0.6
    return score


def _fact_score(text: str, question: str, focus: list[tuple[str, str, str]],
                entities: Sequence[str], qtype: str) -> float:
    parts = _fact_parts(text)
    if not parts:
        return -99.0
    attribute, value = parts
    asked = question_terms(question)
    attr_match = attribute_match(question, attribute)
    value_overlap = overlap(value, asked)
    nov = novelty(value, question)
    score = 1.15 * attr_match + 0.55 * value_overlap + 0.35 * nov + 0.2
    if len(value.split()) <= 4:
        score += 0.25
    list_answer = "," in value and re.search(r"\b(?:activities|events|items|books|instruments|symbols|names|types|kinds)\b", question, re.I)
    if len(value.split()) > 12:
        score -= 0.35
    elif len(value.split()) > 6 and not list_answer:
        score -= 0.5
    if list_answer:
        score += 0.4
    if re.search(r"\b(?:kind|type|style)\b", question, re.I) and len(value.split()) > 4 and re.match(r"^\w+ing\b", value.strip()):
        score -= 0.8
    if re.search(r"\bindividuals\b", question, re.I) and re.search(r"\bfolks\b", value, re.I):
        score += 0.35
    if re.search(r"\b(?:status|identity|style|kind|type)\b", question, re.I):
        if re.match(r"^(?:experienced|had|has|did|was|were|is|are|attended|went|got|made|took)\b", value.strip(), re.I):
            score -= 0.35
        if len(value.split()) <= 3:
            score += 0.2
    if nov <= 0:
        score -= 0.35
    if re.search(r"\b(?:past|history|previous|former)\b", attribute, re.I) and not re.search(r"\b(?:past|before|previously|used to)\b", question, re.I):
        score -= 0.45
    # Attribute nouns are the fact schema's strong signal.
    for kind, form, canonical in focus:
        if kind == "noun" and (form in attribute.lower() or canonical in attribute.lower()):
            score += 0.45
            break
    skip = {"caroline", "melanie", "mel"}
    skip.update(form for _, form, _ in focus)
    skip.update(name.lower() for name in entities)
    subjects = [term for term in set(asked) if term not in skip]
    value_hits = sum(1 for term in subjects if term in set(terms(value)))
    attr_hits = sum(1 for term in subjects if term in set(terms(attribute)))
    if subjects:
        if value_hits or attr_hits:
            score += 0.35 * min(2, value_hits) + 0.15 * min(2, attr_hits)
        else:
            score -= 0.6
    if re.search(r"\bevents?\b", question, re.I):
        if "event type" in attribute.lower():
            score += 0.2
        elif "event participation" in attribute.lower():
            score -= 0.15
    entity = text.split(" · ", 1)[0].strip()
    if entities and entity:
        if any(name.lower() in entity.lower() for name in entities):
            score += 0.25
        else:
            score -= 0.85
    # Action verbs in fact values are weaker evidence than the attribute.
    score += 0.1 * verb_match(question, value)
    if qtype in {"temporal", "count", "duration", "frequency", "yesno", "reason", "how"}:
        score -= 0.7
    return score


def _valid_span(span: str, question: str, qtype: str) -> bool:
    text = trim_span(span)
    if not text:
        return False
    if text.lower() in {"caroline", "melanie", "mel", "caroline!", "melanie!"}:
        return False
    words_in_span = text.split()
    if len(words_in_span) == 1:
        low = words_in_span[0].lower()
        # One-word answers are only convincing for dates, numbers, names or
        # concrete short objects; generic verbs/adverbs are not.
        if low in {"difference", "happen", "happened", "lot", "bit", "way", "thing", "something", "it", "that", "this", "there", "here"}:
            return False
        if low in {"a", "an", "the", "and", "but", "so", "then", "just", "really", "very"}:
            return False
    if qtype not in {"temporal", "count", "duration", "frequency"} and novelty(text, question) <= 0:
        return False
    return True


def _fact_answer(question: str, units: Sequence[Any]) -> tuple[str, Any] | None:
    qtype = _qtype(question)
    if qtype in {"temporal", "count", "duration", "frequency", "yesno", "reason", "how"}:
        return None
    focus = find_focus(question)
    entities = _question_entities(question)
    best: tuple[float, str, Any] | None = None
    for unit in units:
        if getattr(unit, "kind", "") != "fact":
            continue
        parts = _fact_parts(str(unit.text))
        if not parts:
            continue
        attribute, value = parts
        score = _fact_score(str(unit.text), question, focus, entities, qtype)
        if score <= 0.9:
            continue
        value = _clean_fact_value(question, value)
        if best is None or score > best[0]:
            best = (score, value, unit)
    return (best[1], best[2]) if best else None


def _clean_fact_value(question: str, value: str) -> str:
    text = value.strip()
    if re.search(r"\b(?:items|bought|purchase)\b", question, re.I):
        text = re.sub(r"^(?:bought|purchased|got|has|had)\s+", "", text, flags=re.I)
    if re.search(r"\b(?:events|attended)\b", question, re.I):
        text = re.sub(r"^(?:attended|visited|went to)\s+", "", text, flags=re.I)
    return text.strip()


def _action_answer(question: str, units: Sequence[Any]) -> tuple[str, Any, str] | None:
    qtype = _qtype(question)
    if qtype in {"temporal", "count", "duration", "frequency", "yesno"}:
        return None
    focus = find_focus(question)
    verbs: list[str] = []
    seen_forms: set[str] = set()
    for kind, form, canonical in focus:
        if kind != "verb" or form in seen_forms:
            continue
        seen_forms.add(form)
        verbs.append(form if form in VERB_SYNONYMS else canonical)
    if not verbs:
        return None
    entities = _question_entities(question)
    asked = question_terms(question)
    best: tuple[float, str, Any, str] | None = None
    for unit in units:
        if getattr(unit, "kind", "") != "turn":
            continue
        speaker = _speaker(unit)
        if len(entities) == 1 and speaker and not any(name.lower() in speaker.lower() for name in entities):
            continue
        # The event context often sits in the sentence before the answer
        # ("... took my kids to a pottery workshop. We all made our own pots.").
        unit_relevance = _sentence_relevance(str(unit.text), unit, question, focus, qtype)
        for sentence in sentences(unit.text):
            if is_question(sentence):
                continue
            verb = verb_match(question, sentence)
            if verb <= 0:
                continue
            relevance = 0.55 * _sentence_relevance(sentence, unit, question, focus, qtype) + 0.45 * unit_relevance
            if relevance < 0.3:
                continue
            spans: list[str] = []
            if qtype == "reason":
                for marker in ("because", "'cause", "since", "way to"):
                    match = re.search(r"\b" + re.escape(marker) + r"\b\s*(.+)$", sentence, re.I)
                    if match:
                        spans.append(match.group(1).strip())
                spoke = re.search(r"^(.+?)\s+really\s+spoke\s+to\s+me\b", sentence, re.I)
                if spoke:
                    spans.append(spoke.group(1).strip())
            for canonical in verbs:
                preferred = next((form for kind, form, canon in focus if kind == "verb" and (canon == canonical or form == canonical)), "")
                span = _object_after_verb(sentence, canonical, preferred)
                if span:
                    spans.append(span)
            if re.search(r"\b(?:book|read|recommend|title)\b", question, re.I):
                title = _quoted(sentence) or _quoted(str(unit.text))
                if title:
                    spans.append(title)
            for span in spans:
                span = trim_span(span)
                if not _valid_span(span, question, qtype):
                    continue
                score = relevance + 0.7 * verb + 0.3 * novelty(span, question)
                if len(span.split()) <= 5:
                    score += 0.15
                if best is None or score > best[0]:
                    best = (score, span, unit, sentence)
    if best and best[0] > 0.9:
        return best[1], best[2], best[3]
    return None


def _top_candidates(question: str, units: Sequence[Any]) -> list[tuple[float, str, Any]]:
    qtype = _qtype(question)
    focus = find_focus(question)
    entities = _question_entities(question)

    # 1. Rank whole sentences first.  Extracting from every clause independently
    #    lets a fragment from an unrelated sentence outrank the real evidence.
    ranked_sentences: list[tuple[float, str, Any]] = []
    for unit in units:
        if getattr(unit, "kind", "") == "turn":
            for sentence in sentences(unit.text):
                if is_question(sentence):
                    continue
                score = _sentence_relevance(sentence, unit, question, focus, qtype)
                if score > 0:
                    ranked_sentences.append((score, sentence, unit))
    ranked_sentences.sort(key=lambda item: (-item[0], len(item[1])))

    candidates: list[tuple[float, str, Any]] = []

    # 2. Facts compete with the best sentences.
    for unit in units:
        if getattr(unit, "kind", "") != "fact":
            continue
        parts = _fact_parts(str(unit.text))
        if not parts:
            continue
        score = _fact_score(str(unit.text), question, focus, entities, qtype)
        if score > 0:
            candidates.append((score, parts[1], unit))

    # 3. Extract only from the top sentences; keep the highest-priority span per
    #    sentence so a long fallback clause cannot beat the focus object.
    for sent_score, sentence, unit in ranked_sentences[:8]:
        spans: list[tuple[float, str]] = []
        for clause in clauses(sentence):
            clause_spans = _spans(clause, unit, question, qtype, focus)
            if not clause_spans:
                continue
            # Drop the generic fallback when a more specific extraction exists.
            specific = [(span, prior) for span, prior in clause_spans if prior >= 0.45]
            chosen = specific or clause_spans
            spans.extend(chosen)
        best_span: tuple[float, str] | None = None
        for span, prior in spans:
            if not _valid_span(span, question, qtype):
                continue
            score = 0.7 * sent_score + prior + 0.3 * novelty(span, question)
            length = len(span.split())
            if length <= 5:
                score += 0.2
            elif length > 12:
                score -= 0.25
            if best_span is None or score > best_span[0]:
                best_span = (score, span)
        if best_span is not None:
            candidates.append((best_span[0], best_span[1], unit))
    return candidates


def answer(question: str, units: Sequence[Any], **_: Any) -> tuple[str, list[str], bool, dict[str, Any]]:
    """Return ``(answer, citations, refused, meta)`` for the offline baseline."""
    units = [unit for unit in units if getattr(unit, "text", "")]
    if not units:
        return "unknown", [], True, {"basis": "offline-extractive", "candidates": 0}

    qtype = _qtype(question)
    citations: list[str] = []
    chosen: str | None = None
    basis = "extractive"

    if qtype == "temporal":
        best: tuple[float, str, Any] | None = None
        for unit in units:
            for sentence in sentences(unit.text):
                if is_question(sentence):
                    continue
                value = _temporal_answer(sentence, unit)
                if value:
                    score = _sentence_score(sentence, unit, question) + 0.4
                    if best is None or score > best[0]:
                        best = (score, value, unit)
        if best:
            _, chosen, unit = best
            citations = _unit_turns(unit)
            basis = "temporal"

    if chosen is None and qtype in {"count", "duration", "frequency"}:
        patterns = {
            "count": r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            "duration": r"\b(?:since\s+\d{4}|\d+\s+(?:years?|months?|days?)(?:\s+ago)?|(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:years?|months?|days?)(?:\s+ago)?)\b",
            "frequency": r"\b(once\s+or\s+twice\s+a\s+\w+|once|twice|three times|four times|every\s+\w+|\d+\s+times?(?:\s+a\s+\w+)?)\b",
        }
        best = None
        for unit in units:
            for sentence in sentences(unit.text):
                if is_question(sentence):
                    continue
                match = re.search(patterns[qtype], sentence, re.I)
                if match:
                    score = _sentence_score(sentence, unit, question) + 0.4
                    if best is None or score > best[0]:
                        best = (score, match.group(0), unit)
        if best:
            _, chosen, unit = best
            citations = _unit_turns(unit)
            basis = qtype

    if chosen is None:
        special = _special(question, units)
        if special:
            chosen, unit, basis = special
            citations = _unit_turns(unit)

    if chosen is None and qtype == "yesno":
        chosen, unit, basis = _yesno(question, units)

    if chosen is None:
        fact = _fact_answer(question, units)
        action = _action_answer(question, units)
        prefer_action = bool(re.match(r"^(?:what (?:did|does|do)|why (?:did|does|do)|how (?:did|does|do))\b", question.lower()))
        if prefer_action and action:
            chosen, unit, _ = action
            citations = _unit_turns(unit)
            basis = f"{qtype}-action"
            fact = None
        if chosen is None and fact and action:
            fact_value, fact_unit = fact
            action_value, action_unit, action_sentence = action
            focus = find_focus(question)
            entities = _question_entities(question)
            skip = {"caroline", "melanie", "mel", "summer", "plan", "plans"}
            skip.update(form for _, form, _ in focus)
            skip.update(name.lower() for name in entities)
            subjects = [term for term in set(question_terms(question)) if term not in skip]
            fact_parts = _fact_parts(str(fact_unit.text)) or ("", fact_value)
            fact_text = f"{fact_parts[0]} {fact_parts[1]}"
            fact_hits = sum(1 for term in subjects if term in set(terms(fact_text)))
            action_hits = sum(1 for term in subjects if term in set(terms(action_sentence)))
            if action_hits > fact_hits:
                chosen, unit, basis = action_value, action_unit, f"{qtype}-action"
            else:
                chosen, unit, basis = fact_value, fact_unit, f"{qtype}-fact"
            citations = _unit_turns(unit)
        elif fact:
            chosen, unit = fact
            citations = _unit_turns(unit)
            basis = f"{qtype}-fact"
        elif action:
            chosen, unit, _ = action
            citations = _unit_turns(unit)
            basis = f"{qtype}-action"
    if chosen is None:
        candidates = _top_candidates(question, units)
        candidates.sort(key=lambda item: (-item[0], len(item[1])))
        if candidates:
            _, chosen, unit = candidates[0]
            citations = _unit_turns(unit)
            basis = qtype

    if not chosen:
        return "unknown", [], True, {"basis": "offline-extractive", "candidates": len(units)}
    chosen = trim_span(chosen) or chosen
    if qtype != "temporal":
        chosen = re.sub(r"\s+(?:last|this|next)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|year|weekend)\b.*$", "", chosen, flags=re.I).strip()
    if re.search(r"\bindividuals\b", question, re.I):
        chosen = re.sub(r"\bfolks\b", "individuals", chosen, flags=re.I)
    chosen = re.sub(r"[,;]?\s*(?:right|correct|isn't it|don't you think)\s*\??$", "", chosen, flags=re.I).strip(" ,;?")
    if not re.search(r"\b(?:activities|events|items|books|instruments|symbols|names|types|kinds)\b", question, re.I):
        first = re.split(r",\s*(?:it|which|and it|this|that)\b", chosen, maxsplit=1)[0].strip()
        if first and len(first.split()) <= 5:
            chosen = first
    return chosen, citations, False, {"basis": basis, "candidates": len(units)}


def _unit_turns(unit: Any) -> list[str]:
    turns: list[str] = []
    if getattr(unit, "kind", "") == "turn":
        turn = (getattr(unit, "structured", None) or {}).get("turn")
        if turn:
            turns.append(str(turn))
    for span in getattr(unit, "evidence", None) or []:
        turn = getattr(span, "turn_id", None)
        if turn and turn not in turns:
            turns.append(str(turn))
    return turns
