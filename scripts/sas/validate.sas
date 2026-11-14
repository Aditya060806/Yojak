/* NOT EXECUTED. Set root to an organizer-approved SAS upload directory.
   Import only the private bundle after transfer permission is confirmed. */
%let root=/YOUR_APPROVED_PRIVATE_DIRECTORY;
options validvarname=any;
%macro import_csv(name);
proc import datafile="&root./&name..csv" out=work.&name dbms=csv replace;
  guessingrows=max;
run;
%mend;
%import_csv(analytics_sas);
%import_csv(company_sas);
%import_csv(jds_sas);
%import_csv(sds_sas);

proc freq data=analytics_sas;
  tables split*band skills_truncated quality_flag / missing;
run;
proc means data=analytics_sas n nmiss min mean max;
  var exp_min exp_max multiplicity;
run;
proc sort data=analytics_sas out=unique_keys nodupkey;
  by row_key;
run;
proc sql;
  create table split_violations as
  select group_id, count(distinct split) as partitions
  from analytics_sas group by group_id having calculated partitions > 1;
quit;
/* Ordered response: higher outcome = higher band. Check response profile and
   model direction against Python before comparing signs/odds ratios. */
proc logistic data=analytics_sas(where=(split='train'));
  model band(order=internal) = exp_mid skill_count statistics modelling / link=clogit;
run;
/* These Firth fits differ from Python L2 fits. They are sensitivity analyses,
   not an assertion that differently penalized coefficients must be equal. */
proc logistic data=jds_sas;
  model target(event='1') = big_data_skills maths_stats_skills coding_skills
    ai_and_ml_skills dashboard_and_storytelling_skills / firth;
run;
proc logistic data=sds_sas;
  model target(event='1') = neuroticism extraversion openness_to_experience
    agreeableness conscientiousness / firth;
run;
proc mixed data=company_sas(where=(split='train')) method=reml;
  class company_key job_title;
  model log_pay = job_title experience_value / solution;
  random intercept / subject=company_key;
run;
/* Model Studio: assign split as Partition and explicitly map train, validation,
   test. Exclude calibration rows from training/tuning and all identifier fields
   from Inputs. Reserve calibration for conformalization in Python. */
