import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import fs from 'fs';
import path from 'path';
import LessonBody from '../../src/components/learn/LessonBody';
import LearningHub from '../../src/components/learn/LearningHub';
import { parseBlocks, parseQa, safeHref, outlineOf } from '../../src/lib/learnMarkdown';
import type * as LearnApiTypes from '../../src/lib/learnApi';
import * as learnApi from '../../src/lib/learnApi';

// The real module reads import.meta.env, which Jest cannot parse, so it is replaced whole.
jest.mock('../../src/lib/learnApi', () => ({
  LearnApiError: class LearnApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
  fetchCatalog: jest.fn(), fetchOutline: jest.fn(), fetchLesson: jest.fn(), searchLessons: jest.fn(), setLessonDone: jest.fn(),
}));
const api = jest.mocked(learnApi);

const CONTENT = path.resolve(__dirname, '../../agents/orchestrator/app/learn/content');
const lessonText = (rel: string) => fs.readFileSync(path.join(CONTENT, rel), 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');

describe('lesson markdown', () => {
  test('headings, paragraphs, lists, code and tables become blocks', () => {
    const blocks = parseBlocks('## Title\n\nHello **bold** `code`.\n\n- a\n- b\n\n1. one\n2. two\n\n```python\nprint(1)\n```\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n');
    expect(blocks.map((b) => b.t)).toEqual(['h', 'p', 'list', 'list', 'code', 'table']);
    expect(blocks[2]).toMatchObject({ t: 'list', ordered: false, items: ['a', 'b'] });
    expect(blocks[3]).toMatchObject({ t: 'list', ordered: true });
    expect(blocks[4]).toMatchObject({ t: 'code', lang: 'python', code: 'print(1)' });
    expect(blocks[5]).toMatchObject({ t: 'table', head: ['A', 'B'], rows: [['1', '2']] });
  });

  test('callouts hold blocks, and a fence inside is not mistaken for the end', () => {
    const blocks = parseBlocks(':::example Find it\nText\n\n```js\nconst a = 1;\n```\n:::\n\nAfter');
    expect(blocks[0]).toMatchObject({ t: 'callout', kind: 'example', arg: 'Find it' });
    expect((blocks[0] as { blocks: { t: string }[] }).blocks.map((b) => b.t)).toEqual(['p', 'code']);
    expect(blocks[1]).toMatchObject({ t: 'p', text: 'After' });
  });

  test('a pipe inside inline code does not split a table cell', () => {
    const [table] = parseBlocks('| Op | Meaning |\n| --- | --- |\n| `a | b` | or |\n');
    expect(table).toMatchObject({ t: 'table', rows: [['`a | b`', 'or']] });
  });

  test('heading ids are unique and form the "on this page" list', () => {
    const blocks = parseBlocks('## Same\n\ntext\n\n## Same\n\n### Skip me\n');
    expect(outlineOf(blocks).map((h) => h.id)).toEqual(['same', 'same-2']);
  });

  test('only web and in-site links are allowed', () => {
    expect(safeHref('https://x.com/a')).toBe('https://x.com/a');
    expect(safeHref('/agents/')).toBe('/agents/');
    expect(safeHref('javascript:alert(1)')).toBeNull();
    expect(safeHref('//evil.example')).toBeNull();
    expect(safeHref('data:text/html,x')).toBeNull();
  });

  test('markup in a lesson is shown as text, never run', () => {
    const { container } = render(<LessonBody kind="article" body={'A <script>alert(1)</script> and <img src=x onerror=alert(1)>'} />);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toContain('<script>alert(1)</script>');
  });

  test('a javascript: link renders as plain text, not an anchor', () => {
    const { container } = render(<LessonBody kind="article" body={'[click](javascript:alert(1))'} />);
    expect(container.querySelector('a')).toBeNull();
    expect(container.textContent).toContain('click');
  });

  test('code boxes colour keywords and strings, and output is a separate box', () => {
    const { container } = render(<LessonBody kind="article" body={'```python\nprint("hi")  # note\nif x:\n    pass\n```\n\n```output\nhi\n```\n'} />);
    expect(container.querySelector('.tk-kw')?.textContent).toBe('if');
    expect(container.querySelector('.tk-st')?.textContent).toBe('"hi"');
    expect(container.querySelector('.tk-cm')?.textContent).toBe('# note');
    expect(container.querySelector('.lh-code.is-output')).not.toBeNull();
  });

  test('every real lesson file parses and keeps its code and callouts balanced', () => {
    const files: string[] = [];
    const walk = (dir: string) => fs.readdirSync(dir, { withFileTypes: true }).forEach((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : e.name.endsWith('.md') && files.push(path.join(dir, e.name))));
    walk(CONTENT);
    expect(files.length).toBeGreaterThanOrEqual(50);
    files.forEach((file, index) => {
      const text = fs.readFileSync(file, 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
      expect(parseBlocks(text).length).toBeGreaterThan(2);       // every lesson is parsed
      if (index % 8 !== 0) return;                                 // but only a sample is rendered, to keep the test fast
      const rendered = render(<LessonBody kind="article" body={text} />);
      expect(rendered.container.textContent?.length ?? 0).toBeGreaterThan(200);
      rendered.unmount();
    });
  });
});

describe('interview question lessons', () => {
  const body = lessonText('interview-python/questions/python-basics-qa.md');

  test('each "### Q [level]" starts a question and trailing callouts become the footer', () => {
    const qa = parseQa(parseBlocks(body));
    expect(qa.items.length).toBeGreaterThanOrEqual(8);
    expect(qa.items[0]).toMatchObject({ level: 'easy', question: 'What are the key features of Python?' });
    expect(qa.footer.some((b) => b.t === 'callout')).toBe(true);
  });

  test('the first answer is open, the filter narrows the list, and a question toggles', () => {
    render(<LessonBody kind="qa" body={body} />);
    const questions = screen.getAllByRole('button', { expanded: true });
    expect(questions.length).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: 'Medium' }));
    expect(screen.queryByText('What are the key features of Python?')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /^All/ }));
    const second = screen.getByRole('button', { name: /Is Python compiled or interpreted/ });
    expect(second).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(second);
    expect(second).toHaveAttribute('aria-expanded', 'true');
  });
});

