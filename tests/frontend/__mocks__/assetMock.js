// Jest has no bundler-style asset loader, unlike Vite, which resolves an
// `import x from "./file.svg"` (or .png/.jpg/etc) to the file's built URL.
// This stands in for that URL so components importing an image asset for use
// as an <img src> (e.g. Logo.tsx) don't crash the test trying to parse raw
// binary/SVG data as JavaScript.
module.exports = "test-file-stub";
