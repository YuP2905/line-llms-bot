(function() {
  const darkModeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  const updateTheme = (isDark) => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  updateTheme(darkModeMediaQuery.matches);

  darkModeMediaQuery.addEventListener("change", (e) => {
    updateTheme(e.matches);
  });
})();