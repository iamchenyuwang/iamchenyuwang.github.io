(function () {
    var menuButton = document.querySelector('.menu-toggle');
    var navigation = document.querySelector('.site-nav');

    if (menuButton && navigation) {
        menuButton.addEventListener('click', function () {
            var isOpen = menuButton.getAttribute('aria-expanded') === 'true';
            menuButton.setAttribute('aria-expanded', String(!isOpen));
            navigation.classList.toggle('open', !isOpen);
        });

        navigation.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                menuButton.setAttribute('aria-expanded', 'false');
                navigation.classList.remove('open');
            });
        });
    }

    var navLinks = Array.from(document.querySelectorAll('.site-nav a'));
    var sections = navLinks
        .map(function (link) { return document.querySelector(link.getAttribute('href')); })
        .filter(Boolean);

    if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                navLinks.forEach(function (link) {
                    link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
                });
            });
        }, { rootMargin: '-25% 0px -65% 0px', threshold: 0 });

        sections.forEach(function (section) { observer.observe(section); });
    }

    var year = document.getElementById('current-year');
    if (year) year.textContent = String(new Date().getFullYear());
})();
