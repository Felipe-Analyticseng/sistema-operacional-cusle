const chartDefaults={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{enabled:true}},scales:{x:{grid:{display:false},ticks:{maxRotation:90,minRotation:90}},y:{grid:{color:'#edf2f7'},beginAtZero:true,ticks:{precision:0}}}};
function palette(){return ['#486FA7','#F26215','#6B8DB3','#AEC7D4','#F6A66A','#12B76A','#F04438']}
function makeBar(id,labels,data,label,indexAxis='x'){
  const el=document.getElementById(id); if(!el)return;
  new Chart(el,{type:'bar',data:{labels,datasets:[{label,data,backgroundColor:palette()[0],borderRadius:10,maxBarThickness:72}]},options:{...chartDefaults,indexAxis}})
}
fetch('/api/admin/dashboard').then(r=>r.json()).then(d=>{
  makeBar('chartFaixas',(d.faixas||[]).map(x=>x.faixa),(d.faixas||[]).map(x=>x.quantidade),'Pessoas PAC','x');
}).catch(()=>{});
