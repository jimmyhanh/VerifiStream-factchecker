import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contextSuggestions, appendContext } from '../lib/context-suggestions.ts';
const claim = {text:'Gas prices were the highest ever and contributed to the result.',source_quote:'Gas prices were $4.14 this year.',start_seconds:10,end_seconds:20,kind:'causal'};
test('copies relative dates without inventing year or country; labels directions', () => {
 const result=contextSuggestions(claim);
 assert(result.some(s=>s.text==='this year' && s.quote===claim.source_quote));
 assert(!result.some(s=>/2026|United States|U\.S\./.test(s.text)));
 assert(result.some(s=>s.origin==='Search direction' && /causation/.test(s.text)));
 assert(result.filter(s=>s.quote).every(s=>s.quote.includes(s.text)));
});
test('only adjacent nearby segments; no truncation of long quotations',()=>{
 const segments=[{start:0,end:3,text:'Earlier topic'},{start:5,end:10,text:'The policy in London.'},{start:20,end:25,text:'A nearby statement.'},{start:26,end:30,text:'Another topic'}];
 const result=contextSuggestions(claim,segments);
 assert.deepEqual(result.filter(s=>s.origin==='Nearby transcript quotation').map(s=>s.text),['The policy in London.','A nearby statement.']);
 assert(!contextSuggestions(claim,[{start:60,end:70,text:'Far away'}]).some(s=>s.origin==='Nearby transcript quotation'));
 assert(!contextSuggestions({...claim,source_quote:'x'.repeat(301)}).some(s=>s.quote));
});
test('manual text preserved, duplicate clicks harmless, 300 character limit enforced',()=>{
 assert.equal(appendContext('My context','2024'),'My context\n2024');
 assert.equal(appendContext('My context\n2024','2024'),'My context\n2024');
 assert.equal(appendContext('x'.repeat(299),'2024'),'x'.repeat(299));
 assert.equal(appendContext('x'.repeat(295),'2024').length,300);
});
test('suggestions remain scoped to each proposition',()=>{
 const a=contextSuggestions({...claim,source_quote:'In 2024 London opened schools.'});
 const b=contextSuggestions({...claim,source_quote:'In 2022 Paris built homes.'});
 assert(a.some(s=>s.text==='2024')); assert(!b.some(s=>s.text==='2024'));
});
