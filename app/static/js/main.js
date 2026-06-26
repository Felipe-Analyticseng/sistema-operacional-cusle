function onlyDigits(value) {
  return (value || "").replace(/\D/g, "");
}

function maskCpf(value) {
  value = onlyDigits(value).slice(0, 11);
  return value
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function maskPhone(value) {
  value = onlyDigits(value).slice(0, 11);
  return value.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
}

function money(value) {
  value = onlyDigits(value);
  if (!value) return "";
  value = (parseInt(value, 10) / 100).toFixed(2);
  return value.replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

const todayIso = new Date().toISOString().slice(0, 10);
document.querySelectorAll('input[type="date"]:not([max])').forEach((element) => {
  element.max = todayIso;
});

document.addEventListener("input", (event) => {
  const element = event.target;
  if (element.dataset.mask === "cpf") element.value = maskCpf(element.value);
  if (element.dataset.mask === "phone") element.value = maskPhone(element.value);
  if (element.dataset.money !== undefined) element.value = money(element.value);
});

document.querySelectorAll('[data-mask="cpf"]').forEach((element) => {
  element.value = maskCpf(element.value);
});

document.querySelectorAll('[data-mask="phone"]').forEach((element) => {
  element.value = maskPhone(element.value);
});

document.addEventListener("change", (event) => {
  const element = event.target;
  if (element.dataset.toggleTarget) {
    const target = document.getElementById(element.dataset.toggleTarget);
    if (target) target.classList.toggle("hidden", element.value !== "Sim");
  }
  if (element.dataset.checkTarget) {
    const target = document.getElementById(element.dataset.checkTarget);
    if (target) target.classList.toggle("hidden", !element.checked);
  }
});

const qtd = document.getElementById("qtdFilhos");
const container = document.getElementById("filhosContainer");

function optionList(items) {
  return items.map((item) => `<option value="${item}">${item || "Selecione"}</option>`).join("");
}

function renderFilhos() {
  if (!qtd || !container) return;
  const count = Math.min(parseInt(qtd.value || 0, 10), 15);
  const sexo = JSON.parse(container.dataset.sexo || "[]");
  const etnias = JSON.parse(container.dataset.etnias || "[]");
  let html = "";
  for (let index = 0; index < count; index += 1) {
    html += `<div class="child-block"><h3>Filho ${index + 1}</h3><div class="form-grid two"><label>Nome completo *<input name="filho_nome_${index}" required></label><label>Documento CPF ou RG *<input name="filho_documento_${index}" required></label><label>Data de nascimento *<input name="filho_data_nascimento_${index}" type="date" max="${todayIso}" required></label><label>Sexo *<select name="filho_sexo_${index}" required>${optionList(sexo)}</select></label><label>Etnia *<select name="filho_etnia_${index}" required>${optionList(etnias)}</select></label><label>Tem deficiencia? *<select name="filho_possui_deficiencia_${index}" data-toggle-target="filhoDef${index}"><option>Nao</option><option>Sim</option></select></label></div><label class="hidden" id="filhoDef${index}">Descricao da deficiencia<textarea name="filho_descricao_deficiencia_${index}" rows="3"></textarea></label><div class="form-grid two"><label>Problema de saude<textarea name="filho_problema_saude_${index}" rows="2"></textarea></label><label>Alergia<input name="filho_alergia_${index}"></label><label>Medicacao continua<textarea name="filho_medicacao_continua_${index}" rows="2"></textarea></label></div></div>`;
  }
  container.innerHTML = html;
}

if (qtd) {
  qtd.addEventListener("input", renderFilhos);
  renderFilhos();
}

setTimeout(() => document.querySelectorAll(".toast").forEach((toast) => {
  toast.style.display = "none";
}), 5500);

document.addEventListener("click", (event) => {
  const button = event.target.closest(".js-back");
  if (!button) return;
  if (window.history.length > 1) {
    window.history.back();
  } else {
    window.location.href = "/";
  }
});

document.addEventListener("click", (event) => {
  const editButton = event.target.closest(".js-edit-row");
  if (editButton) {
    const row = editButton.closest(".editable-row");
    if (row) row.classList.add("is-editing");
    return;
  }

  const cancelButton = event.target.closest(".js-cancel-edit");
  if (cancelButton) {
    const row = cancelButton.closest(".editable-row");
    if (row) row.classList.remove("is-editing");
  }
});

const signatureForm = document.getElementById("signatureForm");
const signatureCanvas = document.getElementById("signatureCanvas");

function drawTypedSignature() {
  if (!signatureCanvas) return;
  const input = document.getElementById("typedName");
  const hidden = document.getElementById("signatureData");
  const name = (input && input.value.trim()) || "Assinatura";
  const ctx = signatureCanvas.getContext("2d");
  const width = signatureCanvas.width;
  const height = signatureCanvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(72,111,167,.22)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(60, 155);
  ctx.bezierCurveTo(180, 195, 420, 190, width - 70, 150);
  ctx.stroke();
  ctx.fillStyle = "#172033";
  ctx.font = "64px Georgia, Times New Roman, serif";
  ctx.textAlign = "center";
  ctx.fillText(name, width / 2, 128, width - 90);
  ctx.fillStyle = "rgba(23,32,51,.62)";
  ctx.font = "14px Inter, Segoe UI, Arial, sans-serif";
  ctx.fillText("Assinatura eletronica CUSLE", width / 2, 184);
  if (hidden) hidden.value = signatureCanvas.toDataURL("image/png");
}

if (signatureCanvas) {
  drawTypedSignature();
  const typedName = document.getElementById("typedName");
  const redraw = document.getElementById("redrawSignature");
  if (typedName) typedName.addEventListener("input", drawTypedSignature);
  if (redraw) redraw.addEventListener("click", drawTypedSignature);
}

if (signatureForm) {
  signatureForm.addEventListener("submit", () => drawTypedSignature());
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-target]");
  if (!button) return;
  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;
  try {
    await navigator.clipboard.writeText(target.value || target.textContent || "");
    button.textContent = "Link copiado";
  } catch (err) {
    if (target.select) target.select();
    document.execCommand("copy");
    button.textContent = "Link copiado";
  }
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-close-modal]");
  if (!button) return;
  const modal = document.getElementById(button.dataset.closeModal);
  if (modal) modal.hidden = true;
});
