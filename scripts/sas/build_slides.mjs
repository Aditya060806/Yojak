import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = path.resolve(process.cwd());
const runtime = process.env.ARTIFACT_NODE_MODULES;
const skill = process.env.PRESENTATION_SKILL_DIR;
if (!runtime || !skill) throw new Error('Set ARTIFACT_NODE_MODULES and PRESENTATION_SKILL_DIR');
const { Presentation, PresentationFile } = await import(pathToFileURL(path.join(runtime, '@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
const read = async name => JSON.parse(await fs.readFile(path.join(root, 'private_sas', name), 'utf8'));
const research = await read('research_report.json');
const salary = await read('salary_report.json');
const manifest = await read('manifest.json');
const audit = manifest.audit.analytics;
const percent = x => `${(100*x).toFixed(1)}%`;
const content = [
 ['Yojak: skills into decisions', 'Which role fits, which skills next, and how uncertain is the evidence?\n\nA private, source-labelled workflow for the supplied SAS datasets.', null],
 ['Six questions, distinct evidence', 'Role families and skill combinations\nSalary-band explanation and prediction\nCompany-title compensation\nThree-skill learning priorities\nJunior technical skills and recorded hike\nSenior traits and recorded outcomes', null],
 ['No invented career trajectory', 'Market postings, junior observations and senior observations are separate samples.\n\nStatistics pays twice is a hypothesis, not a predetermined or causal conclusion.', null],
 ['Four files, different units of observation', Object.entries(manifest.audit).map(([k,v])=>`${k}: ${v.raw_rows.toLocaleString()} observations`).join('\n')+'\n\nNever join cohort IDs across files.', null],
 ['Preparation changes the evidence', `${audit.exact_duplicates_removed} exact posting duplicates removed.\n${audit.skills_truncated} truncated skill lists flagged.\nMultiplicities retained only for sensitivity analysis.`, 'bands'],
 ['Contradictory labels are retained', `Empirical identical-feature agreement bound: ${percent(audit.empirical_feature_agreement_bound)}.\n\nAn in-sample diagnostic, not a universal prediction ceiling or a QWK ceiling.`, null],
 ['A flag is not a fraud verdict', 'Label-independent conjunctions flag records for sensitivity analysis.\nRemote work and part-time status alone never trigger exclusion.\nAssociation rules report absolute support as well as lift.', null],
 ['Role taxonomy stays auditable', 'Rules leave unmatched titles as Other.\nA 100-record review sample is prepared.\nManual purity assessment remains pending.', 'roles'],
 ['Statistics and modelling as hypotheses', `Training-only explanation: ${research.ordinal.primary_model || 'not verified'}.\nCommon-slope diagnostic: ${research.ordinal.assumption_status}.\nRejected common odds ratios must not headline the results.\nNo causal salary premium is claimed.`, null],
 ['GPU models must beat a baseline', `Selected by validation QWK: ${salary.champion}.\nSparse logistic regression, interval AFT and soft-target classification are separate experiments.`, 'models'],
 ['Uncertainty is broad and visible', `Test QWK: ${salary.test.qwk.toFixed(3)}\nWithin one band: ${percent(salary.test.within_one_band)}\nPrediction-set coverage: ${percent(salary.calibration.test_coverage)}\nMean set width: ${salary.calibration.mean_set_width.toFixed(2)} of 6 bands\n\nCoverage concerns posting labels, not user-profile salaries.`, null],
 ['Two sources provide a plausibility check', `Title-level rank correlation: ${research.company.cross_file.spearman?.toFixed(3)}.\n\nDifferent aggregation and sampling prevent treating this as external validation or proof of annual-lakh units.`, null],
 ['Employer effects need careful interpretation', `Held-out-employer median baseline MAE: ${research.company.heldout_company_baseline_mae_native.toFixed(2)} native units.\n\nMixed-model variance is conditional association, not causal employer contribution. Salary units remain unverified.`, null],
 ['Three skills, an explicit objective', 'Compare frequency advice with coverage optimization at the same three-skill budget.\nA record counts at 60% of observed skills.\nCP-SAT is attempted only for bounded pools.\nAlignment is not a job offer.', null],
 ['Junior technical skills', `${research.jds.n} observations, ${research.jds.groups} validation groups.\nGrouped out-of-fold AUC: ${research.jds.oof_auc.toFixed(3)}.\n\nSmall-sample associations, not promised salary hikes.`, 'jds'],
 ['Senior traits remain aggregate research', `${research.sds.n} observations, ${research.sds.groups} validation groups.\n\nNo individual hiring, promotion or suitability score.`, 'sds'],
 ['SAS execution is still pending', 'Prepared: private CSV bundle, shared partitions and SAS Studio programs.\nNot claimed: executed SAS models, matching software outputs or Visual Analytics screenshots.\nOrganizer-approved access is required.', null],
 ['What stakeholders can do next', 'Students: compare observed requirements, not guaranteed outcomes.\nEducators: validate skill priorities with curriculum prerequisites.\nEmployers: commission prospective, consented research.\nTeam: review taxonomy, confirm units and complete SAS validation.', null],
];
const font = resolvePresentationFont();
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const charts = {
 bands: { labels: Object.keys(audit.bands), values: Object.values(audit.bands), unit: 'Deduplicated postings' },
 roles: { labels: Object.keys(research.role_families), values: Object.values(research.role_families), unit: 'Postings; manual review pending' },
 models: { labels: salary.experiments.map(x=>x.name), values: salary.experiments.map(x=>x.validation.qwk || 0), unit: 'Validation QWK' },
};
for (const name of ['jds','sds']) charts[name] = { labels: research[name].features.map(x=>x.feature.replaceAll('_',' ')), values: research[name].features.map(x=>x.correlation), unit: 'Correlation; not causation' };
const owners=[];
for (const [i,[title,body,visual]] of content.entries()) {
 const slide=p.slides.add(); slide.background.fill='#FAFCFB';
 function text(value,left,top,width,height,size,bold=false,color='#193B30') {
  const s=slide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
  s.text=value; s.text.style={typeface:font,fontSize:size,bold,color,autoFit:'none'};
 }
 text(title,64,42,1152,95,38,true);
 if(visual) {
  const d=charts[visual];
  const decimal=['models','jds','sds'].includes(visual);
  const labels=d.labels.map((label,index)=>decimal ? `${label}  ${d.values[index].toFixed(3)}` : label);
  const c=slide.charts.add('bar',{position:{left:55,top:175,width:780,height:410},categories:labels,series:[{name:d.unit,values:d.values.map(v=>Number(v.toFixed(3))),fill:'#16745C'}],barOptions:{direction:'bar',grouping:'clustered'},hasLegend:false,dataLabels:{showValue:!decimal,position:'outEnd',textStyle:{fontSize:14,fill:'#193B30'}}});
  applyPresentationChartFont(c,{fontFamily:font});
  text(d.unit,70,610,755,30,18,false,'#607169');
  text(body,865,180,350,440,23); owners.push(i+1);
 } else text(body,80,175,1120,455,30);
 text(`Confidential working draft | ${i+1} / 18 | Source ${manifest.source_version}`,64,672,1152,25,13,false,'#607169');
 slide.speakerNotes.textFrame.setText(`Approximately 30 seconds. ${body}\nSources: private_sas/manifest.json, salary_report.json, research_report.json. SAS execution pending.`);
}
const revision=new Date().toISOString().replace(/[:.]/g,'-');
const staging=path.join(root,'private_sas/slide_build',revision); const output=path.join(root,'private_sas/submission');
await fs.mkdir(staging,{recursive:true}); await fs.mkdir(output,{recursive:true});
const candidatePath=path.join(staging,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const finalPath=path.join(output,`Yojak_Presentation_${revision}.pptx`);
await finalizePresentation({workspaceDir:path.join(root,'private_sas'),candidatePath,finalPath,pythonExecutable:process.env.ARTIFACT_PYTHON,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],explicitTotalSlideCount:18,
 requiredNativeChartOwnerSlides:owners,materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
 receiptPath:path.join(staging,'validation.json')});
for(let i=0;i<p.slides.items.length;i++) {
 const preview=await p.export({slide:p.slides.items[i],format:'png',scale:.8});
 await fs.writeFile(path.join(staging,`slide-${i+1}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log(finalPath);
