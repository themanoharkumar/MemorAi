"""
PDF parsing service for MemorAI using PyMuPDF (fitz).
Same three-filter image detection logic:
  1. Size   — skip images <= 100x100px
  2. Position — skip images in header/footer zones (< 8% or > 92% of page height)
  3. Frequency — skip template elements appearing on > 30% of pages
"""

import hashlib
from dataclasses import dataclass

import fitz  # PyMuPDF

CHUNK_THRESHOLD = 40  # Pages: chunk anything over this
CHUNK_SIZE = 40


def _hash_image_bytes(data: bytes) -> int:
    """Simple sum of first 100 byte values — used to deduplicate repeated images."""
    total = 0
    for b in data[:100]:
        total += b
    return total


def detect_pdf_type(
    data: bytes,
    max_pages: int | None = None,
    skip_pages: int = 0,
) -> str:
    """
    Walks every page's images and applies three filters to decide whether
    the PDF contains meaningful educational images.
    Returns 'vision' or 'text'.
    """
    doc = fitz.open(stream=data, filetype="pdf")
    total_pages = doc.page_count

    start_page = min(skip_pages, total_pages - 1)
    pages_to_scan = total_pages - start_page
    if max_pages is not None:
        pages_to_scan = min(pages_to_scan, max_pages)

    end_page = start_page + pages_to_scan

    # Track which pages each image hash appears on (for frequency filter)
    hash_to_pages: dict[int, set[int]] = {}
    image_records: list[dict] = []

    for page_idx in range(start_page, end_page):
        page = doc[page_idx]
        page_height = page.rect.height

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            # Filter 1 — Size: skip tiny images
            if width <= 100 or height <= 100:
                continue

            img_data = base_image.get("image", b"")
            img_hash = _hash_image_bytes(img_data) if img_data else width * 1000 + height

            # Estimate vertical center using image bounding boxes on page
            y_center = 0.5
            for item in page.get_image_info():
                if item.get("xref") == xref:
                    bbox = item.get("bbox")
                    if bbox and page_height > 0:
                        y_center = ((bbox[1] + bbox[3]) / 2) / page_height
                    break

            image_records.append({
                "hash": img_hash,
                "width": width,
                "height": height,
                "y_center": y_center,
                "page_idx": page_idx,
            })

            if img_hash not in hash_to_pages:
                hash_to_pages[img_hash] = set()
            hash_to_pages[img_hash].add(page_idx)

    doc.close()

    # Apply all three filters
    for img in image_records:
        # Filter 1 — Size (already applied above)
        if img["width"] <= 100 or img["height"] <= 100:
            continue

        # Filter 2 — Position: vertical center must be between 8% and 92%
        if img["y_center"] < 0.08 or img["y_center"] > 0.92:
            continue

        # Filter 3 — Frequency: skip template elements appearing on >30% of pages
        pages_with_hash = len(hash_to_pages.get(img["hash"], set()))
        if pages_to_scan > 1 and pages_with_hash / pages_to_scan > 0.3:
            continue

        # Image passed all three filters
        return "vision"

    return "text"


def extract_text_from_pdf(data: bytes) -> str:
    """
    Extracts text content from every page, joining with double newlines.
    Skips pages that fail to parse.
    """
    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[str] = []

    for page_idx in range(doc.page_count):
        try:
            page = doc[page_idx]
            text = page.get_text().strip()
            if text:
                pages.append(text)
        except Exception:
            continue

    doc.close()
    return "\n\n".join(pages)


def get_pdf_page_count(data: bytes) -> int:
    """Returns the total number of pages in the PDF."""
    doc = fitz.open(stream=data, filetype="pdf")
    count = doc.page_count
    doc.close()
    return count


def extract_text_by_chunks(
    data: bytes,
    chunk_size: int = CHUNK_SIZE,
) -> list[dict]:
    """
    Splits PDF text extraction into chunks of chunk_size pages.
    Returns list of {chunkIndex, startPage, endPage, text} dicts.
    """
    doc = fitz.open(stream=data, filetype="pdf")
    total_pages = doc.page_count
    chunks: list[dict] = []
    chunk_index = 0

    start_page = 0
    while start_page < total_pages:
        end_page = min(start_page + chunk_size - 1, total_pages - 1)
        chunk_text_parts: list[str] = []

        for page_idx in range(start_page, end_page + 1):
            try:
                page = doc[page_idx]
                text = page.get_text().strip()
                chunk_text_parts.append(f"\n\n--- Page {page_idx + 1} ---\n{text}")
            except Exception:
                continue

        chunks.append({
            "chunkIndex": chunk_index,
            "startPage": start_page + 1,
            "endPage": end_page + 1,
            "text": "".join(chunk_text_parts).strip(),
        })
        chunk_index += 1
        start_page += chunk_size

    doc.close()
    return chunks


def hash_pdf(data: bytes) -> str:
    """Computes SHA-256 hash of raw PDF bytes — used for deduplication."""
    return hashlib.sha256(data).hexdigest()
