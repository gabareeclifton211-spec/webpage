document.addEventListener('DOMContentLoaded', function () {
  const navToggle = document.getElementById('nav-toggle') || document.querySelector('.nav-toggle');
  const navMenu = document.getElementById('nav-menu') || document.querySelector('.navlinks') || document.querySelector('nav');
  if (!navToggle || !navMenu) return;

  const setAria = (val) => navToggle.setAttribute('aria-expanded', String(val));

  navToggle.addEventListener('click', () => {
    // Support both patterns: body.nav-open (legacy templates) and navMenu.open (newer pattern)
    navMenu.classList.toggle('open');
    document.body.classList.toggle('nav-open');
    setAria(navMenu.classList.contains('open') || document.body.classList.contains('nav-open'));
  });

  // Close menu when clicking outside
  document.addEventListener('click', (e) => {
    if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
      navMenu.classList.remove('open');
      document.body.classList.remove('nav-open');
      setAria(false);
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      navMenu.classList.remove('open');
      document.body.classList.remove('nav-open');
      setAria(false);
    }
  });

  // Close when a nav link is clicked (useful for single-page anchors)
  navMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    navMenu.classList.remove('open');
    document.body.classList.remove('nav-open');
    setAria(false);
  }));
});

