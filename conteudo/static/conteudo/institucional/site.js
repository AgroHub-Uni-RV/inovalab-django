(() => {
  const contrast = document.querySelector('[data-contrast]');
  let fontStep = 0;
  const apply = () => {
    document.documentElement.style.fontSize = `${16 + fontStep * 2}px`;
    contrast?.setAttribute('aria-pressed', String(document.body.classList.contains('high-contrast')));
  };
  try {
    document.body.classList.toggle('high-contrast', localStorage.getItem('inovalab.public.contrast') === 'true');
    fontStep = Math.max(-1, Math.min(3, Number(localStorage.getItem('inovalab.public.font')) || 0));
  } catch (_) { /* A página funciona mesmo sem armazenamento local. */ }
  apply();
  contrast?.addEventListener('click', () => {
    document.body.classList.toggle('high-contrast');
    try { localStorage.setItem('inovalab.public.contrast', document.body.classList.contains('high-contrast')); } catch (_) {}
    apply();
  });
  document.querySelectorAll('[data-font]').forEach(button => button.addEventListener('click', () => {
    fontStep = Math.max(-1, Math.min(3, fontStep + Number(button.dataset.font)));
    try { localStorage.setItem('inovalab.public.font', String(fontStep)); } catch (_) {}
    apply();
  }));
  document.querySelectorAll('[data-inova-carousel]').forEach(root => {
    const track = root.querySelector('[data-carousel-track]');
    if (!track) return;
    const scroll = direction => {
      const card = track.querySelector('li, article');
      const distance = (card?.getBoundingClientRect().width || 260) + 24;
      track.scrollBy({left: direction * distance, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
    };
    root.querySelector('[data-carousel-prev]')?.addEventListener('click', () => scroll(-1));
    root.querySelector('[data-carousel-next]')?.addEventListener('click', () => scroll(1));
  });
})();
