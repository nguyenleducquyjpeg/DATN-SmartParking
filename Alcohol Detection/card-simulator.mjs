import {STATION} from './card-writer-model.mjs?v=2';

// In-memory adapter only: this module never imports Firebase or uses network APIs.
export function createSimulator({schedule=setTimeout, now=Date.now}={}) {
  const base='TramCapThe/'+STATION;
  let data={},card=null,fail=false;
  const listeners=new Map(), cards=new Map();
  const read=path=>path.split('/').reduce((v,k)=>v?.[k],data)??null;
  const snapshot=path=>({val:()=>structuredClone(read(path)),exists:()=>read(path)!==null});
  function put(path,value){
    const parts=path.split('/');let node=data;
    for(const key of parts.slice(0,-1))node=node[key]??={};
    node[parts.at(-1)]=structuredClone(value);
    for(const [key,callbacks] of listeners)if(key===path||key.startsWith(path+'/')||path.startsWith(key+'/'))for(const fn of callbacks)fn(snapshot(key));
  }
  function finish(job,status,error){put(base+'/job',{...job,status,error:error||null,simulated:true,...(status==='SUCCESS'?{verified:true,bytesVerified:96}:{})});}
  function check(job){
    if(!card||card.rfid!==job.rfid)return 'WRONG_CARD';
    if(job.operation==='ERASE'){
      const c=read('HoSoNhanVien'),r=c?.theThuHoi?.[job.rfid];
      return r?.eraseJob===job.id&&r.revokedAt===job.profileVersion&&!c.theRFID?.[job.rfid]&&!Object.values(c.nhanVien||{}).some(p=>p.rfid===job.rfid)?null:'PROFILE_CHANGED';
    }
    const p=read('HoSoNhanVien/nhanVien/'+job.maNhanVien);
    if(!p?.hoatDong||p.rfid!==job.rfid||p.bienSo!==job.bienSo||p.updatedAt!==job.profileVersion)return 'PROFILE_CHANGED';
    return null;
  }
  function process(job){
    schedule(()=>{
      const error=check(job);if(error){finish(job,'ERROR',error);return;}
      put(base+'/job',{...job,status:'WRITING',simulated:true});
      schedule(()=>{
        const error=check(job);if(error){finish(job,'ERROR',error);return;}
        if(job.operation==='ERASE')cards.delete(job.rfid);
        else cards.set(job.rfid,{maNhanVien:job.maNhanVien,bienSo:job.bienSo});
        put(base+'/job',{...job,status:'VERIFYING',simulated:true});
        schedule(()=>finish(job,check(job)||fail?'ERROR':'SUCCESS',check(job)||(fail?'VERIFY_FAILED':null)),900);
      },900);
    },400);
  }
  const api={
    ref:(_db,path)=>path,
    onValue:(path,callback)=>{if(!listeners.has(path))listeners.set(path,new Set());listeners.get(path).add(callback);callback(snapshot(path));return()=>listeners.get(path).delete(callback);},
    get:async path=>snapshot(path),
    runTransaction:async(path,update)=>{
      const value=update(structuredClone(read(path)));
      if(value===undefined)return {committed:false};
      put(path,value);
      if(path===base+'/job'&&value.status==='PENDING')process(value);
      return {committed:true,snapshot:snapshot(path)};
    }
  };
  function heartbeat(){put(base+'/heartbeat',{timestamp:now(),simulated:true});if(card)put(base+'/scan',{...card,timestamp:now()});}
  function scan(uid){
    uid=uid.trim().toUpperCase().replace(/[\s:-]/g,'');
    if(!/^(?:[A-F0-9]{8}|[A-F0-9]{14}|[A-F0-9]{20})$/.test(uid))throw Error('UID mô phỏng cần 8, 14 hoặc 20 ký tự hex.');
    card={rfid:uid,cardType:'MIFARE_1K'};heartbeat();return uid;
  }
  heartbeat();
  return {api,scan,heartbeat,remove(){card=null;put(base+'/scan',null);},setFailure(value){fail=value;},readCard:uid=>structuredClone(cards.get(uid)||null)};
}

export function mountSimulator(sim){
  const panel=document.createElement('section');
  panel.className='bg-amber-50 border border-amber-300 rounded-xl p-5 mb-5';
  panel.innerHTML=`<h2 class="text-xl font-bold">MÔ PHỎNG TRẠM CẤP THẺ</h2>
    <p class="my-3">Không cần ESP32. Hồ sơ và thẻ thử chỉ nằm trong bộ nhớ trang này; tải lại sẽ xóa dữ liệu thử. Không gửi Firebase, không điều khiển cổng và không ghi thẻ vật lý.</p>
    <p class="my-3">1. Quét thẻ giả → 2. Lấy UID vào form, nhập và lưu hồ sơ → 3. Chọn hồ sơ trong mục Cấp & ghi thẻ → 4. Ghi và xem kết quả.</p>
    <label for="sim-uid">UID thẻ giả (có thể giữ giá trị mẫu)</label>
    <input id="sim-uid" value="A31695DC" class="border rounded-lg p-3 m-2" />
    <button id="sim-scan" type="button" class="bg-teal-700 text-white rounded-lg p-3 m-2">Quét thẻ giả</button>
    <button id="sim-remove" type="button" class="border rounded-lg p-3 m-2">Rút thẻ giả</button>
    <label class="block my-3"><input id="sim-fail" type="checkbox" /> Giả lập lỗi đọc lại sau khi ghi</label>
    <p id="sim-status" role="status">Chưa đặt thẻ giả lên trạm.</p>
    <pre id="sim-memory" class="whitespace-pre-wrap mt-3"></pre>`;
  document.getElementById('content-tab-nhanvien').prepend(panel);
  const $=id=>document.getElementById(id);
  $('employee-message').textContent='Sẵn sàng đăng ký thử — dữ liệu chỉ tồn tại trong trang mô phỏng.';
  const banner=document.createElement('p');banner.textContent='MÔ PHỎNG CẤP THẺ — dữ liệu thử, không kết nối thiết bị thật';banner.className='bg-amber-50 text-amber-800 border border-amber-300 p-3';document.querySelector('main').prepend(banner);
  const uidBox=$('employee-rfid');uidBox.placeholder='Bấm Quét thẻ giả, rồi Lấy UID';
  const copy=document.createElement('button');copy.type='button';copy.textContent='Lấy UID từ trạm cấp thẻ';copy.className='border rounded-lg p-2 mt-2';
  uidBox.parentElement.append(copy);copy.onclick=()=>$('writer-copy').click();
  $('sim-scan').onclick=()=>{try{const uid=sim.scan($('sim-uid').value);$('sim-status').textContent=`Đã quét thẻ giả ${uid}. Bấm Lấy UID từ trạm cấp thẻ cạnh ô UID để đăng ký.`;}catch(e){$('sim-status').textContent=e.message;}};
  $('sim-remove').onclick=()=>{sim.remove();$('sim-status').textContent='Đã rút thẻ giả.';};
  $('sim-fail').onchange=()=>sim.setFailure($('sim-fail').checked);
  sim.api.onValue('TramCapThe/'+STATION+'/job',s=>{
    const job=s.val();if(!job)return;
    $('sim-memory').textContent='Kết quả mô phỏng: '+job.status+'\nDữ liệu thẻ giả: '+JSON.stringify(sim.readCard(job.rfid),null,2);
  });
  const timer=setInterval(()=>sim.heartbeat(),5000);
  window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}
