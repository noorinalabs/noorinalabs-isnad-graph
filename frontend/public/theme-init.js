// Set data-theme before first paint to prevent flash of wrong theme
(function () {
  var stored = localStorage.getItem('isnad-graph-theme');
  var theme =
    stored === 'light' || stored === 'dark'
      ? stored
      : stored === 'system' || !stored
        ? window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
        : 'light';
  document.documentElement.setAttribute('data-theme', theme);
})();
