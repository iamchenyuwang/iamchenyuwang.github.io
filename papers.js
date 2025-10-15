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

    // Pagination
    let currentPage = 1;
    const PAGE_SIZE = 20;

    // Elements
    const searchInput = document.getElementById('paper-search');
    const tagList = document.getElementById('tag-list');
    const resetBtn = document.getElementById('reset-filters');
    const resultsCount = document.getElementById('results-count');
    const papersList = document.getElementById('papers-list');
    const emptyState = document.getElementById('empty-state');
    const chartCanvas = document.getElementById('papers-cumulative-chart');
    const pagWrap = document.getElementById('papers-pagination');
    const pagPrev = document.getElementById('page-prev');
    const pagNext = document.getElementById('page-next');
    const pagNumbers = document.getElementById('page-numbers');

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
        // Fill header badges
        const statTotal = document.getElementById('stat-total');
        const statGrowth = document.getElementById('stat-growth');
        const statSince = document.getElementById('stat-since');
        if (statTotal && data.length) statTotal.textContent = data[data.length - 1];
        if (statGrowth && data.length) {
            const growth = data.length > 6 ? (data[data.length - 1] - data[data.length - 7]) : data[data.length - 1];
            statGrowth.textContent = growth;
        }
        if (statSince && labels.length) {
            const [y, m] = labels[0].split('-').map(Number);
            const d = new Date(y, m - 1, 1);
            statSince.textContent = d.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
        }
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
        currentPage = 1;
        renderList();
        renderPagination();
    }

    function renderList() {
        papersList.innerHTML = '';
        const count = visiblePapers.length;
        const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
        const page = Math.min(currentPage, totalPages);
        const startIdx = (page - 1) * PAGE_SIZE;
        const endIdx = Math.min(startIdx + PAGE_SIZE, count);
        resultsCount.textContent = `${count} result${count === 1 ? '' : 's'}${count ? ` · showing ${startIdx + 1}-${endIdx}` : ''}`;
        emptyState.style.display = count ? 'none' : 'block';

        visiblePapers.slice(startIdx, endIdx).forEach((p) => {
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

    function makePageButton(num, isActive = false) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `page-number${isActive ? ' active' : ''}`;
        btn.textContent = String(num);
        btn.addEventListener('click', () => {
            if (currentPage !== num) {
                currentPage = num;
                renderList();
                renderPagination();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        return btn;
    }

    function renderPagination() {
        if (!pagWrap) return;
        const count = visiblePapers.length;
        const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
        if (totalPages <= 1) {
            pagWrap.style.display = 'none';
            return;
        }
        pagWrap.style.display = 'flex';

        // Prev/Next state
        if (pagPrev) {
            pagPrev.disabled = currentPage <= 1;
            pagPrev.onclick = () => { if (currentPage > 1) { currentPage -= 1; renderList(); renderPagination(); window.scrollTo({ top: 0, behavior: 'smooth' }); } };
        }
        if (pagNext) {
            pagNext.disabled = currentPage >= totalPages;
            pagNext.onclick = () => { if (currentPage < totalPages) { currentPage += 1; renderList(); renderPagination(); window.scrollTo({ top: 0, behavior: 'smooth' }); } };
        }

        // Page numbers window (max 7 numbers)
        if (pagNumbers) {
            pagNumbers.innerHTML = '';
            const windowSize = 7;
            let start = Math.max(1, currentPage - Math.floor(windowSize / 2));
            let end = start + windowSize - 1;
            if (end > totalPages) {
                end = totalPages;
                start = Math.max(1, end - windowSize + 1);
            }

            if (start > 1) {
                pagNumbers.appendChild(makePageButton(1, currentPage === 1));
                if (start > 2) {
                    const ell = document.createElement('span');
                    ell.className = 'page-ellipsis';
                    ell.textContent = '…';
                    pagNumbers.appendChild(ell);
                }
            }

            for (let n = start; n <= end; n++) {
                pagNumbers.appendChild(makePageButton(n, n === currentPage));
            }

            if (end < totalPages) {
                if (end < totalPages - 1) {
                    const ell = document.createElement('span');
                    ell.className = 'page-ellipsis';
                    ell.textContent = '…';
                    pagNumbers.appendChild(ell);
                }
                pagNumbers.appendChild(makePageButton(totalPages, currentPage === totalPages));
            }
        }
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
            renderPagination();
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


