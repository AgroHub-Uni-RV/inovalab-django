(() => {
  const body = document.body;
  const sidebar = document.querySelector('#sidebar');
  const mobileToggle = document.querySelector('.mobile-menu');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const profile = document.querySelector('.profile-menu');
  const mobile = window.matchMedia('(max-width: 760px)');
  const setMenu = (open, returnFocus = false) => {
    open = mobile.matches && open;
    body.classList.toggle('sidebar-open', open);
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
  mobileToggle.addEventListener('click', () => setMenu(!body.classList.contains('sidebar-open'), true));
  backdrop.addEventListener('click', () => setMenu(false, true));
  mobile.addEventListener('change', () => setMenu(false, true));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (profile.open) { profile.open = false; profile.querySelector('summary').focus(); }
      else if (body.classList.contains('sidebar-open')) setMenu(false, true);
    }
    if (event.key === 'Tab' && mobile.matches && body.classList.contains('sidebar-open')) {
      const controls = [...sidebar.querySelectorAll('a, button')];
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener('click', event => {
    if (profile.open && !profile.contains(event.target)) profile.open = false;
  });
  setMenu(false);
})();
