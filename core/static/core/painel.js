(() => {
  const body = document.body;
  const sidebar = document.querySelector('#sidebar');
  const toggle = document.querySelector('.sidebar-toggle');
  const mobileToggle = document.querySelector('.mobile-menu');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const profile = document.querySelector('.profile-menu');
  const mobile = window.matchMedia('(max-width: 760px)');
  const storageKey = 'inovalab.sidebar.expanded';
  let preferredOpen = false;
  try { preferredOpen = localStorage.getItem(storageKey) === 'true'; } catch { /* O menu funciona sem armazenamento disponível. */ }
  const setMenu = (open, returnFocus = false, persist = true) => {
    body.classList.toggle('sidebar-expanded', open);
    if (persist) {
      try { localStorage.setItem(storageKey, String(open)); } catch { /* Navegadores podem bloquear o armazenamento. */ }
    }
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Recolher menu' : 'Expandir menu');
    toggle.title = open ? 'Recolher menu' : 'Expandir menu';
    mobileToggle.setAttribute('aria-expanded', String(open));
    mobileToggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    backdrop.hidden = !(open && mobile.matches);
    if (mobile.matches) {
      sidebar.inert = !open;
      document.querySelector('.page-shell').inert = open;
      if (open) sidebar.querySelector('a').focus();
      else if (returnFocus) mobileToggle.focus();
    } else {
      sidebar.inert = false;
      document.querySelector('.page-shell').inert = false;
    }
  };
  toggle.addEventListener('click', () => setMenu(!body.classList.contains('sidebar-expanded'), true));
  mobileToggle.addEventListener('click', () => setMenu(!body.classList.contains('sidebar-expanded'), true));
  backdrop.addEventListener('click', () => setMenu(false, true));
  mobile.addEventListener('change', () => setMenu(body.classList.contains('sidebar-expanded'), false, false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (profile.open) { profile.open = false; profile.querySelector('summary').focus(); }
      else if (body.classList.contains('sidebar-expanded')) setMenu(false, true);
    }
    if (event.key === 'Tab' && mobile.matches && body.classList.contains('sidebar-expanded')) {
      const controls = [...sidebar.querySelectorAll('a, button')];
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener('click', event => {
    if (profile.open && !profile.contains(event.target)) profile.open = false;
  });
  setMenu(preferredOpen, false, false);
})();
