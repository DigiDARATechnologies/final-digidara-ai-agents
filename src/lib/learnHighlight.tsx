/** A tiny syntax colouring for the code boxes in lessons (no library): comments, strings, numbers,
 * keywords, and for HTML and CSS their tags, attributes and properties. It only splits text into
 * spans with a class; the text itself is never changed or put in as HTML. */
import type { ReactNode } from "react";

type Rule = { re: RegExp; classify: (token: string) => string };

const words = (list: string) => new Set(list.split(/\s+/).filter(Boolean));

const PY = words("and as assert async await break class continue def del elif else except finally for from global if import in is lambda None nonlocal not or pass raise return try while with yield True False self");
const JS = words("async await break case catch class const continue default delete do else export extends finally for from function if import in instanceof let new null of return static super switch this throw true false try typeof undefined var void while yield");
const JAVA = words("abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for if implements import instanceof int interface long new null package private protected public record return short static super switch synchronized this throw throws true false try var void volatile while yield sealed permits");
const SQL = words("select from where and or not in between like is null order by group having limit offset distinct as join inner left right full outer on insert into values update set delete create table alter add drop column primary key foreign references unique default check index union all exists case when then else end asc desc count sum avg min max start transaction commit rollback");

const keyword = (set: Set<string>, ci = false) => (token: string) => (set.has(ci ? token.toLowerCase() : token) ? "kw" : "id");

function build(commentSource: string, extra: string, set: Set<string>, ci = false): Rule {
  const source = `(${commentSource})|("(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*'${extra})|(\\b\\d+(?:\\.\\d+)?\\b)|([A-Za-z_][A-Za-z0-9_]*)`;
  return {
    re: new RegExp(source, "g"),
    classify: (token) => {
      if (/^(#|\/\/|\/\*|--)/.test(token)) return "cm";
      if (/^["'`]/.test(token)) return "st";
      if (/^\d/.test(token)) return "nu";
      return keyword(set, ci)(token);
    },
  };
}

const RULES: Record<string, Rule> = {
  python: build("#[^\\n]*", "", PY),
  javascript: build("\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/", "|`(?:[^`\\\\\\\\]|\\\\\\\\.)*`", JS),
  java: build("\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/", "", JAVA),
  sql: build("--[^\\n]*", "", SQL, true),
  html: {
    re: /(<!--[\s\S]*?-->)|("[^"\n]*"|'[^'\n]*')|(<\/?[A-Za-z][\w-]*|\/?>)|([A-Za-z-]+(?==))/g,
    classify: (token) => (token.startsWith("<!--") ? "cm" : /^["']/.test(token) ? "st" : /^(<|\/?>)/.test(token) ? "kw" : "id"),
  },
  css: {
    re: /(\/\*[\s\S]*?\*\/)|("[^"\n]*"|'[^'\n]*')|(@[a-z-]+|#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%|s)?)|([a-z-]+(?=\s*:))/g,
    classify: (token) => (token.startsWith("/*") ? "cm" : /^["']/.test(token) ? "st" : /^(@|#|\d)/.test(token) ? "nu" : "kw"),
  },
};
RULES.js = RULES.javascript;
RULES.py = RULES.python;
RULES.mysql = RULES.sql;
RULES.xml = RULES.html;

export function highlight(code: string, lang: string): ReactNode[] {
  const rule = RULES[lang];
  if (!rule) return [code];
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const match of code.matchAll(new RegExp(rule.re.source, "g"))) {
    const start = match.index ?? 0;
    if (start > last) out.push(code.slice(last, start));
    const token = match[0];
    const cls = rule.classify(token);
    out.push(cls === "id" ? token : <span key={n++} className={`tk-${cls}`}>{token}</span>);
    last = start + token.length;
  }
  if (last < code.length) out.push(code.slice(last));
  return out;
}
