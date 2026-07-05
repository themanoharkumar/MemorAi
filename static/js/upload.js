/**
 * MemorAI — PDF Upload with drag-and-drop and streaming NDJSON ingestion progress
 * Handles the home page upload flow with real-time status updates.
 */

document.addEventListener('DOMContentLoaded', () => {
  const uploadZone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');
  const titleInput = document.getElementById('deck-title');
  const uploadBtn = document.getElementById('upload-btn');
  const ingestionOverlay = document.getElementById('ingestion-overlay');
  const progressStatus = document.getElementById('progress-status');
  const progressBar = document.getElementById('progress-bar');
  const progressEta = document.getElementById('progress-eta');
  const progressDetail = document.getElementById('progress-detail');

  let selectedFile = null;
  let etaInterval = null;

  // ── File Selection ──────────────────────────────────────────────────────

  function onFileSelected(file) {
    if (!file || file.type !== 'application/pdf') {
      toast.error('Please select a valid PDF file.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast.error('File too large. Maximum size is 20MB.');
      return;
    }
    selectedFile = file;
    updateUploadUI(file);
  }

  function updateUploadUI(file) {
    const icon = uploadZone.querySelector('.upload-icon');
    const title = uploadZone.querySelector('.upload-title');
    const subtitle = uploadZone.querySelector('.upload-subtitle');
    if (icon) icon.textContent = '📄';
    if (title) title.textContent = file.name;
    if (subtitle) subtitle.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to upload`;
    uploadZone.style.borderColor = 'var(--color-primary)';
    uploadZone.style.background = 'rgba(108, 99, 255, 0.07)';
    if (uploadBtn) uploadBtn.disabled = false;
  }

  // ── Drag and Drop ───────────────────────────────────────────────────────

  if (uploadZone) {
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) onFileSelected(file);
    });
    uploadZone.addEventListener('click', (e) => {
      if (e.target !== fileInput) fileInput && fileInput.click();
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) onFileSelected(fileInput.files[0]);
    });
  }

  // ── Upload and Stream ───────────────────────────────────────────────────

  if (uploadBtn) {
    uploadBtn.addEventListener('click', startUpload);
  }

  async function startUpload() {
    if (!selectedFile) { toast.error('Please select a PDF file first.'); return; }
    showIngestionOverlay();
    const formData = new FormData();
    formData.append('pdf', selectedFile);
    if (titleInput && titleInput.value.trim()) {
      formData.append('title', titleInput.value.trim());
    }

    try {
      const response = await fetch('/api/ingest', { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Upload failed');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line
        for (const line of lines) {
          if (line.trim()) handleProgress(JSON.parse(line));
        }
      }
    } catch (err) {
      hideIngestionOverlay();
      toast.error(err.message || 'Upload failed. Please try again.');
    }
  }

  let etaSeconds = 0;
  let etaStart = 0;

  function handleProgress(event) {
    const { status } = event;

    if (status === 'analyzing') {
      setProgress('🔍 Analyzing PDF...', 15);
    } else if (status === 'processing') {
      const typeLabel = event.pdf_type === 'vision' ? 'vision' : 'text';
      setProgress(`⚡ Generating flashcards (${typeLabel} mode, ${event.page_count} pages)...`, 35);
      if (event.estimated_seconds) startEtaCountdown(event.estimated_seconds);
    } else if (status === 'saving') {
      clearEta();
      setProgress('💾 Saving your deck...', 85);
    } else if (status === 'done') {
      clearEta();
      setProgress('✅ Done!', 100);
      if (event.existing) {
        setTimeout(() => { window.location.href = `/decks/${event.deck_id}`; }, 800);
      } else if (event.deck) {
        setTimeout(() => { window.location.href = `/decks/${event.deck.id}`; }, 800);
      }
    } else if (status === 'error') {
      clearEta();
      hideIngestionOverlay();
      let msg = event.error || 'Processing failed.';
      if (event.retry_after_seconds) msg += ` Retry in ${event.retry_after_seconds}s.`;
      toast.error(msg);
    }
  }

  function setProgress(label, pct) {
    if (progressStatus) progressStatus.textContent = label;
    if (progressBar) progressBar.style.width = `${pct}%`;
  }

  function startEtaCountdown(seconds) {
    etaSeconds = seconds;
    etaStart = Date.now();
    updateEtaLabel();
    etaInterval = setInterval(() => {
      const elapsed = Math.round((Date.now() - etaStart) / 1000);
      const remaining = Math.max(0, etaSeconds - elapsed);
      if (progressEta) progressEta.textContent = remaining > 0 ? `~${remaining}s remaining` : 'Almost done...';
    }, 1000);
  }

  function updateEtaLabel() {
    if (progressEta) progressEta.textContent = `~${etaSeconds}s remaining`;
  }

  function clearEta() {
    if (etaInterval) { clearInterval(etaInterval); etaInterval = null; }
    if (progressEta) progressEta.textContent = '';
  }

  function showIngestionOverlay() {
    if (ingestionOverlay) {
      ingestionOverlay.style.display = 'flex';
      setProgress('📤 Uploading...', 5);
    }
  }

  function hideIngestionOverlay() {
    if (ingestionOverlay) ingestionOverlay.style.display = 'none';
  }
});
