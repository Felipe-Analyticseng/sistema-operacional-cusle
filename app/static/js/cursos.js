(function () {
  const catalog = window.__COURSE_CATALOG__ || {};
  const form = document.getElementById("cursoForm");
  if (!form) return;

  const nome = document.getElementById("cursoNome");
  const email = document.getElementById("cursoEmail");
  const telefone = document.getElementById("cursoTelefone");
  const cpf = document.getElementById("cursoCpf");
  const dataNascimento = document.getElementById("cursoDataNascimento");
  const menor = document.getElementById("cursoMenor");
  const responsavelWrap = document.getElementById("cursoResponsavelWrap");
  const responsavelNome = document.getElementById("cursoResponsavelNome");
  const responsavelCpf = document.getElementById("cursoResponsavelCpf");
  const participa = document.getElementById("cursoParticipa");
  const perfil = document.getElementById("cursoPerfil");
  const cursoWrap = document.getElementById("cursoWrap");
  const cursoList = document.getElementById("cursoList");
  const submit = document.getElementById("cursoSubmit");
  let renderedPerfil = null;

  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function validEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((value || "").trim());
  }

  function validCpf(value) {
    const digits = onlyDigits(value);
    return digits.length === 11 && !/^(\d)\1{10}$/.test(digits);
  }

  function validPhone(value) {
    const digits = onlyDigits(value);
    return digits.length === 10 || digits.length === 11;
  }

  function validBirthDate(value) {
    if (!value) return false;
    const parsed = new Date(value + "T00:00:00");
    if (Number.isNaN(parsed.getTime())) return false;
    const today = new Date();
    if (parsed > today) return false;
    return today.getFullYear() - parsed.getFullYear() <= 120;
  }

  function selectedCourses() {
    return Array.from(cursoList.querySelectorAll('input[name="curso"]:checked')).map((input) => input.value);
  }

  function renderCourses(perfilValue) {
    const selected = new Set(selectedCourses());
    cursoList.innerHTML = "";
    renderedPerfil = perfilValue;
    const list = catalog[perfilValue] || [];
    let currentDate = null;
    let upiRendered = false;

    list.forEach((item) => {
      const isUpi = item.curso_key === "UPI";
      const itemDate = item.data || null;

      if (isUpi && !upiRendered) {
        const heading = document.createElement("div");
        heading.className = "course-date";
        heading.textContent = "UPI (Todo Mes)";
        cursoList.appendChild(heading);
        upiRendered = true;
      } else if (!isUpi && itemDate !== currentDate) {
        currentDate = itemDate;
        const heading = document.createElement("div");
        heading.className = "course-date";
        heading.textContent = currentDate;
        cursoList.appendChild(heading);
      }

      const label = document.createElement("label");
      label.className = "course-item" + (item.disponivel ? "" : " is-disabled");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.name = "curso";
      checkbox.value = item.curso_key;
      checkbox.disabled = !item.disponivel;
      checkbox.checked = selected.has(item.curso_key);

      const text = document.createElement("span");
      text.className = "course-text";
      text.textContent = item.label;

      if (!item.disponivel) {
        const tag = document.createElement("small");
        tag.textContent = "Indisponivel";
        text.appendChild(tag);
      }

      label.appendChild(checkbox);
      label.appendChild(text);
      cursoList.appendChild(label);
    });
  }

  function computeValidity() {
    const baseOk =
      nome.value.trim().length >= 3 &&
      validEmail(email.value) &&
      validPhone(telefone.value) &&
      validCpf(cpf.value) &&
      validBirthDate(dataNascimento.value) &&
      (menor.value === "sim" || menor.value === "nao");

    if (!baseOk) return false;

    if (menor.value === "sim") {
      if (responsavelNome.value.trim().length < 3) return false;
      if (!validCpf(responsavelCpf.value)) return false;
    }

    if (!(participa.value === "sim" || participa.value === "nao")) return false;
    if (!perfil.value) return false;
    if (participa.value === "nao") return true;
    return selectedCourses().length > 0;
  }

  function refreshUI() {
    const isMinor = menor.value === "sim";
    responsavelWrap.classList.toggle("hidden", !isMinor);
    responsavelNome.required = isMinor;
    responsavelCpf.required = isMinor;

    const wantsCourse = participa.value === "sim";
    cursoWrap.classList.toggle("hidden", !wantsCourse);
    if (wantsCourse && perfil.value && renderedPerfil !== perfil.value) {
      renderCourses(perfil.value);
    } else if (!wantsCourse) {
      cursoList.innerHTML = "";
      renderedPerfil = null;
    }

    submit.disabled = !computeValidity();
  }

  [nome, email, telefone, cpf, dataNascimento, menor, responsavelNome, responsavelCpf, participa, perfil].forEach((element) => {
    if (!element) return;
    element.addEventListener("input", refreshUI);
    element.addEventListener("change", refreshUI);
  });

  cursoList.addEventListener("change", () => {
    submit.disabled = !computeValidity();
  });

  refreshUI();
})();
