export function normalizePerson(input) {
  const p = {maNhanVien:input.maNhanVien.trim().toUpperCase(), hoTen:input.hoTen.trim(),
    boPhan:input.boPhan.trim(), bienSo:input.bienSo.toUpperCase().replace(/[\s.-]/g,''),
    rfid:input.rfid.toUpperCase().replace(/[\s:-]/g,''), hoatDong:input.hoatDong === true};
  if (!/^[A-Z0-9_-]{1,40}$/.test(p.maNhanVien) || !p.hoTen || !p.boPhan) throw Error('Nhập đầy đủ mã nhân viên, họ tên, bộ phận. Mã chỉ gồm chữ, số, _ hoặc -.');
  if (!/^[0-9]{2}[A-Z][A-Z0-9]{1,2}[0-9]{4,5}$/.test(p.bienSo)) throw Error('Biển số không hợp lệ. Ví dụ 76-G1 082.16.');
  if (!(p.rfid===''&&!p.hoatDong) && !/^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$/.test(p.rfid)) throw Error('UID RFID phải có 4, 7 hoặc 10 byte dạng hex.');
  return p;
}
export function mergePerson(current, person, expectedVersion = null) {
  const data = structuredClone(current || {nhanVien:{},theRFID:{},bienSo:{}});
  data.nhanVien ||= {}; data.theRFID ||= {}; data.bienSo ||= {};
  const id=person.maNhanVien, old=data.nhanVien[id];
  if(person.rfid && data.theThuHoi?.[person.rfid]?.eraseJob)throw Error('Thẻ đang có phiên xóa chưa kết thúc. Chờ trạm trả kết quả.');
  if (old && expectedVersion === null) throw Error('Mã nhân viên đã tồn tại. Chọn Sửa trên hồ sơ đó.');
  if ((old?.updatedAt ?? null) !== expectedVersion) throw Error('Hồ sơ đã thay đổi trên máy khác. Tải lại trước khi sửa.');
  for (const [field,index] of [['rfid','theRFID'],['bienSo','bienSo']]) {
    if (data[index][person[field]] && data[index][person[field]] !== id) throw Error('Thẻ hoặc biển số đã được đăng ký cho nhân viên khác.');
    if (old && old[field]) delete data[index][old[field]];
    if(person[field])data[index][person[field]]=id;
  }
  data.nhanVien[id]=person;
  return data;
}
export function revokeCard(current,id,expectedVersion,timestamp){
  const data=structuredClone(current||{}),p=data.nhanVien?.[id];
  if(!p?.rfid)throw Error('Nhân viên không còn thẻ để thu hồi.');
  if(p.updatedAt!==expectedVersion)throw Error('Hồ sơ đã thay đổi. Chọn lại nhân viên.');
  const uid=p.rfid;
  data.theThuHoi||={};data.theThuHoi[uid]={rfid:uid,maNhanVien:id,hoTen:p.hoTen,bienSo:p.bienSo,revokedAt:timestamp};
  data.lichSuThuHoi||={};data.lichSuThuHoi[id+'_'+timestamp]={...data.theThuHoi[uid]};
  if(data.theRFID?.[uid]===id)delete data.theRFID[uid];
  p.rfid='';p.hoatDong=false;p.updatedAt=timestamp;
  return data;
}
export function filteredEvents(events, query='', day='') {
  const q=query.toLocaleLowerCase('vi');
  return Object.values(events || {}).filter(e => {
    const date=Number(e.timestamp);
    const localDay=Number.isFinite(date) ? new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(date) : '';
    return (!day || day===localDay) && `${e.maNhanVien||''} ${e.hoTen||''} ${e.bienSo||''} ${e.rfid||''}`.toLocaleLowerCase('vi').includes(q);
  }).sort((a,b)=>(Number(b.timestamp)||0)-(Number(a.timestamp)||0));
}
export function summarize(events) {
  const counts={IN:0,OUT:0,PASS:0,FAIL:0,ERROR:0,DENIED:0};
  for (const e of events) if (Object.hasOwn(counts,e.loai)) counts[e.loai]++;
  return counts;
}
export function csvCell(value) {
  let s=String(value??'');
  if (/^[=+\-@\t\r]/.test(s)) s="'"+s;
  return '"'+s.replaceAll('"','""')+'"';
}
