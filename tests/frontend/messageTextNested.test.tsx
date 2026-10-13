import { render, screen } from '@testing-library/react';
import { renderMessageText } from '../../src/lib/messageText';

test('headings, bold and nested bullets render as formatting, not raw markdown', () => {
  const { container } = render(<div>{renderMessageText('### Chat Summaries:\n1. **Coding Practice · Data Science**:\n  - Sum of List (Medium)\n    - Fix the Loop (Hard)')}</div>);
  expect(screen.getByText('Chat Summaries:').closest('.message-heading')).not.toBeNull();
  expect(screen.getByText('Coding Practice · Data Science').tagName).toBe('STRONG');
  const items = container.querySelectorAll('.message-list-item');
  expect(items).toHaveLength(3);
  expect((items[1] as HTMLElement).style.paddingLeft).toBe('22px');
  expect((items[2] as HTMLElement).style.paddingLeft).toBe('40px');
  expect(container.textContent).not.toContain('**');
  expect(container.textContent).not.toContain('###');
});
