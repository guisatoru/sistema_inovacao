(function () {
  // Le o estado atual do panel para saber se existe filtro aplicado (texto/checkbox).
  function panelHasAppliedValues(panel) {
    const fields = panel.querySelectorAll("input, select, textarea");

    for (const el of fields) {
      if (!el.name) continue;

      if (el.type === "checkbox" || el.type === "radio") {
        if (el.checked) return true;
        continue;
      }

      if ((el.value || "").trim() !== "") return true;
    }

    return false;
  }

  // Atualiza a cor do icone do filtro conforme estado (aberto/aplicado/limpo).
  function updateFilterIconState(panel, isOpen) {
    const wrap = panel.closest("[data-filter]");
    if (!wrap) return;

    const icon = wrap.querySelector("[data-filter-icon]");
    if (!icon) return;

    const hasApplied = panelHasAppliedValues(panel);

    icon.classList.remove("text-slate-400", "text-indigo-500", "text-indigo-600");

    if (isOpen) {
      icon.classList.add("text-indigo-500");
      return;
    }

    icon.classList.add(hasApplied ? "text-indigo-600" : "text-slate-400");
  }

  // Gira a seta (chevron) do botao do filtro quando o panel abre.
  function setChevronState(panel, isOpen) {
    const wrap = panel.closest("[data-filter]");
    if (!wrap) return;

    const chevron = wrap.querySelector("[data-filter-chevron]");
    if (!chevron) return;

    chevron.classList.toggle("rotate-180", isOpen);
  }

  // Helpers de animacao para abrir/fechar panels de filtro com fallback acessivel.
  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function stopAnim(panel) {
    if (panel._filterAnim) {
      panel._filterAnim.cancel();
      panel._filterAnim = null;
    }
  }

  function hidePanel(panel) {
    stopAnim(panel);
    panel.classList.add("hidden");
    setChevronState(panel, false);
    updateFilterIconState(panel, false);
  }

  function showPanel(panel) {
    stopAnim(panel);
    panel.classList.remove("hidden");
    setChevronState(panel, true);
    updateFilterIconState(panel, true);

    if (prefersReducedMotion()) return;

    panel._filterAnim = panel.animate(
      [
        { opacity: 0, transform: "translateY(-6px) scale(0.985)" },
        { opacity: 1, transform: "translateY(0) scale(1)" },
      ],
      { duration: 170, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
    );

    panel._filterAnim.onfinish = () => {
      panel._filterAnim = null;
    };
  }

  function hidePanelAnimated(panel) {
    if (panel.classList.contains("hidden")) return;

    stopAnim(panel);

    if (prefersReducedMotion()) {
      panel.classList.add("hidden");
      setChevronState(panel, false);
      updateFilterIconState(panel, false);
      return;
    }

    panel._filterAnim = panel.animate(
      [
        { opacity: 1, transform: "translateY(0) scale(1)" },
        { opacity: 0, transform: "translateY(-4px) scale(0.99)" },
      ],
      { duration: 130, easing: "ease-out" }
    );

    panel._filterAnim.onfinish = () => {
      panel.classList.add("hidden");
      setChevronState(panel, false);
      updateFilterIconState(panel, false);
      panel._filterAnim = null;
    };
    panel._filterAnim.oncancel = () => {
      panel._filterAnim = null;
    };
  }

  function closeAll(exceptPanel = null) {
    document.querySelectorAll("[data-filter-panel]").forEach((p) => {
      if (p === exceptPanel) return;
      hidePanelAnimated(p);
    });
  }

  // Captura/restaura os valores do filtro para suportar botao "Cancelar".
  function snapshotValues(panel) {
    const state = {};
    panel.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.name) return;

      if (el.type === "checkbox") {
        // guarda checked
        if (!state[el.name]) state[el.name] = [];
        if (el.checked) state[el.name].push(el.value);
      } else {
        state[el.name] = el.value;
      }
    });
    return state;
  }

  function restoreValues(panel, state) {
    panel.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.name) return;

      if (el.type === "checkbox") {
        const selected = state[el.name] || [];
        el.checked = selected.includes(el.value);
      } else if (Object.prototype.hasOwnProperty.call(state, el.name)) {
        el.value = state[el.name];
      }
    });
  }

  // Busca local dentro de listas de checkbox (ex.: solicitante).
  // filtro de busca dentro do dropdown (checkbox list)
  function wireSearch(panel) {
    const search = panel.querySelector("[data-filter-search]");
    if (!search) return;

    search.addEventListener("input", () => {
      const q = (search.value || "").trim().toLowerCase();
      panel.querySelectorAll("[data-filter-item]").forEach((row) => {
        const text = (row.getAttribute("data-filter-text") || "").toLowerCase();
        row.classList.toggle("hidden", q && !text.includes(q));
      });
    });
  }

  // Limpa apenas os campos do filtro atual (sem submeter o form).
  // botao limpar (do proprio filtro)
  function wireClear(panel) {
    const btn = panel.querySelector("[data-filter-clear]");
    if (!btn) return;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      panel.querySelectorAll("input, select").forEach((el) => {
        if (!el.name) return;
        if (el.type === "checkbox") el.checked = false;
        else el.value = "";
      });

      // se tiver search, limpa tambem e re-mostra tudo
      const search = panel.querySelector("[data-filter-search]");
      if (search) {
        search.value = "";
        panel.querySelectorAll("[data-filter-item]").forEach((row) => row.classList.remove("hidden"));
      }
    });
  }

  // Inicializa todos os dropdowns de filtro e sincroniza UI/estado.
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-filter]").forEach((wrap) => {
      const btn = wrap.querySelector("[data-filter-btn]");
      const panel = wrap.querySelector("[data-filter-panel]");
      const cancelBtn = wrap.querySelector("[data-filter-cancel]");

      if (!btn || !panel) return;

      // impede clique dentro do wrap/panel fechar
      wrap.addEventListener("click", (e) => e.stopPropagation());
      panel.addEventListener("click", (e) => e.stopPropagation());

      wireSearch(panel);
      wireClear(panel);
      updateFilterIconState(panel, false);

      panel.addEventListener("input", () => {
        updateFilterIconState(panel, !panel.classList.contains("hidden"));
      });
      panel.addEventListener("change", () => {
        updateFilterIconState(panel, !panel.classList.contains("hidden"));
      });

      let savedState = snapshotValues(panel);

      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const isOpen = !panel.classList.contains("hidden");
        closeAll(panel);

        if (!isOpen) {
          savedState = snapshotValues(panel);
          showPanel(panel);

          const first = panel.querySelector("input, select");
          if (first) setTimeout(() => first.focus(), 0);
        } else {
          hidePanelAnimated(panel);
        }
      });

      if (cancelBtn) {
        cancelBtn.addEventListener("click", (e) => {
          e.preventDefault();
          restoreValues(panel, savedState);
          hidePanelAnimated(panel);
        });
      }
    });

    document.addEventListener("click", () => closeAll());
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeAll();
    });
  });
})();

