import {filteredEvents,summarize} from './employee-model.mjs';

export function mountOverview(db,{ref,onValue},demo=false){
  const $=id=>document.getElementById(id);
  let people={},inside={},events={},levelChart,userChart;
  const labels={PASS:'Đạt',FAIL:'Không đạt',ERROR:'Lỗi đo'};
  function cell(row,value){const td=document.createElement('td');td.className='p-4 border-b border-slate-100';td.textContent=value??'—';row.append(td);return td;}
  function stamp(e){return e.timestamp?new Date(Number(e.timestamp)).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Chưa có thời gian';}
  function empty(container,text,columns){
    const node=document.createElement(columns?'tr':'div');const content=columns?cell(node,text):node;
    content.className='empty-state';if(columns)content.colSpan=columns;else content.textContent=text;container.append(node);
  }
  function render(){
    const all=filteredEvents(events), tests=all.filter(e=>Object.hasOwn(labels,e.loai)), count=summarize(tests);
    $('overview-employees').textContent=Object.keys(people).length;
    $('overview-inside').textContent=Object.values(people).filter(p=>inside[p.rfid]===true).length;
    $('overview-tests').textContent=tests.length;$('overview-fails').textContent=count.FAIL;
    const body=$('overview-test-rows');body.replaceChildren();
    for(const e of tests.slice(0,30)){
      const row=document.createElement('tr');cell(row,stamp(e));cell(row,e.hoTen||e.maNhanVien||'Chưa gắn nhân viên');cell(row,e.bienSo);
      cell(row,e.adc==null?'—':`${Number(e.adc).toLocaleString('vi-VN',{maximumFractionDigits:1})} ADC`);
      const badge=document.createElement('span');badge.className='badge badge-'+e.loai.toLowerCase();badge.textContent=labels[e.loai];cell(row,'').append(badge);body.append(row);
    }
    if(!tests.length)empty(body,'Chưa có kết quả kiểm tra nồng độ cồn.',5);
    const attention=$('overview-attention');attention.replaceChildren();
    // Recent failed/error measurements, not an employee blacklist or disciplinary status.
    const alerts=tests.filter(e=>e.loai!=='PASS').slice(0,8);
    for(const e of alerts){
      const item=document.createElement('div');item.className='attention-item';
      const strong=document.createElement('strong');strong.textContent=e.hoTen||e.maNhanVien||e.rfid||'Chưa gắn nhân viên';
      const badge=document.createElement('span');badge.className='badge badge-'+e.loai.toLowerCase()+' ml-2';badge.textContent=labels[e.loai];
      const detail=document.createElement('p');detail.textContent=`${e.bienSo||'Chưa có biển số'} · ${stamp(e)}`;
      item.append(strong,badge,detail);attention.append(item);
    }
    if(!alerts.length)empty(attention,'Chưa có lần đo không đạt hoặc lỗi đo.');
    if(typeof Chart==='undefined'){
      $('chart-note').textContent='Chưa tải được biểu đồ. Số liệu vẫn được hiển thị tại Tổng quan và Theo dõi nhân viên.';return;
    }
    if(!levelChart){
      Chart.defaults.color='#64748b';Chart.defaults.font.family="'Segoe UI', Arial, sans-serif";
      levelChart=new Chart($('levelChart'),{type:'doughnut',data:{labels:['Đạt','Không đạt','Lỗi đo'],datasets:[{data:[0,0,0],backgroundColor:['#178d78','#df775b','#e3b64f'],borderWidth:0}]},options:{cutout:'72%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,padding:24}}}}});
      userChart=new Chart($('userChart'),{type:'bar',data:{labels:[],datasets:[{label:'Số lần kiểm tra',data:[],backgroundColor:'#3f829a',borderRadius:5,maxBarThickness:38}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0},grid:{color:'#edf1f5'}},x:{grid:{display:false}}}}});
    }
    levelChart.data.datasets[0].data=[count.PASS,count.FAIL,count.ERROR];levelChart.update();
    const totals=new Map();
    for(const e of tests){const key=e.maNhanVien||e.rfid||'UNKNOWN';const current=totals.get(key)||{label:`${e.maNhanVien||e.rfid||'Chưa rõ'} · ${e.hoTen||''}`,count:0};current.count++;totals.set(key,current);}
    const top=[...totals.values()].sort((a,b)=>b.count-a.count).slice(0,10);
    userChart.data.labels=top.map(x=>x.label);userChart.data.datasets[0].data=top.map(x=>x.count);userChart.update();
    $('chart-note').textContent=tests.length?'Tổng hợp toàn bộ lịch sử kiểm tra. Mỗi lần đo lại được tính riêng.':'Chưa có dữ liệu kiểm tra để hiển thị trên biểu đồ.';
  }
  render();
  if(demo){$('connection-label').textContent='Chế độ xem thử';return;}
  const error=e=>{$('connection-label').textContent='Không đọc được dữ liệu';$('overview-error').textContent='Không tải được dữ liệu: '+e.message;};
  onValue(ref(db,'.info/connected'),s=>{$('connection-label').textContent=s.val()?'Đã kết nối dữ liệu':'Đang kết nối…';$('connection-dot').style.background=s.val()?'#178d78':'#94a3b8';},error);
  onValue(ref(db,'HoSoNhanVien/nhanVien'),s=>{people=s.val()||{};render();},error);
  onValue(ref(db,'XeTrongBai'),s=>{inside=s.val()||{};render();},error);
  onValue(ref(db,'NhatKyNhanVien'),s=>{events=s.val()||{};render();},error);
}
