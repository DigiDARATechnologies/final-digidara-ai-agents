import { useEffect, useState } from "react";
import { listLanguages, runPlayground, type Judge0Language, type PlaygroundResult } from "../lib/codeforgeApi";

interface Props {
  open: boolean;
  onClose: () => void;
  onToast: (message: string) => void;
}

const DEFAULT_SNIPPETS: Record<string, string> = {
  python: 'print("Hello, DigiDARA!")',
  c: '#include <stdio.h>\n\nint main() {\n    printf("Hello, DigiDARA!\\n");\n    return 0;\n}',
  "c++": '#include <iostream>\n\nint main() {\n    std::cout << "Hello, DigiDARA!" << std::endl;\n    return 0;\n}',
  java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, DigiDARA!");\n    }\n}',
  javascript: 'console.log("Hello, DigiDARA!");',
};

function guessSnippet(name: string): string {
  const lower = name.toLowerCase();
  for (const key of Object.keys(DEFAULT_SNIPPETS)) {
    if (lower.startsWith(key)) return DEFAULT_SNIPPETS[key];
  }
  return "";
}

export default function CodeForgePlayground({ open, onClose, onToast }: Props) {
  const [languages, setLanguages] = useState<Judge0Language[] | null>(null);
  const [languageId, setLanguageId] = useState<number | null>(null);
  const [sourceCode, setSourceCode] = useState("");
  const [stdin, setStdin] = useState("");
  const [result, setResult] = useState<PlaygroundResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!open || languages) return;
    listLanguages()
      .then((res) => {
        setLanguages(res.languages);
        const python = res.languages.find((l) => l.name.toLowerCase().startsWith("python 3"));
        const fallback = python ?? res.languages[0];
        if (fallback) {
          setLanguageId(fallback.id);
          setSourceCode(guessSnippet(fallback.name));
        }
      })
      .catch(() => onToast("Could not load the language list."));
  }, [open, languages, onToast]);

  function handleLanguageChange(id: number) {
    setLanguageId(id);
    const lang = languages?.find((l) => l.id === id);
    if (lang) setSourceCode(guessSnippet(lang.name));
    setResult(null);
  }

  async function handleRun() {
    if (languageId === null || !sourceCode.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      const res = await runPlayground(languageId, sourceCode, stdin);
      setResult(res);
    } catch (error) {
      onToast((error as Error).message || "Run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className={`modal-overlay${open ? " open" : ""}`} onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card" style={{ maxWidth: 900, width: "92vw" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "18px 22px", borderBottom: "1px solid var(--border)" }}>
          <h2 style={{ margin: 0 }}>Code Playground</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Language</label>
            {languages === null ? (
              <p>Loading languages…</p>
            ) : (
              <select
                value={languageId ?? ""}
                onChange={(event) => handleLanguageChange(Number(event.target.value))}
                style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid var(--border)" }}
              >
                {languages.map((lang) => (
                  <option key={lang.id} value={lang.id}>
                    {lang.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Code</label>
            <textarea
              value={sourceCode}
              onChange={(event) => setSourceCode(event.target.value)}
              rows={12}
              spellCheck={false}
              style={{ width: "100%", fontFamily: "monospace", fontSize: 13, padding: 10, borderRadius: 8, border: "1px solid var(--border)", resize: "vertical" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Stdin (optional)</label>
            <textarea
              value={stdin}
              onChange={(event) => setStdin(event.target.value)}
              rows={3}
              spellCheck={false}
              style={{ width: "100%", fontFamily: "monospace", fontSize: 13, padding: 10, borderRadius: 8, border: "1px solid var(--border)", resize: "vertical" }}
            />
          </div>

          <button className="btn btn-primary" disabled={running || languageId === null} onClick={handleRun} style={{ alignSelf: "flex-start" }}>
            {running ? "Running…" : "▶ Run"}
          </button>

          {result && (
            <div style={{ background: "var(--bg-soft)", border: "1px solid var(--border)", borderRadius: 8, padding: 14 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{result.status.description}</div>
              {result.stdout && (
                <>
                  <small style={{ opacity: 0.7 }}>stdout</small>
                  <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0 10px" }}>{result.stdout}</pre>
                </>
              )}
              {result.stderr && (
                <>
                  <small style={{ opacity: 0.7 }}>stderr</small>
                  <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0 10px", color: "#c0392b" }}>{result.stderr}</pre>
                </>
              )}
              {result.compile_output && (
                <>
                  <small style={{ opacity: 0.7 }}>compile output</small>
                  <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0 10px", color: "#c0392b" }}>{result.compile_output}</pre>
                </>
              )}
              {(result.time || result.memory) && (
                <small style={{ opacity: 0.7 }}>
                  {result.time ? `${result.time}s` : ""} {result.memory ? `· ${result.memory} KB` : ""}
                </small>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
