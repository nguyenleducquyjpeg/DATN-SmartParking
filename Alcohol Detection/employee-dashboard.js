import {normalizePerson,mergePerson,revokeCard,filteredEvents,summarize,csvCell} from './employee-model.mjs?v=2';
import {confirmCardAction} from './card-confirm.mjs';

export function mountEmployees(db, {ref,onValue,get,runTransaction}, demo=false) {
  const $=id=>document.getElementById(id);
  let catalogue={}, inside={}, events={}, scans={}, version=null, selected=null;
  const fields=['maNhanVien','hoTen','boPhan','bienSo','rfid'];
  const status=text=>{$('employee-message').textContent=text;};
  const cell=(row,text)=>{const td=document.createElement('td');td.className='p-3 border-b border-slate-200';td.textContent=text??'—';row.append(td);return td;};
  function reset(){ $('employee-form').reset();$('employee-active').checked=true;selected=null;version=null;$('employee-maNhanVien').readOnly=false; }
  function renderPeople(){
    const body=$('employee-rows');body.replaceChildren();
    const q=$('employee-search').value.toLocaleLowerCase('vi');
    const people=Object.values(catalogue.nhanVien||{});
    $('employee-count').textContent=people.length;
    $('employee-inside').textContent=people.filter(p=>inside[p.rfid]===true).length;
    for(const p of people.filter(p=>`${p.maNhanVien} ${p.hoTen} ${p.bienSo} ${p.rfid}`.toLocaleLowerCase('vi').includes(q))){
      const row=document.createElement('tr');
      for(const value of [p.maNhanVien,p.hoTen,p.boPhan,p.bienSo,p.rfid,p.hoatDong?'Hiệu lực':'Ngừng',inside[p.rfid]===true?'Tại bưu cục':'Ngoài bưu cục'])cell(row,value);
      const actions=cell(row,'');
      for(const [text,fn] of [['Sửa',()=>{
        fields.forEach(f=>$('employee-'+f).value=p[f]);$('employee-active').checked=p.hoatDong;
        selected=p.maNhanVien;version=p.updatedAt??null;$('employee-maNhanVien').readOnly=true;
        status('Đang sửa '+p.maNhanVien);$('employee-hoTen').focus();
      }],['Thu hồi thẻ',async()=>{
        try{
          if(demo)throw Error('Chế độ xem thử không thay đổi dữ liệu.');
          if(!p.rfid)throw Error('Hồ sơ này không còn thẻ.');
          if(!await confirmCardAction(`Thu hồi thẻ ${p.rfid} của ${p.hoTen}? Hồ sơ sẽ ngừng hiệu lực, gỡ UID và giữ nguyên lịch sử. Dữ liệu vật lý trên thẻ chưa bị xóa.`))return;
          if((await get(ref(db,'XeTrongBai/'+p.rfid))).val())throw Error('Xe còn tại bưu cục. Hoàn tất lượt ra trước khi thu hồi thẻ.');
          const result=await runTransaction(ref(db,'HoSoNhanVien'),c=>revokeCard(c,p.maNhanVien,p.updatedAt,Date.now()),{applyLocally:false});
          if(!result.committed)throw Error('Chưa thu hồi được thẻ.');
          reset();status('Đã thu hồi thẻ '+p.rfid+'. Có thể đặt thẻ lên trạm để xóa dữ liệu; lịch sử nhân viên được giữ nguyên.');
        }catch(e){status(e.message);}
      }],['Lịch sử',()=>{
        $('employee-log-search').value=p.maNhanVien;renderEvents();$('employee-history').scrollIntoView({behavior:'smooth'});
      }]]){const button=document.createElement('button');button.type='button';button.textContent=text;button.className='text-teal-700 underline mr-3';button.onclick=fn;actions.append(button);}
      body.append(row);
    }
    if(!body.children.length){const row=document.createElement('tr');cell(row,'Chưa có nhân viên phù hợp.').colSpan=8;body.append(row);}
  }
  function renderEvents(){
    const rows=filteredEvents(events,$('employee-log-search').value,$('employee-day').value);
    const c=summarize(rows);
    $('employee-summary').textContent=`${c.IN} lượt vào · ${c.OUT} lượt ra · ${c.PASS} lần đo đạt · ${c.FAIL} không đạt · ${c.ERROR} lỗi đo · ${c.DENIED} từ chối`;
    const body=$('employee-log-rows');body.replaceChildren();
    const labels={IN:'Xe vào',OUT:'Xe ra',PASS:'Đo đạt',FAIL:'Đo không đạt',ERROR:'Lỗi đo',DENIED:'Từ chối'};
    for(const e of rows.slice(0,300)){
      const row=document.createElement('tr');
      const time=Number(e.timestamp)?new Date(Number(e.timestamp)).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Chưa có thời gian';
      for(const v of [time,e.maNhanVien,e.hoTen,e.bienSo,labels[e.loai]||e.loai,e.adc==null?'—':`${e.adc} ADC`,e.lyDo||''])cell(row,v);
      body.append(row);
    }
    if(!body.children.length){const row=document.createElement('tr');cell(row,'Chưa có sự kiện. Lịch sử sẽ xuất hiện khi nhân viên thực hiện vào/ra hoặc kiểm tra nồng độ cồn.').colSpan=7;body.append(row);}
  }
  function renderScans(){
    const latest=Object.values(scans).filter(e=>e&&typeof e==='object').sort((a,b)=>(b.timestamp||0)-(a.timestamp||0))[0];
    if(!latest){$('employee-last-scan').textContent='Chưa có lần quét RFID mới.';return;}
    const person=catalogue.nhanVien?.[catalogue.theRFID?.[latest.rfid]];
    $('employee-last-scan').textContent=`Lần quét gần nhất: ${latest.rfid} · ${latest.huong||''} · ${person?person.hoTen:'Chưa đăng ký'} · ${new Date(latest.timestamp).toLocaleString('vi-VN')}`;
    $('employee-use-card').disabled=Date.now()-latest.timestamp>90000;
    $('employee-use-card').onclick=()=>{
      if(Date.now()-latest.timestamp>90000){status('Thẻ đã quét quá 90 giây. Vui lòng quét lại.');return;}
      $('employee-rfid').value=latest.rfid;
    };
  }
  $('employee-form').onsubmit=async event=>{
    event.preventDefault();const button=$('employee-save');button.disabled=true;
    try{
      if(demo)throw Error('Chế độ xem thử: không ghi dữ liệu Firebase.');
      const input=Object.fromEntries(fields.map(f=>[f,$('employee-'+f).value]));
      input.hoatDong=$('employee-active').checked;
      const person=normalizePerson(input), old=catalogue.nhanVien?.[selected];
      if(old&&(old.rfid!==person.rfid||old.bienSo!==person.bienSo)){
        if((await get(ref(db,'XeTrongBai/'+old.rfid))).val())throw Error('Xe còn trong bãi: chưa được đổi thẻ/biển số.');
      }
      person.updatedAt=Date.now();
      await runTransaction(ref(db,'HoSoNhanVien'),current=>mergePerson(current,person,version),{applyLocally:false});
      reset();status('Đã lưu hồ sơ nhân viên.');
    }catch(error){status('Không lưu được: '+error.message);}
    finally{button.disabled=false;}
  };
  $('employee-reset').onclick=()=>{reset();status('Nhập hồ sơ mới.');};
  $('employee-search').oninput=renderPeople;
  $('employee-log-search').oninput=renderEvents;$('employee-day').onchange=renderEvents;
  $('employee-export').onclick=()=>{
    const keys=['timestamp','maNhanVien','hoTen','bienSo','rfid','loai','adc','nguongADC','lyDo'];
    const rows=filteredEvents(events,$('employee-log-search').value,$('employee-day').value);
    const csv='\ufeff'+[keys,...rows.map(e=>keys.map(k=>e[k]))].map(row=>row.map(csvCell).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download='theo-doi-nhan-vien.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  const error=e=>status('Firebase: '+e.message+' — kiểm tra kết nối/quyền truy cập.');
  if(demo){status('Chế độ xem thử — không lưu thay đổi.');renderPeople();renderEvents();renderScans();}
  else{
    onValue(ref(db,'HoSoNhanVien'),s=>{catalogue=s.val()||{};renderPeople();renderScans();},error);
    onValue(ref(db,'XeTrongBai'),s=>{inside=s.val()||{};renderPeople();},error);
    onValue(ref(db,'NhatKyNhanVien'),s=>{events=s.val()||{};renderEvents();},error);
    onValue(ref(db,'SuKienRFID'),s=>{scans=s.val()||{};renderScans();},error);
  }
}
