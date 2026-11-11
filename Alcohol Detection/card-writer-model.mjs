export const STATION='CAP_THE_01';
export const ACTIVE=['PENDING','WRITING','VERIFYING'];
export const JOB_LABELS={PENDING:'Chờ đặt đúng thẻ',WRITING:'Đang ghi thẻ',VERIFYING:'Đang đọc lại kiểm tra',SUCCESS:'Đã ghi và kiểm tra thành công',ERROR:'Ghi thẻ thất bại',EXPIRED:'Yêu cầu hết hạn'};
export const ERRORS={WRONG_CARD:'UID không khớp hồ sơ. Đặt đúng thẻ rồi gửi yêu cầu mới.',UNSUPPORTED_CARD:'Chỉ hỗ trợ MIFARE Classic 1K hoặc 4K.',PROFILE_CHANGED:'Hồ sơ đã thay đổi/ngừng hiệu lực. Chọn lại nhân viên.',AUTH_READ_FAILED:'Không đọc được vùng dữ liệu. Kiểm tra thẻ và khóa truy cập.',FOREIGN_DATA:'Vùng ghi có dữ liệu khác. Dùng thẻ trống hoặc thẻ do hệ thống này cấp.',WRITE_FAILED:'Ghi chưa hoàn tất. Giữ thẻ trên đầu đọc và gửi yêu cầu mới.',VERIFY_FAILED:'Đọc lại không khớp. Không sử dụng kết quả lần ghi này.',STATION_RESTARTED:'Trạm đã khởi động lại giữa phiên. Kiểm tra và ghi lại thẻ.',EXPIRED:'Hết thời gian chờ. Gửi yêu cầu mới.',PROFILE_READ_FAILED:'Không đọc được hồ sơ Firebase.',INVALID_REQUEST:'Yêu cầu ghi không hợp lệ.'};
export function makeJob(person,scan,heartbeat,now,id){
  if(!person||person.hoatDong!==true)throw Error('Chọn một hồ sơ đã lưu và đang hiệu lực.');
  if(!/^[A-Z0-9_-]{1,40}$/.test(person.maNhanVien)||!/^\d{2}[A-Z][A-Z0-9]{1,2}\d{4,5}$/.test(person.bienSo)||! /^(?:[A-F0-9]{8}|[A-F0-9]{14}|[A-F0-9]{20})$/.test(person.rfid))throw Error('Hồ sơ có mã/biển số/UID không hợp lệ.');
  if(!heartbeat||!Number.isFinite(heartbeat.timestamp)||Math.abs(now-heartbeat.timestamp)>30000)throw Error('Trạm cấp thẻ chưa kết nối hoặc quá 30 giây không phản hồi.');
  if(!scan||!Number.isFinite(scan.timestamp)||Math.abs(now-scan.timestamp)>60000)throw Error('Đặt thẻ lên trạm cấp thẻ để đọc UID mới.');
  if(scan.rfid!==person.rfid)throw Error('Thẻ trên trạm không đúng UID của nhân viên được chọn.');
  if(!['MIFARE_1K','MIFARE_4K'].includes(scan.cardType))throw Error('Thẻ này chưa được hỗ trợ. Cần MIFARE Classic 1K/4K.');
  return {id,status:'PENDING',maNhanVien:person.maNhanVien,hoTen:person.hoTen,rfid:person.rfid,bienSo:person.bienSo,profileVersion:person.updatedAt??0,createdAt:now,expiresAt:now+120000};
}
export function enqueueJob(current,job,now){
  if(now>=job.expiresAt)throw Error('Yêu cầu đã hết hạn trước khi gửi. Quét thẻ và thử lại.');
  if(current&&ACTIVE.includes(current.status)&&!(current.status==='PENDING'&&current.expiresAt<=now))throw Error('Trạm đang có yêu cầu chưa kết thúc. Chờ kết quả hoặc khởi động lại trạm nếu bị ngắt giữa phiên.');
  return job;
}
export function makeEraseJob(catalogue,scan,heartbeat,now,id){
  if(!heartbeat?.simulated&&heartbeat?.firmware!=='card-writer-2')throw Error('Cần nạp firmware card-writer-2 cho trạm trước khi xóa thẻ.');
  const record=catalogue?.theThuHoi?.[scan?.rfid];
  if(!record||catalogue.theRFID?.[scan.rfid]||Object.values(catalogue.nhanVien||{}).some(p=>p.rfid===scan.rfid))throw Error('Chỉ xóa thẻ đã thu hồi và chưa cấp lại. Thu hồi thẻ trong danh sách nhân viên trước.');
  const job=makeJob({...record,hoatDong:true,updatedAt:record.revokedAt},scan,heartbeat,now,id);
  return {...job,operation:'ERASE'};
}
export function lockErase(current,job){
  const data=structuredClone(current||{}),r=data.theThuHoi?.[job.rfid];
  if(!r||r.revokedAt!==job.profileVersion||r.eraseJob||data.theRFID?.[job.rfid]||Object.values(data.nhanVien||{}).some(p=>p.rfid===job.rfid))throw Error('Thẻ đã được cấp lại hoặc đang có yêu cầu xóa.');
  r.eraseJob=job.id;r.eraseExpiresAt=job.expiresAt;return data;
}
export function unlockErase(current,job){
  if(!current?.theThuHoi?.[job.rfid]||current.theThuHoi[job.rfid].eraseJob!==job.id)return current;
  const data=structuredClone(current);delete data.theThuHoi[job.rfid].eraseJob;
  data.theThuHoi[job.rfid].eraseStatus=job.status;return data;
}
export function recoverErase(current,uid,stationJob,now){
  const record=current?.theThuHoi?.[uid];
  if(!record?.eraseJob)return current;
  const same=stationJob?.id===record.eraseJob;
  const terminal=same&&['SUCCESS','ERROR','EXPIRED'].includes(stationJob.status);
  const unsent=!same&&Number.isFinite(record.eraseExpiresAt)&&now>record.eraseExpiresAt+30000;
  if(!terminal&&!unsent)return current;
  return unlockErase(current,{rfid:uid,id:record.eraseJob,status:terminal?stationJob.status:'NOT_SENT'});
}
