import {STATION,JOB_LABELS,ERRORS,makeJob,makeEraseJob,lockErase,unlockErase,recoverErase,enqueueJob} from './card-writer-model.mjs?v=3';
import {confirmCardAction} from './card-confirm.mjs';
export function mountCardWriter(db,{ref,onValue,get,runTransaction},demo=false){
  const $=id=>document.getElementById(id),base='TramCapThe/'+STATION;
  let people={},station={},saving=false,offset=0;
  const now=()=>Date.now()+offset;
  const message=text=>{$('writer-message').textContent=text;};
  function render(){
    const p=people[$('writer-person').value];
    $('writer-profile').textContent=p?`${p.maNhanVien} · ${p.hoTen} · Xe ${p.bienSo} · UID ${p.rfid}`:'Chọn nhân viên đã lưu hồ sơ để ghi thẻ.';
    const online=station.heartbeat&&Math.abs(now()-station.heartbeat.timestamp)<30000;
    $('writer-online').textContent=demo?'Chế độ xem thử':station.heartbeat?.simulated?'Trạm mô phỏng (không phải thiết bị thật)':online?'Trạm đang kết nối':'Chưa có phản hồi từ trạm';
    const scan=station.scan;
    $('writer-card').textContent=scan?`UID tại trạm: ${scan.rfid} · ${scan.cardType} · ${new Date(scan.timestamp).toLocaleTimeString('vi-VN')}`:'Đặt thẻ lên RC522 của trạm cấp thẻ.';
    $('writer-copy').disabled=demo||!scan||Math.abs(now()-scan.timestamp)>60000;
    const job=station.job;
    const resultLabel=job?.status==='SUCCESS'&&!(job.verified===true&&job.bytesVerified===96)?'Chưa có xác nhận đọc lại đầy đủ':JOB_LABELS[job?.status]||job?.status;
    $('writer-result').textContent=job?`${job.operation==='ERASE'?'Xóa dữ liệu thẻ':'Ghi thẻ'}: ${job.operation==='ERASE'&&job.status==='SUCCESS'&&job.verified===true?'Đã xóa và đọc lại xác nhận':resultLabel} · UID ${job.rfid} · ${job.maNhanVien}${job.error?' — '+(ERRORS[job.error]||job.error):''}${job.status==='PENDING'&&now()>job.expiresAt?' — Đã hết thời gian chờ; có thể gửi yêu cầu mới.':''}`:'Chưa có yêu cầu ghi thẻ.';
    $('writer-send').disabled=demo||saving||!p||!online;
    $('writer-erase').disabled=demo||saving||!scan||!online;
  }
  $('writer-person').onchange=render;
  $('writer-erase').onclick=async()=>{
    let job=null,locked=false;
    saving=true;render();
    try{
      if(demo)throw Error('Chế độ xem thử không xóa thẻ.');
      const [c,s,h]=await Promise.all(['HoSoNhanVien',base+'/scan',base+'/heartbeat'].map(path=>get(ref(db,path))));
      job=makeEraseJob(c.val(),s.val(),h.val(),now(),crypto.randomUUID());
      if(c.val()?.theThuHoi?.[job.rfid]?.eraseJob){
        const previous=(await get(ref(db,base+'/job'))).val();
        await runTransaction(ref(db,'HoSoNhanVien'),c=>recoverErase(c,job.rfid,previous,now()),{applyLocally:false});
      }
      if(!await confirmCardAction(`Xóa mã nhân viên và biển số trên thẻ ${job.rfid} đã thu hồi từ ${job.hoTen}? Giữ thẻ trên trạm đến khi đọc lại xác nhận. UID và lịch sử không bị xóa.`))return;
      // Reserve this UID in the same catalogue transaction used by registration.
      const reserved=await runTransaction(ref(db,'HoSoNhanVien'),c=>lockErase(c,job),{applyLocally:false});
      if(!reserved.committed)throw Error('Chưa giữ được thẻ để xóa.');locked=true;
      const result=await runTransaction(ref(db,base+'/job'),c=>enqueueJob(c,job,now()),{applyLocally:false});
      if(!result.committed)throw Error('Chưa gửi được yêu cầu xóa.');
      message('Đã gửi yêu cầu xóa. Giữ nguyên thẻ trên trạm đến khi xác nhận.');
    }catch(e){
      message(e.message);
      if(locked)try{
        const current=(await get(ref(db,base+'/job'))).val();
        if(current?.id!==job.id)await runTransaction(ref(db,'HoSoNhanVien'),c=>unlockErase(c,{...job,status:'NOT_SENT'}));
      }catch{message('Chưa xác định được trạng thái gửi lệnh. Giữ nguyên thẻ, kiểm tra kết nối trước khi cấp lại.');}
    }finally{saving=false;render();}
  };
  $('writer-copy').onclick=()=>{
    if(!station.scan||Math.abs(now()-station.scan.timestamp)>60000){message('Quét lại thẻ tại trạm cấp thẻ.');return;}
    $('employee-rfid').value=station.scan.rfid;
    message('Đã điền UID vào biểu mẫu đăng ký phía trên. Lưu hồ sơ trước khi ghi thẻ.');
  };
  $('writer-send').onclick=async()=>{
    saving=true;render();
    try{
      if(demo)throw Error('Chế độ xem thử không ghi Firebase hoặc thẻ.');
      const id=$('writer-person').value;
      const p=(await get(ref(db,'HoSoNhanVien/nhanVien/'+id))).val();
      const [scan,heartbeat]=await Promise.all([get(ref(db,base+'/scan')),get(ref(db,base+'/heartbeat'))]);
      const latest={scan:scan.val(),heartbeat:heartbeat.val()};
      const job=makeJob(p,latest.scan,latest.heartbeat,now(),crypto.randomUUID());
      const result=await runTransaction(ref(db,base+'/job'),current=>enqueueJob(current,job,now()),{applyLocally:false});
      if(!result.committed)throw Error('Chưa tạo được yêu cầu ghi.');
      message('Đã gửi yêu cầu. Giữ đúng thẻ trên RC522 đến khi báo thành công.');
    }catch(e){message(e.message);}finally{saving=false;render();}
  };
  if(!demo){
    const error=e=>message('Không truy cập được trạm cấp thẻ: '+e.message);
    onValue(ref(db,'.info/serverTimeOffset'),s=>{offset=Number(s.val())||0;},error);
    onValue(ref(db,'HoSoNhanVien/nhanVien'),s=>{
      people=s.val()||{};const selected=$('writer-person').value;
      $('writer-person').replaceChildren(new Option('Chọn nhân viên đã đăng ký',''));
      Object.values(people).filter(p=>p.hoatDong===true).sort((a,b)=>a.maNhanVien.localeCompare(b.maNhanVien)).forEach(p=>$('writer-person').add(new Option(`${p.maNhanVien} — ${p.hoTen}`,p.maNhanVien)));
      if(people[selected])$('writer-person').value=selected;render();
    },error);
    for(const key of ['heartbeat','scan','job'])onValue(ref(db,base+'/'+key),s=>{
      station[key]=s.val();render();
      const j=station[key];
      if(key==='job'&&j?.operation==='ERASE'&&['SUCCESS','ERROR','EXPIRED'].includes(j.status))runTransaction(ref(db,'HoSoNhanVien'),c=>unlockErase(c,j),{applyLocally:false}).catch(error);
    },error);
  }
  render();const timer=setInterval(render,2000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}
