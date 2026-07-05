"""
Gemini AI client and flashcard generation helpers for MemorAI.
Uses the new `google.genai` Python SDK (google-genai package).
"""

import asyncio
import json
import os
import re
import tempfile
from dataclasses import dataclass

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-2.5-flash"
DEFAULT_RETRY_WAIT_SECONDS = 15
MAX_RATE_LIMIT_RETRIES = 1

FLASHCARD_PROMPT = """You are a cognitive science expert designing flashcards for maximum long-term retention.

You have the full document — read all text, diagrams, charts, graphs, equations, and visual content.

For every major concept, create cards that test:
1. Definition — what is it exactly?
2. Application — a worked example or real use case
3. Relationship — how does it connect to another concept in this material?
4. Edge case — when does it NOT apply, or what is the common misconception?

Rules:
- Each card tests exactly ONE specific idea
- Questions must require genuine understanding, not pattern matching
- Answers should be concise — 1 to 3 sentences
- Generate between 15 and 25 cards depending on depth of material
- If you see a diagram or chart, create at least one card about what it shows

Return ONLY a raw JSON array. No markdown, no backticks, no explanation:
[{"front":"...","back":"...","topic":"...","type":"definition|application|relationship|edge_case","source":"text|visual|both"}]"""


@dataclass
class RawCard:
    front: str
    back: str
    topic: str
    type: str
    source: str


class GeminiRateLimitError(Exception):
    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
        is_daily_quota: bool = False,
        quota_id: str | None = None,
        quota_metric: str | None = None,
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.is_daily_quota = is_daily_quota
        self.quota_id = quota_id
        self.quota_metric = quota_metric


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    return genai.Client(api_key=api_key)


def _is_rate_limit_error(err: Exception) -> bool:
    msg = str(err).lower()
    return "429" in msg or "503" in msg or "quota" in msg or "rate" in msg


def _parse_retry_after_seconds(err: Exception) -> int | None:
    msg = str(err)
    match = re.search(r'retry[_ ]?after["\s:]+(\d+)', msg, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    match = re.search(r'retry in\s+(\d+(?:\.\d+)?)s', msg, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    return None


def _is_daily_quota(err: Exception) -> bool:
    return "perday" in str(err).lower() or "daily" in str(err).lower()


def _to_rate_limit_error(err: Exception) -> GeminiRateLimitError:
    retry_after = _parse_retry_after_seconds(err)
    is_daily = _is_daily_quota(err)

    if is_daily:
        return GeminiRateLimitError(
            "Gemini daily quota reached for this API key/model. Try again later or use a different key/model.",
            retry_after_seconds=retry_after,
            is_daily_quota=True,
        )

    if "minute" in str(err).lower() or "perminute" in str(err).lower():
        return GeminiRateLimitError(
            "Gemini per-minute rate limit reached. Wait about 60 seconds and try again.",
            retry_after_seconds=retry_after or 60,
            is_daily_quota=False,
        )

    return GeminiRateLimitError(
        "Gemini is rate-limiting requests. Please retry shortly.",
        retry_after_seconds=retry_after,
        is_daily_quota=False,
    )


def _parse_gemini_response(text: str) -> list[RawCard]:
    """Parse Gemini's JSON response into a list of RawCard objects."""
    clean = re.sub(r'```json|```', '', text, flags=re.IGNORECASE).strip()
    candidates = [clean]

    arr_start = clean.find('[')
    arr_end = clean.rfind(']')
    if arr_start != -1 and arr_end > arr_start:
        candidates.append(clean[arr_start:arr_end + 1].strip())

    obj_start = clean.find('{')
    obj_end = clean.rfind('}')
    if obj_start != -1 and obj_end > obj_start:
        candidates.append(clean[obj_start:obj_end + 1].strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                cards = []
                for c in parsed:
                    if isinstance(c, dict) and 'front' in c and 'back' in c:
                        cards.append(RawCard(
                            front=c.get('front', ''),
                            back=c.get('back', ''),
                            topic=c.get('topic', 'General'),
                            type=c.get('type', 'definition'),
                            source=c.get('source', 'text'),
                        ))
                return cards
            if isinstance(parsed, dict) and isinstance(parsed.get("cards"), list):
                cards = []
                for c in parsed["cards"]:
                    if isinstance(c, dict) and 'front' in c and 'back' in c:
                        cards.append(RawCard(
                            front=c.get('front', ''),
                            back=c.get('back', ''),
                            topic=c.get('topic', 'General'),
                            type=c.get('type', 'definition'),
                            source=c.get('source', 'text'),
                        ))
                return cards
        except Exception:
            continue

    raise ValueError("Failed to parse flashcard response from Gemini")


async def generate_with_vision(pdf_data: bytes) -> list[RawCard]:
    """Vision path: for PDFs containing images/diagrams."""
    print(f"[gemini] using vision path, buffer size: {len(pdf_data)}")

    client = _get_client()

    async def call_gemini(retries: int = MAX_RATE_LIMIT_RETRIES) -> str:
        import base64

        if len(pdf_data) < 15 * 1024 * 1024:
            # Small PDF: inline base64
            content_part = types.Part.from_bytes(
                data=pdf_data,
                mime_type="application/pdf",
            )
        else:
            # Large PDF: File API
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name

            try:
                # Upload file
                uploaded = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.files.upload(path=tmp_path, config={"mime_type": "application/pdf", "display_name": "study-material.pdf"})
                )

                # Wait for file to be ready
                polls = 0
                while hasattr(uploaded, 'state') and str(uploaded.state).upper() == "PROCESSING" and polls < 10:
                    await asyncio.sleep(2)
                    uploaded = await asyncio.get_event_loop().run_in_executor(None, lambda: client.files.get(name=uploaded.name))
                    polls += 1

                content_part = types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf")
            finally:
                import os as _os
                _os.unlink(tmp_path)

        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=MODEL,
                        contents=[content_part, FLASHCARD_PROMPT],
                    )
                ),
                timeout=90.0
            )
            return response.text
        except Exception as err:
            if _is_rate_limit_error(err):
                rate_err = _to_rate_limit_error(err)
                retry_after = rate_err.retry_after_seconds or DEFAULT_RETRY_WAIT_SECONDS
                if retries > 0 and not rate_err.is_daily_quota:
                    print(f"[gemini] vision path rate-limited. Retrying in {retry_after}s... ({retries} left)")
                    await asyncio.sleep(retry_after)
                    return await call_gemini(retries - 1)
                raise rate_err
            raise

    text = await call_gemini()
    return _parse_gemini_response(text)


