(function () {
  // Referencias principais do drawer (painel, backdrop e area de conteudo dinamico).
  const drawer = document.getElementById("drawer");
  const backdrop = document.getElementById("drawerBackdrop");
  const content = document.getElementById("drawerContent");

  if (!drawer || !backdrop || !content) return;

  let navUrls = [];
  let navIndex = -1;

  // Mantem a lista de URLs do drawer para navegacao anterior/proximo.
  function setNav(urls, index) {
    navUrls = Array.isArray(urls) ? urls : [];
    navIndex = typeof index === "number" ? index : -1;
  }

  // Abre/fecha a estrutura visual do drawer e trava o scroll da pagina.
  function openDrawer() {
    drawer.classList.remove("translate-x-full");
    backdrop.classList.remove("hidden");
    document.documentElement.classList.add("overflow-hidden"); // trava scroll
  }

  function closeDrawer() {
    drawer.classList.add("translate-x-full");
    document.documentElement.classList.remove("overflow-hidden");

    setTimeout(() => {
      backdrop.classList.add("hidden");
    }, 250);
  }

  // Liga os botoes de navegacao entre registros carregados no drawer.
  function bindNavButtons() {
    const btnPrev = content.querySelector("[data-drawer-prev]");
    const btnNext = content.querySelector("[data-drawer-next]");

    if (btnPrev) {
      btnPrev.disabled = navIndex <= 0;
      btnPrev.onclick = () => {
        if (navIndex > 0) {
          navIndex--;
          loadDrawer(navUrls[navIndex]);
        }
      };
    }

    if (btnNext) {
      btnNext.disabled = navIndex < 0 || navIndex >= navUrls.length - 1;
      btnNext.onclick = () => {
        if (navIndex >= 0 && navIndex < navUrls.length - 1) {
          navIndex++;
          loadDrawer(navUrls[navIndex]);
        }
      };
    }
  }

  // Respeita acessibilidade de reducao de movimento para animacoes do drawer.
  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  // Controla a expansao inline dos itens de historico dentro do drawer.
  function setHistoryExpanded(toggle, panel, expanded) {
    const chevron = toggle.querySelector("[data-history-chevron]");
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");

    if (chevron) chevron.classList.toggle("rotate-180", expanded);

    if (expanded) {
      panel.classList.remove("hidden");
      if (!prefersReducedMotion()) {
        panel.animate(
          [
            { opacity: 0, transform: "translateY(-4px)" },
            { opacity: 1, transform: "translateY(0)" },
          ],
          { duration: 160, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
        );
      }
      return;
    }

    if (prefersReducedMotion()) {
      panel.classList.add("hidden");
      return;
    }

    const anim = panel.animate(
      [
        { opacity: 1, transform: "translateY(0)" },
        { opacity: 0, transform: "translateY(-3px)" },
      ],
      { duration: 120, easing: "ease-out" }
    );

    anim.onfinish = () => panel.classList.add("hidden");
  }

  // Vincula o comportamento de acordeao aos itens do historico renderizados no partial.
  function bindHistoryAccordions() {
    const toggles = content.querySelectorAll("[data-history-toggle]");
    toggles.forEach((toggle) => {
      const container = toggle.closest(".rounded-xl");
      const panel = container ? container.querySelector("[data-history-panel]") : null;
      if (!panel) return;

      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") === "true";
        setHistoryExpanded(toggle, panel, !expanded);
      });
    });
  }

  // Carrega o partial HTML via AJAX e rebinda interacoes do conteudo injetado.
  async function loadDrawer(url) {
    if (!url) return;

    // loading state (so skeleton)
    content.innerHTML = `
      <div class="space-y-3">
        <div class="h-5 w-2/3 rounded bg-slate-100 animate-pulse"></div>
        <div class="h-4 w-full rounded bg-slate-100 animate-pulse"></div>
        <div class="h-4 w-5/6 rounded bg-slate-100 animate-pulse"></div>
        <div class="h-28 w-full rounded bg-slate-100 animate-pulse"></div>
      </div>
    `;

    openDrawer();

    try {
      const res = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });

      if (!res.ok) throw new Error("Falha ao carregar detalhes.");

      const html = await res.text();
      content.innerHTML = html;

      // fechar
      content.querySelectorAll("[data-drawer-close]").forEach((btn) => {
        btn.addEventListener("click", closeDrawer);
      });

      // agora sim os botoes existem, entao binda
      bindNavButtons();
      bindHistoryAccordions();
    } catch (err) {
      content.innerHTML = `
        <div class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div class="font-semibold mb-1">Não foi possível carregar</div>
          <div>${err?.message || "Tente novamente."}</div>
        </div>
      `;
    }
  }

  // API global usada pela tabela/lista para abrir o drawer.
  window.AppDrawer = { open: loadDrawer, close: closeDrawer, setNav };

  // fechar ao clicar no backdrop
  backdrop.addEventListener("click", closeDrawer);

  // fechar no ESC
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  // fechar em qualquer botao com data-drawer-close (fora do conteudo, se existir)
  document.querySelectorAll("[data-drawer-close]").forEach((btn) => {
    btn.addEventListener("click", closeDrawer);
  });
})();
