import test from 'node:test';
import assert from 'node:assert/strict';
import {makeJob,enqueueJob} from './card-writer-model.mjs';
const now=1793940000000;
const person={maNhanVien:'NV001',hoTen:'Nhân viên mẫu',bienSo:'76G108216',rfid:'A31695DC',hoatDong:true,updatedAt:123};
const scan={rfid:person.rfid,cardType:'MIFARE_1K',timestamp:now};
const heartbeat={timestamp:now};
const make=(p=person,s=scan,h=heartbeat)=>makeJob(p,s,h,now,'12345678-1234-1234-1234-123456789abc');
test('job binds stored employee, UID, plate and profile version',()=>{
 const job=make();assert.equal(job.rfid,person.rfid);assert.equal(job.profileVersion,123);assert.equal(job.expiresAt,now+120000);assert.equal(job.status,'PENDING');
});
test('wrong card cannot be requested',()=>assert.throws(()=>make(person,{...scan,rfid:'11223344'})));
test('unsupported card cannot be requested',()=>assert.throws(()=>make(person,{...scan,cardType:'NTAG213'})));
test('4K card supported',()=>assert.equal(make(person,{...scan,cardType:'MIFARE_4K'}).status,'PENDING'));
test('missing or stale station cannot be requested',()=>{
 assert.throws(()=>make(person,scan,null));assert.throws(()=>make(person,scan,{timestamp:now-31000}));
 for(const timestamp of [undefined,null,'invalid',NaN])assert.throws(()=>make(person,scan,{timestamp}));
});
test('old or future card scan rejected',()=>{
 assert.throws(()=>make(person,{...scan,timestamp:now-61000}));assert.throws(()=>make(person,{...scan,timestamp:now+61000}));
 for(const timestamp of [undefined,null,'invalid',NaN])assert.throws(()=>make(person,{...scan,timestamp}));
});
test('inactive or missing employee rejected',()=>{assert.throws(()=>make(null));assert.throws(()=>make({...person,hoatDong:false}));});
test('long code is bounded to memory format',()=>{assert.doesNotThrow(()=>make({...person,maNhanVien:'A'.repeat(40)}));assert.throws(()=>make({...person,maNhanVien:'A'.repeat(41)}));});
test('active writer cannot be replaced, even when browser clicks twice',()=>{
 const job=make();for(const status of ['PENDING','WRITING','VERIFYING'])assert.throws(()=>enqueueJob({...job,status},job,now));
});
test('expired pending request can be replaced but interrupted writes must be resolved',()=>{
 const job=make();assert.equal(enqueueJob({...job,expiresAt:now-1},job,now),job);
 assert.throws(()=>enqueueJob({...job,status:'WRITING',expiresAt:now-1},job,now));
});
test('new job allowed after verified success or error',()=>{
 const job=make();for(const status of ['SUCCESS','ERROR','EXPIRED'])assert.equal(enqueueJob({...job,status},job,now),job);
});
