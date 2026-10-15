(() => {
  const selectors = ['.auth-intro > *','.auth-panel > *','.role-card','.portal-content > *','.workspace-content > *','.metric-card','.panel-card'].join(',');
  const items = [...document.querySelectorAll(selectors)].filter((item, index, all) => all.indexOf(item) === index);
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => entries.forEach(({ target, isIntersecting }) => {
      if (isIntersecting) { target.classList.add('is-visible'); observer.unobserve(target); }
    }), { threshold: .08 });
    items.forEach((item, index) => { item.classList.add('rh-reveal'); item.style.transitionDelay = `${Math.min(index * 38, 260)}ms`; observer.observe(item); });
  } else items.forEach((item) => item.classList.add('is-visible'));
})();
