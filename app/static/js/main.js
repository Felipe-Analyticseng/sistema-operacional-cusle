function onlyDigits(v){return (v||'').replace(/\D/g,'')}
function maskCpf(v){v=onlyDigits(v).slice(0,11);return v.replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d{1,2})$/,'$1-$2')}
function maskPhone(v){v=onlyDigits(v).slice(0,11);return v.replace(/(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2')}
function money(v){v=onlyDigits(v); if(!v) return ''; v=(parseInt(v,10)/100).toFixed(2)+''; return v.replace('.',',').replace(/\B(?=(\d{3})+(?!\d))/g,'.')}
document.addEventListener('input',e=>{const el=e.target;if(el.dataset.mask==='cpf')el.value=maskCpf(el.value);if(el.dataset.mask==='phone')el.value=maskPhone(el.value);if(el.dataset.money!==undefined)el.value=money(el.value)});
document.addEventListener('change',e=>{const el=e.target;if(el.dataset.toggleTarget){const target=document.getElementById(el.dataset.toggleTarget);if(target)target.classList.toggle('hidden',el.value!=='Sim')}if(el.dataset.checkTarget){const target=document.getElementById(el.dataset.checkTarget);if(target)target.classList.toggle('hidden',!el.checked)}});
const qtd=document.getElementById('qtdFilhos'); const container=document.getElementById('filhosContainer');
function optionList(items){return items.map(x=>`<option value="${x}">${x||'Selecione'}</option>`).join('')}
function renderFilhos(){if(!qtd||!container)return; const n=Math.min(parseInt(qtd.value||0,10),15); const sexo=JSON.parse(container.dataset.sexo||'[]'); const etnias=JSON.parse(container.dataset.etnias||'[]'); let html=''; for(let i=0;i<n;i++){html+=`<div class="child-block"><h3>Filho ${i+1}</h3><div class="form-grid two"><label>Nome completo *<input name="filho_nome_${i}" required></label><label>Documento CPF ou RG *<input name="filho_documento_${i}" required></label><label>Data de nascimento *<input name="filho_data_nascimento_${i}" type="date" required></label><label>Sexo *<select name="filho_sexo_${i}" required>${optionList(sexo)}</select></label><label>Etnia *<select name="filho_etnia_${i}" required>${optionList(etnias)}</select></label><label>Tem deficiência? *<select name="filho_possui_deficiencia_${i}" data-toggle-target="filhoDef${i}"><option>Não</option><option>Sim</option></select></label></div><label class="hidden" id="filhoDef${i}">Descrição da deficiência<textarea name="filho_descricao_deficiencia_${i}" rows="3"></textarea></label></div>`} container.innerHTML=html}
if(qtd){qtd.addEventListener('input',renderFilhos);renderFilhos()}
setTimeout(()=>document.querySelectorAll('.toast').forEach(t=>t.style.display='none'),5500)

document.addEventListener('click', e => { const btn = e.target.closest('.js-back'); if(!btn) return; if(window.history.length > 1){ window.history.back(); } else { window.location.href = '/'; } });
document.addEventListener('click', e => {
  const editBtn = e.target.closest('.js-edit-row');
  if(editBtn){
    const row = editBtn.closest('.editable-row');
    if(row) row.classList.add('is-editing');
    return;
  }
  const cancelBtn = e.target.closest('.js-cancel-edit');
  if(cancelBtn){
    const row = cancelBtn.closest('.editable-row');
    if(row) row.classList.remove('is-editing');
  }
});
