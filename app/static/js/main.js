function onlyDigits(v){return (v||'').replace(/\D/g,'')}
function maskCpf(v){v=onlyDigits(v).slice(0,11);return v.replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d{1,2})$/,'$1-$2')}
function maskPhone(v){v=onlyDigits(v).slice(0,11);return v.replace(/(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2')}
function money(v){v=onlyDigits(v); if(!v) return ''; v=(parseInt(v,10)/100).toFixed(2)+''; return v.replace('.',',').replace(/\B(?=(\d{3})+(?!\d))/g,'.')}
document.addEventListener('input',e=>{const el=e.target;if(el.dataset.mask==='cpf')el.value=maskCpf(el.value);if(el.dataset.mask==='phone')el.value=maskPhone(el.value);if(el.dataset.money!==undefined)el.value=money(el.value)});
document.querySelectorAll('[data-mask="cpf"]').forEach(el=>{el.value=maskCpf(el.value)});
document.querySelectorAll('[data-mask="phone"]').forEach(el=>{el.value=maskPhone(el.value)});
document.addEventListener('change',e=>{const el=e.target;if(el.dataset.toggleTarget){const target=document.getElementById(el.dataset.toggleTarget);if(target)target.classList.toggle('hidden',el.value!=='Sim')}if(el.dataset.checkTarget){const target=document.getElementById(el.dataset.checkTarget);if(target)target.classList.toggle('hidden',!el.checked)}});
const qtd=document.getElementById('qtdFilhos'); const container=document.getElementById('filhosContainer');
function optionList(items){return items.map(x=>`<option value="${x}">${x||'Selecione'}</option>`).join('')}
function renderFilhos(){if(!qtd||!container)return; const n=Math.min(parseInt(qtd.value||0,10),15); const sexo=JSON.parse(container.dataset.sexo||'[]'); const etnias=JSON.parse(container.dataset.etnias||'[]'); let html=''; for(let i=0;i<n;i++){html+=`<div class="child-block"><h3>Filho ${i+1}</h3><div class="form-grid two"><label>Nome completo *<input name="filho_nome_${i}" required></label><label>Documento CPF ou RG *<input name="filho_documento_${i}" required></label><label>Data de nascimento *<input name="filho_data_nascimento_${i}" type="date" required></label><label>Sexo *<select name="filho_sexo_${i}" required>${optionList(sexo)}</select></label><label>Etnia *<select name="filho_etnia_${i}" required>${optionList(etnias)}</select></label><label>Tem deficiência? *<select name="filho_possui_deficiencia_${i}" data-toggle-target="filhoDef${i}"><option>Não</option><option>Sim</option></select></label></div><label class="hidden" id="filhoDef${i}">Descrição da deficiência<textarea name="filho_descricao_deficiencia_${i}" rows="3"></textarea></label><div class="form-grid two"><label>Problema de saúde<textarea name="filho_problema_saude_${i}" rows="2"></textarea></label><label>Alergia<input name="filho_alergia_${i}"></label><label>Medicação contínua<textarea name="filho_medicacao_continua_${i}" rows="2"></textarea></label></div></div>`} container.innerHTML=html}
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

const signatureForm = document.getElementById('signatureForm');
const signatureCanvas = document.getElementById('signatureCanvas');
function drawTypedSignature(){
  if(!signatureCanvas)return;
  const input = document.getElementById('typedName');
  const hidden = document.getElementById('signatureData');
  const name = (input && input.value.trim()) || 'Assinatura';
  const ctx = signatureCanvas.getContext('2d');
  const w = signatureCanvas.width;
  const h = signatureCanvas.height;
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0,0,w,h);
  ctx.strokeStyle = 'rgba(72,111,167,.22)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(60,155);
  ctx.bezierCurveTo(180,195,420,190,w-70,150);
  ctx.stroke();
  ctx.fillStyle = '#172033';
  ctx.font = '64px Georgia, Times New Roman, serif';
  ctx.textAlign = 'center';
  ctx.fillText(name, w/2, 128, w-90);
  ctx.fillStyle = 'rgba(23,32,51,.62)';
  ctx.font = '14px Inter, Segoe UI, Arial, sans-serif';
  ctx.fillText('Assinatura eletrônica CUSLE', w/2, 184);
  if(hidden) hidden.value = signatureCanvas.toDataURL('image/png');
}
if(signatureCanvas){
  drawTypedSignature();
  const typedName = document.getElementById('typedName');
  const redraw = document.getElementById('redrawSignature');
  if(typedName) typedName.addEventListener('input', drawTypedSignature);
  if(redraw) redraw.addEventListener('click', drawTypedSignature);
}
if(signatureForm){
  signatureForm.addEventListener('submit', () => drawTypedSignature());
}

document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-copy-target]');
  if(!btn)return;
  const target = document.getElementById(btn.dataset.copyTarget);
  if(!target)return;
  try{
    await navigator.clipboard.writeText(target.value || target.textContent || '');
    btn.textContent = 'Link copiado';
  }catch(err){
    target.select && target.select();
    document.execCommand('copy');
    btn.textContent = 'Link copiado';
  }
});
