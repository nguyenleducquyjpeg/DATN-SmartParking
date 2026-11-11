import test from 'node:test';
import assert from 'node:assert/strict';
import {createSimulator} from './card-simulator.mjs';
import {makeJob,enqueueJob} from './card-writer-model.mjs';
const base='TramCapThe/CAP_THE_01';
async function setup(){
 const queue=[],sim=createSimulator({schedule:fn=>queue.push(fn),now:()=>100000});
 const p={maNhanVien:'NV001',hoTen:'Mẫu',bienSo:'76G108216',rfid:'A31695DC',hoatDong:true,updatedAt:1};
 sim.scan(p.rfid);
 await sim.api.runTransaction('HoSoNhanVien',()=>({nhanVien:{NV001:p}}));
 const job=makeJob(p,(await sim.api.get(base+'/scan')).val(),(await sim.api.get(base+'/heartbeat')).val(),100000,'test');
 await sim.api.runTransaction(base+'/job',old=>enqueueJob(old,job,100000));
 return {sim,queue,job};
}
test('simulator writes card then verifies and isolates each instance',async()=>{
 const {sim,queue}=await setup();const statuses=[];sim.api.onValue(base+'/job',s=>statuses.push(s.val().status));
 while(queue.length)queue.shift()();
 assert.deepEqual(statuses,['PENDING','WRITING','VERIFYING','SUCCESS']);
 assert.equal((await sim.api.get(base+'/job')).val().verified,true);
 assert.deepEqual(sim.readCard('A31695DC'),{maNhanVien:'NV001',bienSo:'76G108216'});
 assert.equal((await createSimulator().api.get('HoSoNhanVien')).val(),null);
});
test('removing card interrupts writing',async()=>{const {sim,queue}=await setup();queue.shift()();sim.remove();while(queue.length)queue.shift()();assert.equal((await sim.api.get(base+'/job')).val().error,'WRONG_CARD');});
test('injected verification failure never claims success',async()=>{const {sim,queue}=await setup();sim.setFailure(true);while(queue.length)queue.shift()();const job=(await sim.api.get(base+'/job')).val();assert.equal(job.error,'VERIFY_FAILED');assert.notEqual(job.verified,true);});
test('invalid UID rejected',()=>assert.throws(()=>createSimulator().scan('bad')));
test('profile change stops issuance',async()=>{const {sim,queue}=await setup();await sim.api.runTransaction('HoSoNhanVien',()=>null);while(queue.length)queue.shift()();assert.equal((await sim.api.get(base+'/job')).val().error,'PROFILE_CHANGED');});
