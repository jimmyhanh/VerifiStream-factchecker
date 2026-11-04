import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceAssessment} from '../lib/source-assessment.ts';
test('unknown metadata yields unknown credibility, not a zero score',()=>{
 const result=sourceAssessment({publisher:null,publication_date:null,source_type:'unknown',primary_secondary:'unknown',metadata_origin:'page_declared_unverified'});
 assert.equal(result.score,null);assert.equal(result.rating,'Not rated');
 assert.equal(result.signals[0].value,'Unknown');
});
test('complete self-declared metadata earns no trust points or independence',()=>{
 const result=sourceAssessment({publisher:'Example',publication_date:'2026-11-04',source_type:'report',primary_secondary:'primary',metadata_origin:'page_declared_unverified'});
 assert.equal(result.score,null);
 assert.equal(result.signals.find(s=>s.label==='Independent confirmation').value,'Not established');
 assert.equal(result.signals.find(s=>s.label==='Primary / secondary').value,'primary');
});