async def generate_with_text(text_content: str, custom_prompt: str = FLASHCARD_PROMPT) -> list[RawCard]:
    """Text path: for text-only PDFs (cheaper, faster)."""
    print(f"[gemini] using text path, chars: {len(text_content)}")

    client = _get_client()

    async def call_gemini(prompt: str, retries: int = MAX_RATE_LIMIT_RETRIES) -> str:
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=MODEL,
                        contents=[
                            f"DOCUMENT TEXT:\n\n{text_content}",
                            prompt,
                        ],
                    )
                ),
                timeout=90.0
            )
            return response.text
        except Exception as err:
            if _is_rate_limit_error(err):
                rate_err = _to_rate_limit_error(err)
                retry_after = rate_err.retry_after_seconds or DEFAULT_RETRY_WAIT_SECONDS
                if retries > 0 and not rate_err.is_daily_quota:
                    print(f"[gemini] text path rate-limited. Retrying in {retry_after}s... ({retries} left)")
                    await asyncio.sleep(retry_after)
                    return await call_gemini(prompt, retries - 1)
                raise rate_err
            print(f"[gemini] Request failed immediately: {err}")
            raise

    text = await call_gemini(custom_prompt)
    return _parse_gemini_response(text)


def _deduplicate_cards(cards: list[RawCard]) -> list[RawCard]:
    seen: set[str] = set()
    result: list[RawCard] = []
    for card in cards:
        key = re.sub(r'[^a-z0-9 ]', '', card.front.lower())[:60].strip()
        if key not in seen:
            seen.add(key)
            result.append(card)
    return result


def _cap_by_topic(cards: list[RawCard], max_per_topic: int = 4) -> list[RawCard]:
    topic_counts: dict[str, int] = {}
    result: list[RawCard] = []
    for card in cards:
        topic = card.topic.lower()
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if topic_counts[topic] <= max_per_topic:
            result.append(card)
    return result


async def generate_from_chunks(chunks: list[dict]) -> list[RawCard]:
    """Process large PDFs in chunks — sequential to avoid rate limits."""
    all_cards: list[RawCard] = []

    for chunk in chunks:
        print(f"[gemini] processing chunk {chunk['chunkIndex'] + 1}/{len(chunks)} pages {chunk['startPage']}-{chunk['endPage']}")

        chunk_prompt = f"""This is pages {chunk['startPage']} to {chunk['endPage']} of a larger document.
Generate 10-15 flashcards covering only the content in these pages.
Focus on the most important concepts. Do not repeat concepts already likely covered in earlier chapters.

Return ONLY a JSON array:
[{{"front":"...","back":"...","topic":"...","type":"...","source":"text"}}]"""

        try:
            cards = await generate_with_text(chunk["text"], chunk_prompt)
            all_cards.extend(cards)
        except Exception as err:
            print(f"[gemini] chunk {chunk['chunkIndex']} failed: {err}")
            # Continue — partial results are better than none

        # Small delay between chunks to avoid free-tier rapid limits
        if chunk["chunkIndex"] < len(chunks) - 1:
            await asyncio.sleep(2)

    return _cap_by_topic(_deduplicate_cards(all_cards))
