// MathJax configuration for pymdownx.arithmatex (generic mode).
//
// arithmatex (generic: true) wraps $...$ / $$...$$ and \(...\) / \[...\]
// source math in elements with class "arithmatex", normalising inline math
// to \(...\) and display math to \[...\]. MathJax is therefore configured
// to process only those elements, with matching delimiters.
window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

// Re-typeset on every page change (Material's instant navigation).
document$.subscribe(() => {
  MathJax.startup.output.clearCache();
  MathJax.typesetClear();
  MathJax.texReset();
  MathJax.typesetPromise();
});
