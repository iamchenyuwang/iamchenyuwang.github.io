// Papers page logic: fetch JSON, render filters, list, and reader

(function() {
    const DATA_URL = '_data/tagged_papers.json';

    /** @type {Array<{title:string, abstract:string, url:string, published?:string, tags?:string[]}>} */
    let allPapers = [];
    let visiblePapers = [];
    let activeTags = new Set();

    // Chart time window: start from Jan 2015
    const START_YEAR = 2018;
    const START_MONTH = 1; // 1-12

    // Elements
    const searchInput = document.getElementById('paper-search');
    const tagList = document.getElementById('tag-list');
    const resetBtn = document.getElementById('reset-filters');
    const resultsCount = document.getElementById('results-count');
    const papersList = document.getElementById('papers-list');
    const emptyState = document.getElementById('empty-state');
    const chartCanvas = document.getElementById('papers-cumulative-chart');

    const readerCard = document.getElementById('reader-card');
    const readerContent = document.getElementById('reader-content');
    const readerTitle = document.getElementById('reader-title');
    const readerAbstract = document.getElementById('reader-abstract');
    const readerDate = document.getElementById('reader-date');
    const readerTags = document.getElementById('reader-tags');
    const readerOpen = document.getElementById('reader-open');

    // Util
    const normalize = (s) => (s || '').toLowerCase();
    const formatDate = (iso) => {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        } catch { return ''; }
    };

    function buildCumulativeSeries(papers) {
        // Group by YYYY-MM
        const monthlyCounts = new Map();
        for (const p of papers) {
            if (!p.published) continue;
            const d = new Date(p.published);
            if (isNaN(d)) continue;
            const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
            monthlyCounts.set(key, (monthlyCounts.get(key) || 0) + 1);
        }
        if (monthlyCounts.size === 0) return { labels: [], data: [] };

        // Build continuous months range from min to max
        const keys = Array.from(monthlyCounts.keys()).sort();
        const [minY, minM] = keys[0].split('-').map(Number);
        const [maxY, maxM] = keys[keys.length - 1].split('-').map(Number);
        // If all data is before the start window, nothing to show
        if (maxY < START_YEAR || (maxY === START_YEAR && maxM < START_MONTH)) {
            return { labels: [], data: [] };
        }
        const labels = [];
        const perMonth = [];
        // Clamp the start point to the requested window start
        let y = minY, m = minM;
        if (y < START_YEAR || (y === START_YEAR && m < START_MONTH)) {
            y = START_YEAR; m = START_MONTH;
        }
        while (y < maxY || (y === maxY && m <= maxM)) {
            const key = `${y}-${String(m).padStart(2, '0')}`;
            labels.push(key);
            perMonth.push(monthlyCounts.get(key) || 0);
            m += 1;
            if (m > 12) { m = 1; y += 1; }
        }

        // Cumulative sum
        const data = [];
        let acc = 0;
        for (const c of perMonth) {
            acc += c;
            data.push(acc);
        }
        return { labels, data };
    }

    function renderCumulativeChart(papers) {
        if (!chartCanvas || typeof Chart === 'undefined') return;
        const { labels, data } = buildCumulativeSeries(papers);
        const ctx = chartCanvas.getContext('2d');
        // Destroy previous chart instance if any (store on canvas)
        if (chartCanvas._chartInstance) {
            chartCanvas._chartInstance.destroy();
        }
        chartCanvas._chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.map(key => {
                    const [y, m] = key.split('-').map(Number);
                    const d = new Date(y, m - 1, 1);
                    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
                }),
                datasets: [{
                    label: 'Cumulative papers',
                    data,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.15)',
                    tension: 0.25,
                    fill: true,
                    pointRadius: 2,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.parsed.y} papers`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    function collectAllTags(papers) {
        const set = new Set();
        for (const p of papers) {
            if (Array.isArray(p.tags)) {
                p.tags.forEach(t => set.add(t));
            }
        }
        return Array.from(set).sort((a, b) => a.localeCompare(b));
    }

    function buildTagChips(tags) {
        tagList.innerHTML = '';
        tags.forEach(tag => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'tag-chip';
            btn.textContent = tag;
            btn.setAttribute('data-tag', tag);
            btn.addEventListener('click', () => {
                if (activeTags.has(tag)) {
                    activeTags.delete(tag);
                    btn.classList.remove('active');
                } else {
                    activeTags.add(tag);
                    btn.classList.add('active');
                }
                applyFilters();
            });
            tagList.appendChild(btn);
        });
    }

    function applyFilters() {
        const q = normalize(searchInput.value);
        visiblePapers = allPapers.filter(p => {
            const inSearch = !q || normalize(p.title).includes(q) || normalize(p.abstract).includes(q);
            const inTags = activeTags.size === 0 || (Array.isArray(p.tags) && [...activeTags].every(t => p.tags.includes(t)));
            return inSearch && inTags;
        });
        renderList();
    }

    function renderList() {
        papersList.innerHTML = '';
        const count = visiblePapers.length;
        resultsCount.textContent = `${count} result${count === 1 ? '' : 's'}`;
        emptyState.style.display = count ? 'none' : 'block';

        visiblePapers.forEach((p, idx) => {
            const li = document.createElement('li');
            li.className = 'paper-item';

            const title = document.createElement('h3');
            title.className = 'paper-title';
            title.textContent = p.title || 'Untitled';

            const meta = document.createElement('div');
            meta.className = 'paper-meta';
            const dateSpan = document.createElement('span');
            dateSpan.className = 'paper-date';
            dateSpan.textContent = formatDate(p.published);
            meta.appendChild(dateSpan);

            const tagsWrap = document.createElement('div');
            tagsWrap.className = 'paper-tags';
            (p.tags || []).forEach(t => {
                const chip = document.createElement('span');
                chip.className = 'tag-chip small';
                chip.textContent = t;
                tagsWrap.appendChild(chip);
            });

            const excerpt = document.createElement('p');
            excerpt.className = 'paper-excerpt';
            excerpt.textContent = (p.abstract || '').slice(0, 220) + ((p.abstract || '').length > 220 ? '…' : '');

            const actions = document.createElement('div');
            actions.className = 'paper-actions';
            if (readerCard) {
                const readBtn = document.createElement('button');
                readBtn.type = 'button';
                readBtn.className = 'btn-secondary';
                readBtn.innerHTML = '<i class="fas fa-eye"></i> Read';
                readBtn.addEventListener('click', () => openInReader(p));
                actions.appendChild(readBtn);
            }

            const openBtn = document.createElement('a');
            openBtn.href = p.url || '#';
            openBtn.target = '_blank';
            openBtn.rel = 'noopener';
            openBtn.className = 'btn-primary';
            openBtn.innerHTML = '<i class="fas fa-external-link-alt"></i> arXiv';

            actions.appendChild(openBtn);

            li.appendChild(title);
            li.appendChild(meta);
            if (tagsWrap.childNodes.length) li.appendChild(tagsWrap);
            li.appendChild(excerpt);
            li.appendChild(actions);

            papersList.appendChild(li);
        });
    }

    function openInReader(paper) {
        const placeholder = readerCard.querySelector('.reader-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        readerContent.style.display = 'block';
        readerTitle.textContent = paper.title || 'Untitled';
        readerAbstract.textContent = paper.abstract || '';
        readerDate.textContent = formatDate(paper.published);
        readerOpen.href = paper.url || '#';

        readerTags.innerHTML = '';
        (paper.tags || []).forEach(t => {
            const chip = document.createElement('span');
            chip.className = 'tag-chip small';
            chip.textContent = t;
            readerTags.appendChild(chip);
        });
    }

    function resetFilters() {
        searchInput.value = '';
        activeTags.clear();
        tagList.querySelectorAll('.tag-chip').forEach(el => el.classList.remove('active'));
        applyFilters();
    }

    async function init() {
        try {
            const res = await fetch(DATA_URL, { cache: 'no-store' });
            if (!res.ok) throw new Error(`Failed to load ${DATA_URL}`);
            allPapers = await res.json();
            // Sort by date desc
            allPapers.sort((a, b) => (b.published || '').localeCompare(a.published || ''));

            buildTagChips(collectAllTags(allPapers));
            visiblePapers = allPapers.slice();
            renderList();
            renderCumulativeChart(allPapers);
        } catch (e) {
            console.error(e);
            resultsCount.textContent = 'Load failed';
            emptyState.style.display = 'block';
            emptyState.querySelector('h3').textContent = 'Failed to load papers';
            emptyState.querySelector('p').textContent = 'Please refresh the page later.';
        }

        // Bind events
        searchInput.addEventListener('input', applyFilters);
        resetBtn.addEventListener('click', resetFilters);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();


