import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizePerson,mergePerson,filteredEvents,summarize,csvCell} from './employee-model.mjs';
const input={maNhanVien:'001',hoTen:'Quý',boPhan:'Shipper',bienSo:'76-G1 082.16',rfid:'a3:16:95:dc',hoatDong:true};
test('normalize registered motorcycle and UID',()=>{
  const p=normalizePerson(input);assert.equal(p.bienSo,'76G108216');assert.equal(p.rfid,'A31695DC');
});
test('reject malformed and missing fields',()=>{
  for(const patch of [{maNhanVien:'bad/id'},{hoTen:''},{rfid:'123'},{bienSo:'<script>'}])assert.throws(()=>normalizePerson({...input,...patch}));
});
test('create catalogue and both indexes atomically',()=>{
  const p={...normalizePerson(input),updatedAt:1}, data=mergePerson(null,p);
  assert.equal(data.theRFID.A31695DC,'001');assert.equal(data.bienSo['76G108216'],'001');assert.deepEqual(data.nhanVien['001'],p);
});
test('reject duplicated employee, card and plate',()=>{
  const p={...normalizePerson(input),updatedAt:1}, data=mergePerson(null,p);
  assert.throws(()=>mergePerson(data,p));
  assert.throws(()=>mergePerson(data,{...p,maNhanVien:'002',bienSo:'59X112345'}));
  assert.throws(()=>mergePerson(data,{...p,maNhanVien:'002',rfid:'11223344'}));
});
test('update removes old indexes without mutating original snapshot',()=>{
  const p={...normalizePerson(input),updatedAt:1}, original=mergePerson(null,p);
  const updated=mergePerson(original,{...p,rfid:'11223344',bienSo:'59X112345',updatedAt:2},1);
  assert.equal(updated.theRFID.A31695DC,undefined);assert.equal(updated.bienSo['76G108216'],undefined);
  assert.equal(original.theRFID.A31695DC,'001');assert.equal(updated.theRFID['11223344'],'001');
});
test('stale edit cannot overwrite newer version',()=>{
  const p={...normalizePerson(input),updatedAt:2}, data=mergePerson(null,p);
  assert.throws(()=>mergePerson(data,{...p,hoTen:'Other'},1));
});
test('day filter uses Vietnam time and counts every retest',()=>{
  const events={a:{maNhanVien:'001',loai:'FAIL',timestamp:Date.parse('2026-11-02T18:00:00Z')},b:{maNhanVien:'001',loai:'PASS',timestamp:Date.parse('2026-11-03T01:00:00Z')},c:{maNhanVien:'002',loai:'IN',timestamp:Date.parse('2026-11-03T01:00:00Z')}};
  const rows=filteredEvents(events,'001','2026-11-03');assert.equal(rows.length,2);
  const result=summarize(rows);assert.equal(result.PASS,1);assert.equal(result.FAIL,1);assert.equal(result.IN,0);
});
test('CSV quotes strings and neutralizes formulas',()=>{
  assert.equal(csvCell('=1+1'),'"\'=1+1"');assert.equal(csvCell('A"B'),'"A""B"');
});
