(() => {
  const failures = [];
  if (document.documentElement.scrollWidth > innerWidth + 1) failures.push('page overflow');
  for (const element of document.querySelectorAll('.card-heading, .tabs, .month-card')) {
    if (element.scrollWidth > element.clientWidth + 1) failures.push(element.className + ': content overflow');
  }
  for (const row of document.querySelectorAll('.weekdays')) {
    const cells = [...row.children].map(element => element.getBoundingClientRect());
    for (let index = 1; index < cells.length; index++) {
      if (cells[index - 1].right > cells[index].left + 1) failures.push('weekday collision');
    }
  }
  for (const grid of document.querySelectorAll('.month-days')) {
    const days = [...grid.children];
    for (let index = 1; index < days.length; index++) {
      const first = days[index - 1].getBoundingClientRect(), second = days[index].getBoundingClientRect();
      if (Math.abs(first.y - second.y) < 1 && first.right > second.left + 1) failures.push('calendar day collision');
    }
  }
  if (failures.length) throw new Error(JSON.stringify({viewport: innerWidth, expanded:document.body.classList.contains('sidebar-expanded'), failures}));
  return {passed:true, viewport:innerWidth, expanded:document.body.classList.contains('sidebar-expanded')};
})()
