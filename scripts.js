const navMenu = document.querySelector('[data-nav-menu]');
const navBackdrop = document.querySelector('[data-nav-backdrop]');
const navToggles = document.querySelectorAll('.nav-toggle');

const setNavState = (isOpen) => {
  if (!navMenu) return;
  navMenu.setAttribute('data-open', isOpen);
  navBackdrop?.setAttribute('data-visible', isOpen);
  navToggles.forEach((btn) => btn.setAttribute('aria-expanded', String(isOpen)));
  document.body.classList.toggle('nav-open', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
};

navToggles.forEach((button) => {
  const shouldOpen = !button.classList.contains('close');
  button.addEventListener('click', () => setNavState(shouldOpen));
});

navBackdrop?.addEventListener('click', () => setNavState(false));
navMenu?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setNavState(false)));
window.addEventListener('keyup', (event) => {
  if (event.key === 'Escape') {
    setNavState(false);
  }
});
window.addEventListener('resize', () => {
  if (window.innerWidth > 960) {
    setNavState(false);
  }
});

const faqItems = document.querySelectorAll('[data-faq]');
faqItems.forEach((item) => {
  const button = item.querySelector('button');
  const answer = item.querySelector('p');
  if (!button || !answer) return;

  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
    answer.hidden = expanded;
    item.classList.toggle('is-open', !expanded);
  });
});

const form = document.getElementById('contact-form');
const feedback = document.getElementById('form-feedback');

const showFeedback = (message, type) => {
  if (!feedback) return;
  feedback.textContent = message;
  feedback.classList.remove('success', 'error');
  if (type) feedback.classList.add(type);
};

const clearFeedback = () => {
  if (!feedback) return;
  feedback.textContent = '';
  feedback.classList.remove('success', 'error');
};

form?.addEventListener('submit', (event) => {
  event.preventDefault();
  const requiredFields = Array.from(form.querySelectorAll('[required]'));
  const missing = requiredFields.filter((field) => !field.value.trim());

  if (missing.length) {
    showFeedback('Please complete all required fields before sending.', 'error');
    return;
  }

  showFeedback('Request received! Our team will reply within one business day.', 'success');
  form.reset();
  setTimeout(clearFeedback, 6000);
});

setNavState(false);
