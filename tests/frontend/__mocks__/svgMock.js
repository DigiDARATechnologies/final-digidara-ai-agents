// Jest has no bundler-style asset loader, unlike Vite, which resolves an
// `import x from "./file.svg"` to the file's built URL. This stands in for
// that URL so components importing an .svg for use as an <img src> (e.g.
// Logo.tsx) don't crash the test with "Unexpected token '<'" from Jest
// trying to parse raw SVG markup as JavaScript.
module.exports = "test-file-stub.svg";
