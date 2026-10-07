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
  const calendar = document.querySelector('[data-events-calendar]');
  const payloadNode = document.getElementById('inova-events-calendar-payload');
  if (calendar && payloadNode) {
    const payload = JSON.parse(payloadNode.textContent);
    const dates = new Set(payload.eventDates);
    const cards = [...calendar.querySelectorAll('[data-event-card]')];
    const grid = calendar.querySelector('[data-events-grid]');
    const label = calendar.querySelector('[data-events-month]');
    const prev = calendar.querySelector('[data-events-prev]');
    const next = calendar.querySelector('[data-events-next]');
    const empty = calendar.querySelector('[data-events-empty]');
    let year = payload.initialYear, month = payload.initialMonth, selected = '', page = 0;
    const iso = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
    const renderCards = () => {
      const filtered = cards.filter(card => !selected || card.dataset.eventDate === selected);
      const visible = new Set(filtered.slice(page * 2, page * 2 + 2));
      cards.forEach(card => { card.hidden = !visible.has(card); });
      prev.disabled = page === 0;
      next.disabled = (page + 1) * 2 >= filtered.length;
      if (empty) empty.hidden = filtered.length > 0;
    };
    const renderMonth = () => {
      const monthName = payload.monthNames[month - 1];
      label.textContent = monthName;
      const yearLabel = document.createElement('span');
      yearLabel.className = 'institutional-visually-hidden';
      yearLabel.textContent = ` ${year}`;
      label.append(yearLabel);
      grid.setAttribute('aria-label', `Calendário de ${monthName} de ${year}`);
      const first = new Date(year, month - 1, 1, 12);
      const fragment = document.createDocumentFragment();
      for (let index = 0; index < 42; index++) {
        const day = new Date(year, month - 1, index + 1 - first.getDay(), 12);
        const date = iso(day), outside = day.getMonth() !== month - 1;
        const hasEvent = dates.has(date);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'inova-events-calendar__day focus-ring';
        button.classList.toggle('is-outside', outside);
        button.classList.toggle('is-event', hasEvent);
        button.classList.toggle('is-selected', date === selected);
        button.disabled = outside || !hasEvent;
        button.dataset.eventDate = date;
        button.textContent = day.getDate();
        button.setAttribute('aria-pressed', String(date === selected));
        button.setAttribute('aria-label', `${day.getDate()} de ${payload.monthNames[day.getMonth()]} de ${day.getFullYear()}${hasEvent ? ' — eventos disponíveis' : ''}`);
        fragment.append(button);
      }
      grid.replaceChildren(fragment);
    };
    grid.addEventListener('click', event => {
      const button = event.target.closest('button[data-event-date]');
      if (!button || button.disabled) return;
      selected = selected === button.dataset.eventDate ? '' : button.dataset.eventDate;
      page = 0;
      // Preservar o foco no dia acionado durante a seleção.
      grid.querySelectorAll('button').forEach(day => {
        day.classList.toggle('is-selected', day.dataset.eventDate === selected);
        day.setAttribute('aria-pressed', String(day.dataset.eventDate === selected));
      });
      renderCards();
    });
    calendar.querySelectorAll('[data-month-step]').forEach(button => {
      button.disabled = false;
      button.addEventListener('click', () => {
        const target = new Date(year, month - 1 + Number(button.dataset.monthStep), 1, 12);
        year = target.getFullYear();
        month = target.getMonth() + 1;
        selected = '';
        page = 0;
        renderMonth();
        renderCards();
      });
    });
    prev.addEventListener('click', () => { if (!prev.disabled) { page--; renderCards(); } });
    next.addEventListener('click', () => { if (!next.disabled) { page++; renderCards(); } });
    renderMonth();
    renderCards();
  }
})();
