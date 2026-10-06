(async () => {
  await document.fonts.ready;
  const sidebar = document.querySelector('#sidebar');
  const bounds = sidebar?.getBoundingClientRect();
  return {
    path: location.pathname,
    status: performance.getEntriesByType('navigation')[0]?.responseStatus,
    expanded: document.body.classList.contains('sidebar-expanded'),
    cached: localStorage.getItem('inovalab.sidebar.expanded'),
    sidebar: !!sidebar,
    header: !!document.querySelector('.topbar'),
    footer: !!document.querySelector('.footer'),
    centers: [...document.querySelectorAll('.sidebar .nav-item .icon')].map(icon => {
      const rect = icon.getBoundingClientRect();
      return rect.x + rect.width / 2 - (bounds.x + bounds.width / 2);
    }),
    legend: [...document.querySelectorAll('.calendar-legend li')].map(item => ({
      label: item.textContent.trim(),
      color: getComputedStyle(item.querySelector('.swatch')).backgroundColor,
    })),
    logos: [...document.querySelectorAll('img[alt="InovaLab"]')].map(img => ({
      loaded: img.complete && img.naturalWidth > 0,
      width: img.getBoundingClientRect().width,
    })),
    overflow: document.documentElement.scrollWidth - innerWidth,
  };
})();
