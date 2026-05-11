/*
 * theme.js
 * Handles site theme preference for light/dark/system modes.
 */

(function () {
  const key = 'unc-theme-preference';
  const validThemes = ['system', 'light', 'dark'];
  const themeMeta = {
    system: {
      iconClass: 'fa-circle-half-stroke',
      label: 'System',
      next: 'light',
    },
    light: {
      iconClass: 'fa-sun',
      label: 'Light',
      next: 'dark',
    },
    dark: {
      iconClass: 'fa-moon',
      label: 'Dark',
      next: 'system',
    },
  };

  function getSystemTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function getSavedPreference() {
    try {
      const savedPreference = localStorage.getItem(key);
      if (validThemes.includes(savedPreference)) {
        return savedPreference;
      }
    } catch (error) {
      return 'system';
    }

    return 'system';
  }

  function setSavedPreference(preference) {
    try {
      localStorage.setItem(key, preference);
    } catch (error) {
      // Ignore localStorage failures and continue with runtime theme only.
    }
  }

  function applyTheme(preference) {
    const resolvedTheme = preference === 'system' ? getSystemTheme() : preference;
    document.documentElement.setAttribute('data-theme-preference', preference);
    document.documentElement.setAttribute('data-theme', resolvedTheme);
    document.documentElement.style.colorScheme = resolvedTheme;
  }

  function updateToggleUi(preference) {
    const button = document.getElementById('theme-toggle');
    const icon = document.getElementById('theme-toggle-icon');
    if (!button || !icon || !themeMeta[preference]) {
      return;
    }

    const currentLabel = themeMeta[preference].label;
    const nextLabel = themeMeta[themeMeta[preference].next].label;
    icon.className = `fa-solid ${themeMeta[preference].iconClass}`;
    button.setAttribute('title', `Theme: ${currentLabel} (click for ${nextLabel})`);
    button.setAttribute('aria-label', `Theme is ${currentLabel}. Click to switch to ${nextLabel}.`);
  }

  function initializeThemeToggle() {
    const button = document.getElementById('theme-toggle');
    if (!button) {
      return;
    }

    const currentPreference = getSavedPreference();
    updateToggleUi(currentPreference);

    button.addEventListener('click', function () {
      const activePreference = getSavedPreference();
      const nextTheme = themeMeta[activePreference].next;
      setSavedPreference(nextTheme);
      applyTheme(nextTheme);
      updateToggleUi(nextTheme);
    });
  }

  function watchSystemThemeChanges() {
    if (!window.matchMedia) {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleSystemThemeUpdate = function () {
      const savedPreference = getSavedPreference();
      if (savedPreference === 'system') {
        applyTheme('system');
      }
      updateToggleUi(savedPreference);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleSystemThemeUpdate);
      return;
    }

    if (mediaQuery.addListener) {
      mediaQuery.addListener(handleSystemThemeUpdate);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const preference = getSavedPreference();
    applyTheme(preference);
    initializeThemeToggle();
    updateToggleUi(preference);
    watchSystemThemeChanges();
  });
})();
