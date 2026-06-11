document.addEventListener("DOMContentLoaded", () => {
  const applyTheme = (theme) => {
    const normalizedTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = normalizedTheme;
    localStorage.setItem("app-theme", normalizedTheme);

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const isDark = normalizedTheme === "dark";
      const label = button.querySelector(".theme-label");
      button.setAttribute("aria-pressed", String(isDark));
      button.setAttribute("aria-label", isDark ? "Ativar tema claro" : "Ativar tema escuro");
      if (label) {
        label.textContent = isDark ? "Tema escuro" : "Tema claro";
      }
    });
  };

  applyTheme(localStorage.getItem("app-theme") || "light");

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      if (window.lucide) {
        window.lucide.createIcons();
      }
    });
  });

  const applySidebar = (state) => {
    const normalizedState = state === "collapsed" ? "collapsed" : "expanded";
    const isCollapsed = normalizedState === "collapsed";
    document.documentElement.dataset.sidebar = normalizedState;
    localStorage.setItem("app-sidebar", normalizedState);

    document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(isCollapsed));
      button.setAttribute("aria-label", isCollapsed ? "Expandir menu" : "Recolher menu");
      button.setAttribute("title", isCollapsed ? "Expandir menu" : "Recolher menu");
    });
  };

  applySidebar(localStorage.getItem("app-sidebar") || "expanded");

  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextState = document.documentElement.dataset.sidebar === "collapsed" ? "expanded" : "collapsed";
      applySidebar(nextState);
    });
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }

  document.querySelectorAll("[data-money]").forEach((input) => {
    input.addEventListener("blur", () => {
      const raw = input.value.replace(/[^\d,.-]/g, "").trim();
      if (!raw) return;
      const normalized = raw.includes(",")
        ? raw.replace(/\./g, "").replace(",", ".")
        : raw;
      const value = Number.parseFloat(normalized);
      if (!Number.isNaN(value)) {
        input.value = value.toLocaleString("pt-BR", {
          style: "currency",
          currency: "BRL",
        });
      }
    });
  });

  document.querySelectorAll("[data-file-label]").forEach((input) => {
    input.addEventListener("change", () => {
      const target = document.querySelector(input.dataset.fileLabel);
      if (target) {
        target.textContent = input.files.length ? input.files[0].name : "Nenhum arquivo selecionado";
      }
    });
  });

  document.querySelectorAll("[data-requires-observation]").forEach((select) => {
    select.addEventListener("change", () => {
      const observation = document.querySelector(select.dataset.requiresObservation);
      if (!observation) return;
      const mustExplain = ["Reprovado", "Corrigir"].includes(select.value);
      observation.required = mustExplain;
      observation.classList.toggle("border-danger", mustExplain);
    });
  });

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const input = document.querySelector(button.dataset.passwordToggle);
    if (!input) return;

    button.addEventListener("click", () => {
      const shouldShow = input.type === "password";
      input.type = shouldShow ? "text" : "password";
      button.setAttribute("aria-pressed", String(shouldShow));
      button.setAttribute("aria-label", shouldShow ? "Ocultar senha" : "Mostrar senha");
      button.innerHTML = shouldShow
        ? '<i data-lucide="eye-off" aria-hidden="true"></i>'
        : '<i data-lucide="eye" aria-hidden="true"></i>';

      if (window.lucide) {
        window.lucide.createIcons();
      }
    });
  });
});
