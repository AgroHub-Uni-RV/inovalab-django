(() => {
  let dispose;
  window.initializeTaskTimer = () => {
    dispose?.();
    const timer = document.querySelector('[data-task-timer]');
    if (!timer) return;
    const initial = Number(timer.dataset.seconds);
    const started = performance.now();
    const running = timer.dataset.running === 'true';
    const render = () => {
      const total = initial + (running ? Math.floor((performance.now() - started) / 1000) : 0);
      timer.textContent = [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60]
        .map(value => String(value).padStart(2, '0')).join(':');
    };
    let interval;
    const resume = () => {
      clearInterval(interval);
      render();
      if (running && !document.hidden) interval = setInterval(render, 1000);
    };
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('pageshow', resume);
    const stop = () => clearInterval(interval);
    window.addEventListener('pagehide', stop);
    dispose = () => {
      stop();
      document.removeEventListener('visibilitychange', resume);
      window.removeEventListener('pageshow', resume);
      window.removeEventListener('pagehide', stop);
    };
    resume();
  };
  window.initializeTaskTimer();
  document.addEventListener('inovalab:content-updated', () => window.initializeTaskTimer());
})();
