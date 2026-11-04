import {test} from 'node:test';
import assert from 'node:assert/strict';
import {screeningIds,evidencePriority,confidenceLevel,evidenceGaps} from '../lib/evidence-workflow.ts';
test('screening is bounded, balanced and deterministic without treating lexical match as support',()=>{
 const run={results:[0,1,2].map(g=>({passages:Array.from({length:15},(_,i)=>({id:`${g}-${i}`,lexical_relevance:i}))}))};
 const ids=screeningIds(run);assert.equal(ids.length,12);assert.equal(new Set(ids).size,12);
 for(let g=0;g<3;g++)assert.equal(ids.filter(x=>x.startsWith(`${g}-`)).length,4);
 assert.equal(ids[0],'0-14');
});
test('contradictions are prioritized equally to support; irrelevant last, unknown not discarded',()=>{
 const result=r=>({status:'mapped',decision:{relationship:r}});
 assert.equal(evidencePriority(result('SUPPORTS')),evidencePriority(result('CONTRADICTS')));
 assert(evidencePriority(result('QUALIFIES'))<evidencePriority(result('CONTEXT')));
 assert(evidencePriority()<evidencePriority(result('IRRELEVANT')));
});
test('confidence bands preserve quantitative score boundaries',()=>{
 assert.deepEqual([0,24,25,49,50,74,75,100].map(confidenceLevel),['Very limited','Very limited','Low','Low','Moderate','Moderate','High','High']);
});
test('findings expose unresolved, unselected, failed-fetch and no-decisive-evidence gaps',()=>{
 const gaps=evidenceGaps({coverage:{unresolved_passage_ids:['a'],unmapped_passage_ids:['b'],failed_fetch_count:1},citations:[],evidence_status:'Insufficient Evidence'});
 assert.equal(gaps.length,4);assert(gaps.some(g=>g.includes('outside')));assert(gaps.some(g=>g.includes('could not')));
});
