import test from 'node:test';
import assert from 'node:assert/strict';
import {mergePerson,revokeCard,normalizePerson} from './employee-model.mjs';
import {makeEraseJob,lockErase,unlockErase,recoverErase,enqueueJob} from './card-writer-model.mjs';
import {createSimulator} from './card-simulator.mjs';
const p={maNhanVien:'NV001',hoTen:'Mẫu',boPhan:'Giao nhận',bienSo:'76G108216',rfid:'A31695DC',hoatDong:true,updatedAt:1};
const catalogue=()=>mergePerson(null,p);
const revoked=()=>revokeCard(catalogue(),p.maNhanVien,1,100);
const scan={rfid:p.rfid,cardType:'MIFARE_1K',timestamp:1000},beat={timestamp:1000,simulated:true};
const erase=c=>makeEraseJob(c,scan,beat,1000,'erase-test');
test('revoke removes UID index, disables profile and preserves audit and plate',()=>{
 const original=catalogue(),c=revokeCard(original,p.maNhanVien,1,100);
 assert.equal(original.nhanVien.NV001.rfid,p.rfid);
 assert.equal(c.nhanVien.NV001.rfid,'');assert.equal(c.nhanVien.NV001.hoatDong,false);
 assert.equal(c.theRFID[p.rfid],undefined);assert.equal(c.bienSo[p.bienSo],'NV001');
 assert.equal(c.lichSuThuHoi.NV001_100.rfid,p.rfid);
 assert.equal(normalizePerson(c.nhanVien.NV001).rfid,'');
 assert.throws(()=>normalizePerson({...c.nhanVien.NV001,hoatDong:true}));
});
test('stale or repeated revoke rejected',()=>{assert.throws(()=>revokeCard(catalogue(),'NV001',0,100));assert.throws(()=>revokeCard(revoked(),'NV001',100,200));});
test('erase rejects assigned cards and old station firmware',()=>{
 assert.throws(()=>erase(catalogue()));
 assert.throws(()=>makeEraseJob(revoked(),scan,{timestamp:1000,firmware:'card-writer-1'},1000,'test'));
});
test('erase reservation prevents assigning UID until matching job completes',()=>{
 const c=revoked(),job=erase(c),locked=lockErase(c,job),next={...p,maNhanVien:'NV002',bienSo:'59A112345'};
 assert.throws(()=>mergePerson(locked,next));assert.throws(()=>lockErase(locked,job));
 assert.throws(()=>mergePerson(unlockErase(locked,{...job,id:'other'}),next));
 const released=unlockErase(locked,{...job,status:'SUCCESS'});
 assert.equal(mergePerson(released,next).theRFID[p.rfid],'NV002');
});
test('only abandoned expired reservations recover; active erase stays locked',()=>{
 const job=erase(revoked()),c=lockErase(revoked(),job),late=job.expiresAt+31000;
 assert.equal(recoverErase(c,job.rfid,null,1000).theThuHoi[job.rfid].eraseJob,job.id);
 assert.equal(recoverErase(c,job.rfid,{...job,status:'WRITING'},late).theThuHoi[job.rfid].eraseJob,job.id);
 assert.equal(recoverErase(c,job.rfid,null,late).theThuHoi[job.rfid].eraseJob,undefined);
 assert.throws(()=>enqueueJob(null,job,late));
});
test('simulator supports revoke, erase verification and reissue',async()=>{
 const queue=[],sim=createSimulator({schedule:fn=>queue.push(fn),now:()=>1000});
 sim.scan(p.rfid);const c=revoked(),job=erase(c);
 await sim.api.runTransaction('HoSoNhanVien',()=>lockErase(c,job));
 await sim.api.runTransaction('TramCapThe/CAP_THE_01/job',v=>enqueueJob(v,job,1000));
 while(queue.length)queue.shift()();
 const result=(await sim.api.get('TramCapThe/CAP_THE_01/job')).val();
 assert.equal(result.status,'SUCCESS');assert.equal(result.bytesVerified,96);assert.equal(sim.readCard(p.rfid),null);
 await sim.api.runTransaction('HoSoNhanVien',c=>unlockErase(c,result));
 await sim.api.runTransaction('HoSoNhanVien',c=>mergePerson(c,{...p,maNhanVien:'NV002',bienSo:'59A112345'}));
 assert.equal((await sim.api.get('HoSoNhanVien/theRFID/'+p.rfid)).val(),'NV002');
});
