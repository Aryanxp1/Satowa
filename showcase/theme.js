(() => {
  const toggle = document.getElementById('theme-toggle');
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme;
    toggle.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
    toggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    localStorage.setItem('setowa-theme', theme);
  };
  apply((localStorage.getItem('setowa-theme') || localStorage.getItem('lex-theme')) === 'dark' ? 'dark' : 'light');
  toggle.addEventListener('click', () => apply(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
})();
