import { render } from '@testing-library/react';
import { renderMessageText } from '../../src/lib/messageText';

function renderText(text: string) {
  return render(<div>{renderMessageText(text)}</div>).container;
}

test('a fenced block is rendered verbatim in a monospace <pre>, keeping the caret aligned', () => {
  const error = '  File "src/main.py", line 3\n    print(total\n              ^\nSyntaxError: \'(\' was never closed';
  const container = renderText('### Syntax error in your code\n\n```\n' + error + '\n```');
  const pre = container.querySelector('pre.message-code');
  expect(pre).not.toBeNull();
  expect(pre!.textContent).toBe(error);
  expect(container.querySelector('.message-heading')!.textContent).toBe('Syntax error in your code');
});

test('backslash-n inside a code line is NOT turned into a line break (outside a fence it still is)', () => {
  const inside = renderText('```\nprint("hi\\n"\n```');
  expect(inside.querySelector('pre')!.textContent).toBe('print("hi\\n"');
  const outside = renderText('first\\nsecond');
  expect(outside.textContent).toContain('first');
  expect(outside.firstElementChild!.children.length).toBe(2);
});

test('markdown inside a fence is not interpreted', () => {
  const container = renderText('```\n**not bold** and - not a bullet and # not a heading\n```');
  expect(container.querySelector('strong')).toBeNull();
  expect(container.querySelector('.message-list-item')).toBeNull();
  expect(container.querySelector('pre')!.textContent).toBe('**not bold** and - not a bullet and # not a heading');
});

test('several fenced blocks and the text between them all render, in order', () => {
  const container = renderText('### 2 syntax errors in your code\n\n```\nfirst error\n```\n\n```\nsecond error\n```\n\nAttach both files again once it is fixed.');
  const blocks = Array.from(container.querySelectorAll('pre.message-code')).map((pre) => pre.textContent);
  expect(blocks).toEqual(['first error', 'second error']);
  expect(container.textContent).toContain('Attach both files again once it is fixed.');
  expect(container.textContent!.indexOf('first error')).toBeLessThan(container.textContent!.indexOf('second error'));
});

test('a message with no fence renders exactly as before, blank lines included', () => {
  const container = renderText('Line one\n\nLine three');
  expect(container.querySelector('pre')).toBeNull();
  expect(container.firstElementChild!.children.length).toBe(3);
});

test('bullets, numbered items, headings and inline markup still work', () => {
  const container = renderText('# Title\n- a bullet\n1. a step\nSome **bold** and `code`');
  expect(container.querySelector('.message-heading')!.textContent).toBe('Title');
  expect(container.querySelectorAll('.message-list-item')).toHaveLength(2);
  expect(container.querySelector('strong')!.textContent).toBe('bold');
  expect(container.querySelector('code')!.textContent).toBe('code');
});

test('an unclosed fence is shown as plain text rather than swallowing the message', () => {
  const container = renderText('before\n```\nnever closed');
  expect(container.querySelector('pre')).toBeNull();
  expect(container.textContent).toContain('never closed');
});

test('message text is never interpreted as HTML', () => {
  const container = renderText('```\n<img src=x onerror=alert(1)>\n```\n<b>hi</b>');
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('b')).toBeNull();
  expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
});
