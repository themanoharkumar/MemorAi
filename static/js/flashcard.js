/**
 * MemorAI — Flashcard 3D flip and study session logic
 * Keyboard shortcuts: Space/Enter = flip, 1-4 = rate, Escape = end session
 */

document.addEventListener('DOMContentLoaded', async () => {
  const deckId = window.DECK_ID;
  if (!deckId) return;

  // ── State ──────────────────────────────────────────────────────────────

  let cards = [];
  let currentIndex = 0;
  let isFlipped = false;
  let isTransitioning = false;
  let sessionStats = { again: 0, hard: 0, good: 0, easy: 0, total: 0 };

  // ── Elements ───────────────────────────────────────────────────────────

  const flashcard = document.getElementById('flashcard');
  const questionEl = document.getElementById('card-question');
  const answerEl = document.getElementById('card-answer');
  const topicEl = document.getElementById('card-topic');
  const typeEl = document.getElementById('card-type');
  const flipHint = document.getElementById('flip-hint');
  const ratingSection = document.getElementById('rating-section');
  const progressText = document.getElementById('session-progress');
  const sessionDone = document.getElementById('session-done');
  const studyArea = document.getElementById('study-area');
  const loadingEl = document.getElementById('study-loading');

  // Interval preview elements
  const previewEls = {
    0: document.getElementById('preview-0'),
    1: document.getElementById('preview-1'),
    2: document.getElementById('preview-2'),
    3: document.getElementById('preview-3'),
  };

  // ── Load cards ─────────────────────────────────────────────────────────

  try {
    const data = await apiGet(`/api/study?deck_id=${deckId}&limit=50`);
    cards = data.cards || [];
    if (loadingEl) loadingEl.style.display = 'none';
    if (cards.length === 0) {
      showEmpty();
    } else {
      if (studyArea) studyArea.style.display = 'block';
      renderCard();
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    toast.error('Failed to load study cards.');
  }

  // ── Render card ─────────────────────────────────────────────────────────

  function renderCard() {
    const card = cards[currentIndex];
    if (!card) { showDone(); return; }

    isFlipped = false;
    if (flashcard) flashcard.classList.remove('flipped');
    if (flipHint) flipHint.style.display = 'block';
    if (ratingSection) ratingSection.style.display = 'none';

    if (questionEl) questionEl.textContent = card.front;
    if (answerEl) answerEl.textContent = card.back;
    if (topicEl) topicEl.textContent = card.topic;
    if (typeEl) { typeEl.textContent = formatCardType(card.type); }

    // Update progress
    if (progressText) {
      progressText.textContent = `${currentIndex + 1} / ${cards.length}`;
    }

    // Update interval previews
    const previews = previewIntervals(card);
    for (const [rating, days] of Object.entries(previews)) {
      const el = previewEls[rating];
      if (el) el.textContent = days === 1 ? '1 day' : `${days} days`;
    }
  }

  function previewIntervals(card) {
    return {
      0: calcInterval(card, 0),
      1: calcInterval(card, 1),
      2: calcInterval(card, 2),
      3: calcInterval(card, 3),
    };
  }

  function calcInterval(card, rating) {
    // Simplified preview matching SM-2 logic
    let { ease_factor: ef, interval, repetitions: reps } = card;
    ef = Math.max(1.3, parseFloat((ef + 0.1 - (3 - rating) * (0.08 + (3 - rating) * 0.02)).toFixed(2)));
    if (rating === 0) return 1;
    if (rating === 1) { return reps === 0 ? 1 : reps === 1 ? 3 : Math.max(2, Math.round(interval * 1.2)); }
    if (rating === 2) { return reps === 0 ? 1 : reps === 1 ? 6 : Math.round(interval * ef); }
    return reps === 0 ? 4 : reps === 1 ? 10 : Math.round(interval * ef * 1.3);
  }

  // ── Flip card ──────────────────────────────────────────────────────────

  function flipCard() {
    if (isTransitioning) return;
    isFlipped = !isFlipped;
    if (flashcard) flashcard.classList.toggle('flipped', isFlipped);
    if (isFlipped) {
      if (flipHint) flipHint.style.display = 'none';
      if (ratingSection) ratingSection.style.display = 'grid';
    } else {
      if (flipHint) flipHint.style.display = 'block';
      if (ratingSection) ratingSection.style.display = 'none';
    }
  }

  if (flashcard) {
    flashcard.addEventListener('click', flipCard);
  }

  // ── Rate card ──────────────────────────────────────────────────────────

  document.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const rating = parseInt(btn.dataset.rating);
      await submitRating(rating);
    });
  });

  async function submitRating(rating) {
    if (isTransitioning) return;
    isTransitioning = true;

    const card = cards[currentIndex];
    const ratingKeys = ['again', 'hard', 'good', 'easy'];
    sessionStats[ratingKeys[rating]]++;
    sessionStats.total++;

    try {
      await apiPost('/api/review', { card_id: card.id, rating });
    } catch (err) {
      toast.error('Failed to save review.');
    }

    // If Again (0), add card to end of queue
    if (rating === 0) {
      cards.push({ ...card });
    }

    currentIndex++;
    if (currentIndex >= cards.length) {
      showDone();
    } else {
      // Small transition delay for feel
      await new Promise(r => setTimeout(r, 150));
      renderCard();
    }

    isTransitioning = false;
  }

  // ── Keyboard shortcuts ─────────────────────────────────────────────────

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.code === 'Space' || e.code === 'Enter') { e.preventDefault(); flipCard(); }
    if (e.key === '1' && isFlipped) submitRating(0);
    if (e.key === '2' && isFlipped) submitRating(1);
    if (e.key === '3' && isFlipped) submitRating(2);
    if (e.key === '4' && isFlipped) submitRating(3);
  });

  // ── End states ─────────────────────────────────────────────────────────

  function showEmpty() {
    if (studyArea) studyArea.style.display = 'none';
    const emptyEl = document.getElementById('study-empty');
    if (emptyEl) emptyEl.style.display = 'block';
  }

  function showDone() {
    if (studyArea) studyArea.style.display = 'none';
    if (sessionDone) {
      sessionDone.style.display = 'flex';
      // Update stats summary
      const statsEl = document.getElementById('session-stats');
      if (statsEl) {
        const { again, hard, good, easy, total } = sessionStats;
        statsEl.innerHTML = `
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;text-align:center;margin:1.5rem 0">
            <div><div style="font-size:1.5rem;font-family:var(--font-display);font-weight:700;color:var(--color-danger)">${again}</div><div style="font-size:0.75rem;color:rgba(240,240,255,0.5);margin-top:0.25rem">Again</div></div>
            <div><div style="font-size:1.5rem;font-family:var(--font-display);font-weight:700;color:var(--color-warning)">${hard}</div><div style="font-size:0.75rem;color:rgba(240,240,255,0.5);margin-top:0.25rem">Hard</div></div>
            <div><div style="font-size:1.5rem;font-family:var(--font-display);font-weight:700;color:var(--color-primary)">${good}</div><div style="font-size:0.75rem;color:rgba(240,240,255,0.5);margin-top:0.25rem">Good</div></div>
            <div><div style="font-size:1.5rem;font-family:var(--font-display);font-weight:700;color:var(--color-success)">${easy}</div><div style="font-size:0.75rem;color:rgba(240,240,255,0.5);margin-top:0.25rem">Easy</div></div>
          </div>
        `;
      }
    }
  }
});
