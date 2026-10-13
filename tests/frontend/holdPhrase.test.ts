import { isHoldRequest, joinAnswer, withoutHoldPhrase } from '../../src/lib/holdPhrase';

test.each([
  'Just a minute', 'just a minute.', 'Wait', 'wait a second', 'one moment please', 'Hold on', 'Let me think',
  'I worked at Infosys, just a minute', 'My project was about sales, let me think.', 'give me a second',
])('"%s" asks for more time', (text) => {
  expect(isHoldRequest(text)).toBe(true);
});

test.each([
  'I can wait for the results', 'The meeting took a minute longer than planned and then we left early',
  'I worked at Infosys for two years.', 'Waiting in line is boring',
])('"%s" is a normal answer', (text) => {
  expect(isHoldRequest(text)).toBe(false);
});

test('what was said before the phrase is kept and joined with the rest', () => {
  expect(withoutHoldPhrase('I worked at Infosys, just a minute')).toBe('I worked at Infosys');
  expect(withoutHoldPhrase('Just a minute')).toBe('');
  expect(joinAnswer('I worked at Infosys', 'as a data analyst.')).toBe('I worked at Infosys as a data analyst.');
  expect(joinAnswer('', 'Hello.')).toBe('Hello.');
});