describe('learning hub screens', () => {
  const course = (over: object = {}) => ({
    slug: 'python', title: 'Python', track: 'technical', level: 'Beginner', summary: 'Learn it', icon: 'Py', color: '#3776ab', status: 'live' as const,
    kind: 'tutorial' as const, lessons: 2, chapters: 1, minutes: 5, completed: 0, ...over,
  });
  const catalog = (access: { unlocked: boolean; reason: LearnApiTypes.AccessReason } = { unlocked: true, reason: 'coins' }) => ({
    access,
    tracks: [
      { id: 'technical', title: 'Technical', blurb: 'Code', courses: [course(), course({ slug: 'react', title: 'React', status: 'soon', lessons: 0, minutes: 0 })] },
      { id: 'aptitude', title: 'Aptitude', blurb: 'Numbers', courses: [] },
    ],
    paths: [{ id: 'p', title: 'Full Stack', summary: 'All of it', courses: [course()] }],
  });
  const outline = () => ({
    ...course(), chapters: [{ id: 'start', title: 'Getting started', summary: '', lessons: [
      { id: 'one', title: 'First lesson', minutes: 2, kind: 'article', done: false },
      { id: 'two', title: 'Second lesson', minutes: 3, kind: 'article', done: false },
    ] }],
    outcomes: ['Write programs'],
  });
  const lesson = (id: string, number: number) => ({
    course: { slug: 'python', title: 'Python', track: 'technical', color: '#3776ab' },
    lesson: { id, chapter: 'start', chapter_title: 'Getting started', title: id === 'one' ? 'First lesson' : 'Second lesson', summary: 'S', takeaways: ['Learn A'],
      kind: 'article', minutes: 2, body: '## Part one\n\nHello\n\n## Part two\n\nWorld\n', done: false, number, of: 2 },
    previous: number === 2 ? { id: 'one', title: 'First lesson', chapter_title: 'Getting started' } : null,
    next: number === 1 ? { id: 'two', title: 'Second lesson', chapter_title: 'Getting started' } : null,
  });

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
    api.fetchCatalog.mockReset().mockResolvedValue(catalog());
    api.fetchOutline.mockReset().mockResolvedValue(outline());
    api.fetchLesson.mockReset().mockImplementation(async (_c, l) => lesson(l, l === 'one' ? 1 : 2));
    api.setLessonDone.mockReset().mockResolvedValue({ course: 'python', lesson: 'one', completed: true });
    api.searchLessons.mockReset().mockResolvedValue({ query: 'x', results: [] });
  });

  test('a locked learner sees the lock page with a buy button, and no lessons', async () => {
    api.fetchCatalog.mockResolvedValue({ ...catalog({ unlocked: false, reason: 'no_purchase' }), tracks: [], paths: [] } as never);
    const buy = jest.fn();
    render(<LearningHub onBuyCoins={buy} />);
    expect(await screen.findByText('The Learning Hub opens with coins')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Buy coins' }));
    expect(buy).toHaveBeenCalled();
  });

  test('coins over shows its own message', async () => {
    api.fetchCatalog.mockRejectedValue(new learnApi.LearnApiError(402, 'Your coins are over. Buy coins to keep reading.'));
    render(<LearningHub onBuyCoins={jest.fn()} />);
    expect(await screen.findByText('Your coins are over')).toBeInTheDocument();
  });

  test('the home page shows a tile per category; a category page lists its courses and switches category', async () => {
    render(<LearningHub />);
    const technical = await screen.findByRole('button', { name: /Technical: 1 courses, 2 lessons/ });
    expect(screen.getByRole('button', { name: /Aptitude: 0 courses/ })).toBeInTheDocument();
    fireEvent.click(technical);
    expect(await screen.findByRole('heading', { level: 1, name: 'Technical' })).toBeInTheDocument();
    expect(screen.getByText('Coming soon')).toBeInTheDocument();                       // planned courses are listed, not clickable cards
    expect(screen.queryByRole('button', { name: /React/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Aptitude/ }));                 // the switcher
    expect(await screen.findByRole('heading', { level: 1, name: 'Aptitude' })).toBeInTheDocument();
    expect(screen.getByText(/being written/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Learning Hub' }));             // breadcrumb back to the start
    expect(await screen.findByText('Browse by category')).toBeInTheDocument();
  });

  test('opening a course shows a breadcrumb that goes back to its category', async () => {
    render(<LearningHub />);
    fireEvent.click(await screen.findByRole('button', { name: /Technical: 1 courses/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Python, 2 lessons/ }));
    expect(await screen.findByText('Write programs')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Start learning/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Technical' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Technical' })).toBeInTheDocument();
  });

  test('reading a lesson: take-aways, next and previous, and marking it complete', async () => {
    render(<LearningHub />);
    fireEvent.click(await screen.findByRole('button', { name: /Technical: 1 courses/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Python, 2 lessons/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Start learning/ }));
    expect(await screen.findByRole('heading', { level: 1, name: 'First lesson' })).toBeInTheDocument();
    expect(screen.getByText('Learn A')).toBeInTheDocument();
    expect(screen.getAllByText('Part one').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Mark as complete' }));
    await waitFor(() => expect(api.setLessonDone).toHaveBeenCalledWith('python', 'one', true));
    expect(await screen.findByRole('button', { name: /Completed/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Next/ }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Second lesson' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Previous/ })).toBeInTheDocument();
  });

  test('search shows results and opens the lesson', async () => {
    api.searchLessons.mockResolvedValue({ query: 'loops', results: [{ course: 'python', course_title: 'Python', lesson: 'one', title: 'First lesson', chapter_title: 'Getting started', snippet: 'a loop' }] });
    render(<LearningHub />);
    fireEvent.change(await screen.findByPlaceholderText(/Search lessons/), { target: { value: 'loops' } });
    const hit = await screen.findByRole('button', { name: /First lesson/ });
    fireEvent.click(hit);
    expect(await screen.findByRole('heading', { level: 1, name: 'First lesson' })).toBeInTheDocument();
  });
});
