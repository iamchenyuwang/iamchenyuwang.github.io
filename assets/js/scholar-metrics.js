// Update Google Scholar metrics on the Publications page from a JSON file.
// Updates both overall stats (citations, h-index, i10-index) and per-paper citation counts.
// Falls back to existing numbers in the HTML if the JSON cannot be loaded.

(function updateScholarMetrics() {
    fetch('assets/data/scholar_metrics.json', { cache: 'no-store' })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
            if (!data) return;

            // Update overall stats
            var citationsEl = document.getElementById('citations-count');
            var hIndexEl = document.getElementById('hindex-count');
            var i10El = document.getElementById('i10-count');

            if (citationsEl && typeof data.citations === 'number') {
                citationsEl.textContent = String(data.citations);
            }
            if (hIndexEl && typeof data.h_index === 'number') {
                hIndexEl.textContent = String(data.h_index);
            }
            if (i10El && typeof data.i10_index === 'number') {
                i10El.textContent = String(data.i10_index);
            }

            // Update per-paper citation counts
            if (!Array.isArray(data.articles)) return;

            // Build a lookup map: normalized title -> citation count
            var citationMap = {};
            data.articles.forEach(function (article) {
                var key = normalizeTitle(article.title);
                citationMap[key] = article.citations;
            });

            // Find all publication items and update their citation counts
            var pubItems = document.querySelectorAll('.pub-item');
            pubItems.forEach(function (item) {
                var titleEl = item.querySelector('.pub-title');
                if (!titleEl) return;

                var key = normalizeTitle(titleEl.textContent);
                if (!(key in citationMap)) return;

                var count = citationMap[key];

                // Update the metric span
                var metricEl = item.querySelector('.pub-metrics .metric');
                if (metricEl && count > 0) {
                    metricEl.innerHTML = '<i class="fas fa-quote-left"></i> ' + count + ' citation' + (count !== 1 ? 's' : '');
                } else if (!metricEl && count > 0) {
                    // Create metrics div if it doesn't exist
                    var metricsDiv = document.createElement('div');
                    metricsDiv.className = 'pub-metrics';
                    metricsDiv.innerHTML = '<span class="metric"><i class="fas fa-quote-left"></i> ' + count + ' citation' + (count !== 1 ? 's' : '') + '</span>';
                    var pubContent = item.querySelector('.pub-content');
                    var pubLinks = item.querySelector('.pub-links');
                    if (pubContent && pubLinks) {
                        pubContent.insertBefore(metricsDiv, pubLinks);
                    }
                }

                // Update "Cited by X" link text
                var citedByLinks = item.querySelectorAll('.pub-link');
                citedByLinks.forEach(function (link) {
                    if (link.textContent.trim().indexOf('Cited by') === 0) {
                        link.innerHTML = '<i class="fas fa-quote-right"></i> Cited by ' + count;
                    }
                });
            });

            // Also update Recent Works section on the homepage
            var workItems = document.querySelectorAll('.work-item');
            workItems.forEach(function (item) {
                var titleEl = item.querySelector('h3');
                if (!titleEl) return;

                var key = normalizeTitle(titleEl.textContent);
                if (!(key in citationMap)) return;

                var count = citationMap[key];
                // Update citation text in work-meta paragraphs
                var metaEls = item.querySelectorAll('.work-meta');
                metaEls.forEach(function (meta) {
                    var strongEls = meta.querySelectorAll('strong');
                    strongEls.forEach(function (strong) {
                        var text = strong.textContent;
                        if (text.match(/\d+ citation/)) {
                            strong.textContent = count + ' citation' + (count !== 1 ? 's' : '');
                        }
                    });
                });
            });
        })
        .catch(function () {
            // Silently ignore; keep hardcoded values as fallback.
        });

    function normalizeTitle(title) {
        return (title || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    }
})();
