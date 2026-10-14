(() => {
  const key = 'ridehub-theme';
  const themes = ['light', 'dark', 'blue'];
  const isPortal = document.body.classList.contains('portal-page');
  const isWorkspace = document.body.classList.contains('dashboard-page');
  let theme = localStorage.getItem(key);
  if (!themes.includes(theme)) theme = localStorage.getItem('ridehub-user-theme');
  if (!themes.includes(theme)) theme = (isPortal || isWorkspace) ? 'dark' : 'light';

  function applyTheme(nextTheme, persist = true) {
    if (!themes.includes(nextTheme)) return;
    theme = nextTheme;
    document.body.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === 'dark' ? 'dark' : 'light';
    if (persist) {
      localStorage.setItem(key, theme);
      localStorage.setItem('ridehub-user-theme', theme);
    }
    document.querySelectorAll('[data-theme-choice]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === theme));
    });
  }

  applyTheme(theme, false);
  document.querySelectorAll('[data-theme-choice]').forEach(button => {
    button.addEventListener('click', () => {
      applyTheme(button.dataset.themeChoice);
      button.closest('details')?.removeAttribute('open');
    });
  });

  const infoDialogs = {
    about: document.querySelector('#about-dialog'),
    contact: document.querySelector('#contact-dialog'),
    terms: document.querySelector('#terms-dialog'),
    privacy: document.querySelector('#privacy-dialog'),
    faqs: document.querySelector('#faqs-dialog'),
  };
  document.querySelectorAll('[data-open-info]').forEach(link => {
    link.addEventListener('click', event => {
      const dialog = infoDialogs[link.dataset.openInfo];
      if (!dialog) return;
      event.preventDefault();
      dialog.showModal();
    });
  });
  document.querySelectorAll('[data-close-info]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });
  Object.values(infoDialogs).forEach(dialog => dialog?.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  }));

  const progress = document.querySelector('#scroll-progress-fill');
  if (progress) {
    let progressFrame = 0;
    const updateProgress = () => {
      if (progressFrame) return;
      progressFrame = requestAnimationFrame(() => {
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        progress.style.transform = `scaleX(${scrollable > 0 ? window.scrollY / scrollable : 0})`;
        progressFrame = 0;
      });
    };
    window.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress, { passive: true });
    updateProgress();
  }

  function removeUnsupportedOptions(root = document) {
    root.querySelectorAll?.('option[value="cycle"]').forEach(option => option.remove());
    const picker = root.querySelector?.('#vehicle-type');
    if (picker?.value === 'cycle') picker.value = 'car';
  }
  removeUnsupportedOptions();
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) removeUnsupportedOptions(node);
  }))).observe(document.body, { childList: true, subtree: true });

  const heroVisual = document.querySelector('.hero-visual');
  if (heroVisual && !matchMedia('(prefers-reduced-motion: reduce)').matches && matchMedia('(pointer: fine)').matches) {
    let motionFrame = 0;
    heroVisual.addEventListener('pointermove', event => {
      const bounds = heroVisual.getBoundingClientRect();
      const x = ((event.clientX - bounds.left) / bounds.width - .5) * 2;
      const y = ((event.clientY - bounds.top) / bounds.height - .5) * 2;
      if (motionFrame) cancelAnimationFrame(motionFrame);
      motionFrame = requestAnimationFrame(() => {
        heroVisual.style.setProperty('--parallax-x', `${(x * 8).toFixed(2)}px`);
        heroVisual.style.setProperty('--parallax-y', `${(y * 8).toFixed(2)}px`);
        heroVisual.style.setProperty('--parallax-small-x', `${(x * -4).toFixed(2)}px`);
        heroVisual.style.setProperty('--parallax-small-y', `${(y * -5).toFixed(2)}px`);
      });
    });
    heroVisual.addEventListener('pointerleave', () => {
      heroVisual.style.setProperty('--parallax-x', '0px');
      heroVisual.style.setProperty('--parallax-y', '0px');
      heroVisual.style.setProperty('--parallax-small-x', '0px');
      heroVisual.style.setProperty('--parallax-small-y', '0px');
    });
  }

  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const revealSelector = [
      '.hero-content', '.hero-visual', '.search-card', '.section-heading', '.category-card',
      '.stats-bar', '.step', '.vehicle-card', '.final-cta-inner', '.portal-content > *',
      '.workspace-hero', '.stats-grid > *', '.panel-card', '.card', '.results-heading',
      '.vehicle-result-card', '.shop-result-card', '.shop-listing-card',
    ].join(',');
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('rh-visible');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.1, rootMargin: '0px 0px -24px 0px' });
    const observeRevealItems = root => {
      if (root.nodeType === Node.ELEMENT_NODE && root.matches(revealSelector) && !root.classList.contains('rh-reveal')) {
        root.classList.add('rh-reveal');
        observer.observe(root);
      }
      root.querySelectorAll?.(revealSelector).forEach(item => {
        if (item.classList.contains('rh-reveal')) return;
        item.classList.add('rh-reveal');
        observer.observe(item);
      });
    };
    observeRevealItems(document);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE) observeRevealItems(node);
    }))).observe(document.body, { childList: true, subtree: true });
  }
})();
