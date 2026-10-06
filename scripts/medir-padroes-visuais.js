(async () => {
  // Ler os arquivos atuais, como uma recarga completa, durante a depuração.
  await Promise.all([...document.querySelectorAll('link[rel=stylesheet]')].map(link => new Promise((resolve, reject) => {
    const url = new URL(link.href);
    url.searchParams.set('verificar-ui', Date.now().toString());
    link.onload = resolve;
    link.onerror = () => reject(new Error('Não foi possível carregar ' + url.pathname));
    link.href = url.href;
  })));
  await document.fonts.ready;
  const measure = selector => {
    const element = document.querySelector(selector);
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    const css = getComputedStyle(element);
    return {
      left: rect.left, width: rect.width, height: rect.height,
      font: css.fontFamily, size: css.fontSize, weight: css.fontWeight,
      radius: css.borderTopLeftRadius, gap: css.columnGap,
      padding: [css.paddingTop, css.paddingRight, css.paddingBottom, css.paddingLeft],
    };
  };
  const results = [];
  const check = mode => results.push({
    path: location.pathname, width: innerWidth, mode,
    status: performance.getEntriesByType('navigation')[0]?.responseStatus,
    overflow: document.documentElement.scrollWidth - innerWidth,
    brokenImages: [...document.images].filter(image => image.complete && !image.naturalWidth).length,
    clippedDashboardControls: [...document.querySelectorAll('.dashboard .card-heading, .dashboard .tabs, .dashboard .calendar-legend')]
      .filter(element => element.scrollWidth > element.clientWidth + 1)
      .map(element => element.className),
    clippedActiveTabs: [...document.querySelectorAll('.module-tabs a[aria-current=page]')].filter(link => {
      const nav = link.closest('.module-tabs');
      const clipBottom = nav.getBoundingClientRect().bottom - parseFloat(getComputedStyle(nav).borderBottomWidth);
      const rect = link.getBoundingClientRect();
      const lineTop = rect.bottom - parseFloat(getComputedStyle(link).borderBottomWidth);
      return Math.min(rect.bottom, clipBottom) - lineTop < 1;
    }).map(link => link.textContent.trim()),
    fontLoaded: [...document.fonts].some(font => font.family === 'Montserrat' && font.status === 'loaded'),
    body: measure('body'), container: measure('.module-page, .dashboard'),
    header: measure('.topbar-inner'), footer: measure('.footer-inner'),
    heading: measure('.page-heading h1, .sheet-content h1, .login-card h2'),
    statistics: measure('.statistics'), card: measure('.stat-card'),
    statTitle: measure('.stat-copy h2'), statNumber: measure('.stat-copy strong'),
    statIcon: measure('.stat-icon'),
    clippedStatLabels: [...document.querySelectorAll('.stat-copy h2')].filter(label => {
      const range = document.createRange();
      range.selectNodeContents(label);
      return [...range.getClientRects()].some(rect => rect.right > label.getBoundingClientRect().right + 1);
    }).map(label => label.textContent.trim()),
    taskNumberGaps: [...document.querySelectorAll('.task-row')].map(row => {
      const number = row.querySelector('.task-number');
      const range = document.createRange();
      range.selectNodeContents(number);
      return {
        expected: parseFloat(getComputedStyle(row).columnGap),
        actual: row.querySelector('.task-copy').getBoundingClientRect().left - range.getBoundingClientRect().right,
      };
    }),
    filter: measure('.filter-bar'),
    field: measure('main input:not([type=hidden]):not([type=checkbox]):not([type=radio]), main select, main textarea'),
    button: measure('.primary-button, .sheet-actions button[type=submit], .login-card button[type=submit]'),
    table: measure('.table-wrapper'), sheet: measure('.detail-sheet'),
  });
  check('collapsed');
  if (innerWidth > 760 && document.querySelector('.sidebar-toggle')) {
    document.querySelector('.sidebar-toggle').click();
    await new Promise(resolve => setTimeout(resolve, 200));
    check('expanded');
  }
  return results;
})()
