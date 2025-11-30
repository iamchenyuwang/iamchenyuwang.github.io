// Update Google Scholar metrics on the Publications page from a JSON file.
// Falls back to existing numbers in the HTML if the JSON cannot be loaded.

(function updateScholarMetrics() {
    const citationsEl = document.getElementById('citations-count');
    const hIndexEl = document.getElementById('hindex-count');
    const i10El = document.getElementById('i10-count');

    if (!citationsEl || !hIndexEl || !i10El) return;

    fetch('assets/data/scholar_metrics.json', { cache: 'no-store' })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
            if (!data) return;
            if (typeof data.citations === 'number') {
                citationsEl.textContent = String(data.citations);
            }
            if (typeof data.h_index === 'number') {
                hIndexEl.textContent = String(data.h_index);
            }
            if (typeof data.i10_index === 'number') {
                i10El.textContent = String(data.i10_index);
            }
        })
        .catch(() => {
            // Silently ignore; keep hardcoded values as fallback.
        });
})();


