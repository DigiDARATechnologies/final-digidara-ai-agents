import { isEnglishText } from '../../src/lib/englishOnly';

test.each([
  'வணக்கம், எனக்கு SQL கற்றுக்கொடு',
  'मुझे पायथन सिखाओ',
  'నాకు జావా నేర్పు',
  '教我编程',
  'Explain this: 𑿀',
])('other languages are refused: %s', (text) => {
  expect(isEnglishText(text)).toBe(false);
});

test.each([
  'Explain recursion with an example, please!',
  'Résumé tips: π ≈ 3.14, √16 = 4 👍',
  'C++ vs. Java — which first?',
])('English is accepted: %s', (text) => {
  expect(isEnglishText(text)).toBe(true);
});
