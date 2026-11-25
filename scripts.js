const navMenu = document.querySelector('[data-nav-menu]');
const navBackdrop = document.querySelector('[data-nav-backdrop]');
const navToggles = document.querySelectorAll('.nav-toggle');

let navReturnFocus = null;
const navBackground = document.querySelectorAll('.nav-wrapper, main, .site-footer, .skip-link');

const setNavState = (isOpen) => {
  if (!navMenu) return;
  const wasOpen = navMenu.getAttribute('data-open') === 'true';
  if (isOpen && !wasOpen) navReturnFocus = document.activeElement;
  navMenu.hidden = !isOpen;
  navMenu.inert = !isOpen;
  navBackground.forEach((element) => { element.inert = isOpen; });
  navMenu.setAttribute('data-open', String(isOpen));
  navBackdrop?.setAttribute('data-visible', isOpen);
  navToggles.forEach((btn) => btn.setAttribute('aria-expanded', String(isOpen)));
  document.body.classList.toggle('nav-open', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
  if (isOpen && !wasOpen) navMenu.querySelector('.close')?.focus();
  if (!isOpen && wasOpen && navReturnFocus?.getClientRects().length) navReturnFocus.focus();
};

navToggles.forEach((button) => {
  const shouldOpen = !button.classList.contains('close');
  button.addEventListener('click', () => setNavState(shouldOpen));
});

navBackdrop?.addEventListener('click', () => setNavState(false));
navMenu?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setNavState(false)));
window.addEventListener('keydown', (event) => {
  if (navMenu?.getAttribute('data-open') !== 'true') return;
  if (event.key === 'Escape') { event.preventDefault(); setNavState(false); }
  if (event.key === 'Tab') {
    const items = Array.from(navMenu.querySelectorAll('a[href], button:not([disabled])'));
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
window.addEventListener('resize', () => {
  if (window.innerWidth > 1200) {
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
  feedback.textContent = window.HomeLanguage?.feedback(message) ?? message;
  feedback.classList.remove('success', 'error');
  if (type) feedback.classList.add(type);
};

let isSubmitting = false;
form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (isSubmitting) return;
  form.querySelectorAll('[required]').forEach((field) => { field.value = field.value.trim(); });
  if (!form.reportValidity()) {
    showFeedback('Please complete all required fields with valid details.', 'error');
    return;
  }
  const endpoint = form.dataset.formspreeEndpoint;
  if (!endpoint || !/^https:\/\/formspree\.io\/f\/[a-zA-Z0-9]+$/.test(endpoint)) {
    showFeedback('The contact form is temporarily unavailable. Please try again later.', 'error');
    return;
  }
  const button = form.querySelector('button[type="submit"]');
  const data = new FormData(form);
  isSubmitting = true;
  button.disabled = true;
  button.textContent = window.HomeLanguage?.translate('Sending…') ?? 'Sending…';
  form.setAttribute('aria-busy', 'true');
  showFeedback('Sending your request…');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(endpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) throw new Error('Submission rejected');
    showFeedback('Your request was submitted successfully. Thank you for contacting us!', 'success');
    form.reset();
  } catch {
    showFeedback('We could not confirm your submission. Your details are still here; please try again later.', 'error');
  } finally {
    clearTimeout(timeout);
    isSubmitting = false;
    button.disabled = false;
    button.textContent = window.HomeLanguage?.translate('Send Request') ?? 'Send Request';
    form.removeAttribute('aria-busy');
  }
});

setNavState(false);
