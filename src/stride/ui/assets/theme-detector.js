// OS Theme Detection for STRIDE Dashboard
// Detects user's OS color scheme preference and applies initial theme

(function () {
  "use strict";

  // Always default to dark theme
  function getOSThemePreference() {
    return true; // Always use dark theme by default
  }

  // Apply theme to all relevant elements
  function applyTheme(isDark) {
    const theme = isDark ? "dark-theme" : "light-theme";

    // Update root element
    const root = document.querySelector("body").parentElement;
    if (root) {
      root.className = theme;
    }

    // Update page content
    const pageContent = document.getElementById("page-content");
    if (pageContent) {
      pageContent.className = "page-content " + theme;
    }

    // Update sidebar
    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
      sidebar.className = "sidebar-nav " + theme;
    }

    // Update theme toggle switch
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.checked = isDark;
    }

    console.log("STRIDE Theme applied:", theme);
  }

  // Apply theme on page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      const prefersDark = getOSThemePreference();
      applyTheme(prefersDark);
    });
  } else {
    // DOM already loaded
    const prefersDark = getOSThemePreference();
    applyTheme(prefersDark);
  }

  // OS theme change listener removed - we always default to dark theme
  // Users can manually toggle theme using the theme toggle switch
})();
