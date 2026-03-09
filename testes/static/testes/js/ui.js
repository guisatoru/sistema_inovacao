(function () {
  // ===== Toast auto-dismiss =====
  function initToasts() {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toasts = Array.from(container.querySelectorAll(".toast"));
    toasts.forEach((t) => {
      setTimeout(() => {
        t.classList.add("out");
        setTimeout(() => t.remove(), 200);
      }, 2800);
    });
  }

  // ===== Modal =====
  const modal = {
    el: null,
    titleEl: null,
    msgEl: null,

    obsWrap: null,
    obsLabel: null,
    obsInput: null,
    obsError: null,

    cancelBtn: null,
    confirmBtn: null,

    onConfirm: null,
    mode: "confirm",
    requireObs: false,

    open({ title, message, withObs = false, requireObs = false, confirmText = "Confirmar", mode = "confirm", onConfirm }) {
      this.onConfirm = onConfirm || null;
      this.mode = mode;
      this.requireObs = !!requireObs;

      this.titleEl.textContent = title || "Confirmar ação";
      this.msgEl.textContent = message || "Tem certeza?";

      // reset erro
      this.obsError.textContent = "";
      this.obsError.classList.add("hidden");

      if (withObs) {
        this.obsWrap.classList.remove("hidden");
        this.obsInput.value = "";
        this.obsLabel.textContent = this.requireObs ? "Observação (obrigatória)" : "Observação (opcional)";
        setTimeout(() => this.obsInput.focus(), 0);
      } else {
        this.obsWrap.classList.add("hidden");
      }

      if (mode === "info") {
        this.cancelBtn.classList.add("hidden");
        this.confirmBtn.textContent = confirmText || "Fechar";
      } else {
        this.cancelBtn.classList.remove("hidden");
        this.confirmBtn.textContent = confirmText || "Confirmar";
      }

      this.el.classList.remove("hidden");
      this.el.setAttribute("aria-hidden", "false");
    },

    close() {
      this.el.classList.add("hidden");
      this.el.setAttribute("aria-hidden", "true");
      this.onConfirm = null;
      this.mode = "confirm";
      this.requireObs = false;
    },

    showObsError(msg) {
      this.obsError.textContent = msg;
      this.obsError.classList.remove("hidden");
      this.obsInput.focus();
    },
  };

  function initModal() {
    modal.el = document.getElementById("appModal");
    if (!modal.el) return;

    modal.titleEl = document.getElementById("modalTitle");
    modal.msgEl = document.getElementById("modalMessage");

    modal.obsWrap = document.getElementById("modalObsWrap");
    modal.obsInput = document.getElementById("modalObs");

    modal.obsLabel = modal.obsWrap ? modal.obsWrap.querySelector("label") : null;
    if (!modal.obsLabel) {
      modal.obsLabel = document.createElement("label");
      modal.obsLabel.className = "block text-xs text-slate-600 mb-1";
      modal.obsLabel.textContent = "Observação";
      modal.obsWrap.prepend(modal.obsLabel);
    }

    modal.obsError = document.createElement("div");
    modal.obsError.className = "mt-2 text-xs font-semibold text-rose-700 hidden";
    modal.obsWrap.appendChild(modal.obsError);

    // botão cancelar (qualquer data-modal-close serve)
    modal.cancelBtn = modal.el.querySelector("[data-modal-close]");
    modal.confirmBtn = document.getElementById("modalConfirmBtn");

    // fechar
    modal.el.querySelectorAll("[data-modal-close]").forEach((el) => {
      el.addEventListener("click", () => modal.close());
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.el.classList.contains("hidden")) modal.close();
    });

    modal.confirmBtn.addEventListener("click", () => {
      const obs = (modal.obsInput?.value || "").trim();

      if (!modal.obsWrap.classList.contains("hidden") && modal.requireObs && !obs) {
        modal.showObsError("Observação é obrigatória.");
        return; // não fecha
      }

      if (typeof modal.onConfirm === "function") {
        modal.onConfirm({ observacao: obs });
      }
      modal.close();
    });
  }

  function ensureHiddenInput(form, name) {
    let input = form.querySelector(`input[name='${name}']`);
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      form.appendChild(input);
    }
    return input;
  }

  function openConfirmForForm(form, customSubmitterBtn) {
    const title = form.getAttribute("data-confirm-title") || (customSubmitterBtn?.getAttribute("data-confirm-title")) || "Confirmar ação";
    const msg = form.getAttribute("data-confirm-form") || (customSubmitterBtn?.getAttribute("data-confirm-form")) || "Confirmar?";
    const requireObs = (form.getAttribute("data-require-obs") === "1") || (customSubmitterBtn?.getAttribute("data-require-obs") === "1");
    const withObsAttr = form.getAttribute("data-with-obs") ?? customSubmitterBtn?.getAttribute("data-with-obs");
    const withObs = withObsAttr != null ? withObsAttr === "1" : requireObs;

    // se for botão de lote com formaction, garantir action correta
    const targetAction = customSubmitterBtn?.getAttribute("formaction");
    if (targetAction) form.setAttribute("action", targetAction);

      modal.open({
        title,
        message: msg,
        withObs,
        requireObs,
        mode: "confirm",
      onConfirm: ({ observacao }) => {
        const input = ensureHiddenInput(form, "observacao");
        input.value = observacao || "";
        form.submit();
      },
    });
  }

  // ==========================
  // Delegation (pega drawer também)
  // ==========================

  // 1) Intercepta CLIQUE no submit (mais confiável pro drawer)
  function onDocumentClick(e) {
    // Observações clicáveis
    const obsTrigger = e.target.closest("[data-show-obs]");
    if (obsTrigger) {
      e.preventDefault();
      const title = obsTrigger.getAttribute("data-obs-title") || "Observação";
      const text = (obsTrigger.getAttribute("data-obs-text") || "").trim();
      modal.open({
        title,
        message: text ? text : "Sem observação registrada.",
        withObs: false,
        mode: "info",
        confirmText: "Fechar",
      });
      return;
    }

    // Botão submit dentro de form com confirmação
    const submitBtn = e.target.closest("button[type='submit'], input[type='submit']");
    if (submitBtn) {
      const form = submitBtn.closest("form");
      if (form && form.hasAttribute("data-confirm-form")) {
        if (submitBtn.disabled) return;
        e.preventDefault();
        openConfirmForForm(form, submitBtn.tagName === "BUTTON" ? submitBtn : null);
        return;
      }

      // Caso especial: botão com data-confirm-form (lote) mesmo sem form com atributo
      if (submitBtn.hasAttribute("data-confirm-form")) {
        const f = submitBtn.closest("form");
        if (!f || submitBtn.disabled) return;
        e.preventDefault();
        openConfirmForForm(f, submitBtn.tagName === "BUTTON" ? submitBtn : null);
        return;
      }
    }
  }

  // 2) Intercepta SUBMIT (fallback)
  function onDocumentSubmit(e) {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute("data-confirm-form")) return;

    const submitter = e.submitter;
    if (submitter && submitter.disabled) return;

    e.preventDefault();
    openConfirmForForm(form, submitter && submitter.tagName === "BUTTON" ? submitter : null);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initToasts();
    initModal();

    // capture true pra pegar cedo
    document.addEventListener("click", onDocumentClick, true);
    document.addEventListener("submit", onDocumentSubmit, true);
  });
})();
