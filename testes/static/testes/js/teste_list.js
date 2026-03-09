(function () {
  // Helpers leves para query e manipulacao da tabela/lista.
  function qs(sel, root = document) {
    return root.querySelector(sel);
  }
  function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
  }

  // Estado da selecao (linhas elegiveis, marcadas e IDs).
  function getEnabledChecks() {
    return qsa(".rowCheck").filter((cb) => !cb.disabled);
  }

  function getCheckedChecks() {
    return getEnabledChecks().filter((cb) => cb.checked);
  }

  function getSelectedIds() {
    return getCheckedChecks().map((cb) => cb.value);
  }

  function setButtonsState({ hasSelection, allCanPay }) {
    const btnPagar = qs("#btnBulkPagar");
    const btnPromover = qs("#btnBulkPromover");
    const btnCancelar = qs("#btnBulkCancelar");
    const btnQuestionar = qs("#btnBulkQuestionar");

    if (btnPromover) btnPromover.disabled = !hasSelection;
    if (btnCancelar) btnCancelar.disabled = !hasSelection;
    if (btnQuestionar) btnQuestionar.disabled = !hasSelection;

    if (btnPagar) btnPagar.disabled = !(hasSelection && allCanPay);
  }

  // Animacao da barra de acoes em lote (aparece/some conforme selecao).
  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function stopBulkAnim(bulkBar) {
    if (bulkBar && bulkBar._bulkAnim) {
      bulkBar._bulkAnim.cancel();
      bulkBar._bulkAnim = null;
    }
  }

  function showBulkBarAnimated(bulkBar) {
    if (!bulkBar || !bulkBar.classList.contains("hidden")) return;

    stopBulkAnim(bulkBar);
    bulkBar.classList.remove("hidden");

    if (prefersReducedMotion()) return;

    bulkBar._bulkAnim = bulkBar.animate(
      [
        { opacity: 0, transform: "translateY(-8px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 180, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
    );

    bulkBar._bulkAnim.onfinish = () => {
      bulkBar._bulkAnim = null;
    };
  }

  function hideBulkBarAnimated(bulkBar) {
    if (!bulkBar || bulkBar.classList.contains("hidden")) return;

    stopBulkAnim(bulkBar);

    if (prefersReducedMotion()) {
      bulkBar.classList.add("hidden");
      return;
    }

    bulkBar._bulkAnim = bulkBar.animate(
      [
        { opacity: 1, transform: "translateY(0)" },
        { opacity: 0, transform: "translateY(-6px)" },
      ],
      { duration: 120, easing: "ease-out" }
    );

    bulkBar._bulkAnim.onfinish = () => {
      bulkBar.classList.add("hidden");
      bulkBar._bulkAnim = null;
    };
    bulkBar._bulkAnim.oncancel = () => {
      bulkBar._bulkAnim = null;
    };
  }

  function updateBulkBar(totalSelected) {
    const bulkBar = qs("#bulkBar");
    const countEl = qs("#selCount");

    if (countEl) countEl.textContent = String(totalSelected);

    if (!bulkBar) return;
    if (totalSelected > 0) showBulkBarAnimated(bulkBar);
    else hideBulkBarAnimated(bulkBar);
  }

  // Mantem o checkbox "selecionar todos" sincronizado com as linhas.
  function updateCheckAllState() {
    const checkAll = qs("#checkAll");
    if (!checkAll) return;

    const enabledChecks = getEnabledChecks();
    const checkedEnabled = enabledChecks.filter((cb) => cb.checked);

    checkAll.checked =
      enabledChecks.length > 0 && checkedEnabled.length === enabledChecks.length;

    checkAll.indeterminate =
      checkedEnabled.length > 0 && checkedEnabled.length < enabledChecks.length;
  }

  function computeAllCanPay(checkedChecks) {
    if (checkedChecks.length === 0) return false;
    return checkedChecks.every((cb) => cb.dataset.canPay === "1");
  }

  // Recalcula toda a UI dependente da selecao atual.
  function updateUI() {
    const checked = getCheckedChecks();
    const ids = checked.map((cb) => cb.value);

    const hasSelection = ids.length > 0;
    const allCanPay = computeAllCanPay(checked);

    updateBulkBar(ids.length);
    setButtonsState({ hasSelection, allCanPay });
    updateCheckAllState();
  }

  // Bindings da pagina (selecao em lote + clique na linha para abrir drawer).
  function bindCheckAll() {
    const checkAll = qs("#checkAll");
    if (!checkAll) return;

    checkAll.addEventListener("change", () => {
      const enabledChecks = getEnabledChecks();
      enabledChecks.forEach((cb) => (cb.checked = checkAll.checked));
      updateUI();
    });
  }

  function bindRowChecks() {
    qsa(".rowCheck").forEach((cb) => {
      cb.addEventListener("change", updateUI);
    });
  }

  function bindRowClickDrawer() {
    const rows = qsa("tr[data-detail-url]");
    const urls = rows.map((r) => r.dataset.detailUrl);

    rows.forEach((row, index) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest("input, button, a, label, i")) return;

        const url = row.dataset.detailUrl;
        if (!url) return;

        if (window.AppDrawer) {
          window.AppDrawer.setNav(urls, index);
          window.AppDrawer.open(url);
        }
      });
    });
  }

  function init() {
    updateUI();
    bindCheckAll();
    bindRowChecks();
    bindRowClickDrawer();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
