import { render } from '@testing-library/react';
import LandingPage from '../../src/components/LandingPage';

jest.mock('../../src/components/LegalModal', () => ({ __esModule: true, default: () => null }));

const AGENT_PAGES = [
  'coding-practice', 'aptitude-trainer', 'communication-coach', 'mock-interview',
  'resume-builder', 'job-agent', 'capstone-project', 'ai-certification',
];

// Google only follows <a href>, so the rendered home page must link to every public agent page.
test('the landing page links to every agent page and the public sections with real anchors', () => {
  const { container } = render(<LandingPage onLogin={jest.fn()} />);
  const hrefs = Array.from(container.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'));
  for (const slug of AGENT_PAGES) expect(hrefs).toContain(`/agents/${slug}/`);
  for (const path of ['/agents/', '/pricing/', '/for-colleges/', '/faq/']) expect(hrefs).toContain(path);
});

test('section links still scroll on the page instead of leaving it', () => {
  const scrollIntoView = jest.fn();
  window.HTMLElement.prototype.scrollIntoView = scrollIntoView;
  const { container } = render(<LandingPage onLogin={jest.fn()} />);
  const link = container.querySelector('a[href="/pricing/"]') as HTMLAnchorElement;
  const notPrevented = link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  expect(notPrevented).toBe(false);
});
