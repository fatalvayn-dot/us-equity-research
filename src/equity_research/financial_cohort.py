"""Join exact candidate identities across dated financial cohorts, never refresh dates."""
import copy,hashlib,json
from collections import Counter
from datetime import datetime

from .cache import encode
from .models import aware
from .mvp import validate_candidates
from .reporting import build_report

COMPANY_KEYS=frozenset({'symbol','issuer_id','fields','period_start','period_end','currency',
    'scope_status','scope_reason','deferred_fields','pending_reason'})


def assemble_financial_cohort(candidates,batches):
    rows=validate_candidates(candidates);batches=list(batches)
    if not batches:raise ValueError('explicit source financial cohorts required')
    requested={r['issuer_id']:r['symbol'] for r in rows};index={};sources=[];times=[]
    for number,batch in enumerate(batches,1):
        build_report(batch)  # Revalidate original fact/period/attempt contracts.
        stamp=datetime.fromisoformat(batch['generated_at'])
        if not aware(stamp):raise ValueError('aware source cohort timestamp required')
        times.append(stamp)
        digest=hashlib.sha256(json.dumps(batch,default=encode,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        sources.append(dict(source=number,generated_at=stamp.isoformat(),sha256=digest))
        for company in batch['companies']:
            cik=company['issuer_id']
            if cik not in requested:continue
            if company['symbol']!=requested[cik]:raise ValueError('candidate/source symbol mismatch')
            if cik in index:raise ValueError('ambiguous duplicate issuer across cohorts')
            index[cik]=(number,company)
    output=[];counts=Counter()
    for row in rows:
        if row['issuer_id'] not in index:
            output.append(dict(**row,fields=[],scope_status='pending_scope',scope_reason='financial_cohort_missing',pending_reason='financial_cohort_missing'))
            counts['missing']+=1;continue
        number,company=index[row['issuer_id']]
        selected={k:copy.deepcopy(v) for k,v in company.items() if k in COMPANY_KEYS}
        output.append(selected);counts[str(number)]+=1
    merged=dict(schema_version=1,generated_at=max(times).isoformat(),companies=output)
    report=build_report(merged)
    report['financial_cohort']=dict(mode='mixed_dated_inputs_no_network',sources=sources,
        selected_by_source=dict(counts),oldest_source_generated_at=min(times).isoformat(),
        newest_source_generated_at=max(times).isoformat(),all_new_100_live_run=False,
        per_fact_source_and_query_times_preserved=True)
    return merged,report


def render_cohort_markdown(report):
    from .reporting import render_markdown
    lines=['# Farklı tarihlerde toplanmış finansal veriler','',
        'Bu rapor yeni bir canlı 100 şirket taraması değildir. Her verinin özgün kaynak ve sorgu tarihleri korunmuştur.','']
    for source in report['financial_cohort']['sources']:
        lines.append(f"Girdi {source['source']}: {source['generated_at']} · SHA-256 {source['sha256']}")
    lines.extend(['', 'Girdiye göre seçilen şirket sayısı: '+json.dumps(report['financial_cohort']['selected_by_source']), ''])
    return '\n'.join(lines)+render_markdown(report)


def render_cohort_html(report):
    from html import escape
    from .report_html import render_html
    dates='; '.join(str(s['source'])+': '+s['generated_at'] for s in report['financial_cohort']['sources'])
    banner='<section class="notice"><strong>Farklı tarihlerde toplanmış finansal veriler.</strong> Bu rapor yeni bir canlı 100 şirket taraması değildir. Kaynak ve sorgu tarihleri korunmuştur.<br>'+escape(dates)+'</section>'
    return render_html(report).replace('<body>','<body>'+banner,1)
