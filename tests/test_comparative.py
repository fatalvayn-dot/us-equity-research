import json
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from equity_research.cache import encode
from equity_research.comparative import comparison_plan, calculate_growth, comparable_periods, build_comparative_report
from equity_research.companyfacts import companyfacts_url
from equity_research.fields import SPECS
from equity_research.models import Fact, Source
from equity_research.providers import ProviderFailure
from equity_research.transport import Response

CIK = '0000320193'
NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
ACC = '0000320193-26-000001'
ANNUAL = dict(accession=ACC, form='10-K', filed_on='2026-10-01', report_end='2026-09-26', primary_document='annual.htm',
              source_url='https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/annual.htm')
START, END = date(2025, 9, 28), date(2026, 9, 26)
PS, PE = date(2024, 9, 29), date(2025, 9, 27)

def document():
    return Response(ANNUAL['source_url'], f'''<html xmlns:dei="http://xbrl.sec.gov/dei/2026"><xbrli:context id="d"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>{START}</xbrli:startDate><xbrli:endDate>{END}</xbrli:endDate></xbrli:period></xbrli:context><ix:nonNumeric name="dei:DocumentType" contextRef="d">10-K</ix:nonNumeric><ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="d">FY</ix:nonNumeric><ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="d">{END}</ix:nonNumeric></html>'''.encode(), NOW)

def row(start=START, end=END, value=120, **changes):
    result = dict(start=str(start), end=str(end), val=value, filed='2026-10-01', accn=ACC, form='10-K', fp='FY', fy=2026)
    result.update(changes); return result

def financial(rows=None):
    payload = dict(cik=int(CIK), entityName='Synthetic', facts={'us-gaap':{SPECS['revenue'].tag:{'units':{'USD':rows if rows is not None else [row(),row(PS, PE, 100)]}}}})
    return Response(companyfacts_url(CIK), json.dumps(payload).encode(), NOW)

def plan(doc=None, response=None, **changes):
    args = dict(issuer_id=CIK, symbol='AAPL', annual=ANNUAL, as_of=NOW); args.update(changes)
    return comparison_plan(doc or document(), response or financial(), **args)

def fact(start=START, end=END, value='120', **changes):
    f = Fact(CIK, 'revenue', Decimal(value), Source.SEC, start, end, 'USD', 'currency', NOW,
             NOW-timedelta(days=1), SPECS['revenue'].accounting_definition, companyfacts_url(CIK),
             filing_accession=ACC, filed_on=date(2026,10,1), raw_sha256='a'*64)
    return replace(f, **changes)

def batch(f):
    from dataclasses import asdict
    q = {k:getattr(f,k) for k in ('issuer_id','field','period_start','period_end','currency','unit','accounting_definition')}
    return json.loads(json.dumps(dict(schema_version=1, generated_at=NOW, companies=[dict(symbol='AAPL',issuer_id=CIK,scope_status='pending_scope',scope_reason='review',fields=[dict(query=q,state='collected',fact=asdict(f),as_of=NOW,attempts=[dict(source='Yahoo',status='unsupported_field',attempted_at=NOW),dict(source='SEC',status='valid',attempted_at=NOW)])])]),default=encode))

class ComparativeTests(unittest.TestCase):
    def test_literal_week_calendar_and_no_selected_values(self):
        r=plan();self.assertEqual(r['prior_period'],dict(period_start=str(PS),period_end=str(PE)))
        self.assertEqual(r['fields'],['revenue']);self.assertFalse(r['financial_values_selected']);self.assertEqual(r['provider_attempts'],[])
        from equity_research.batch import load_plan
        self.assertEqual(load_plan(r['prior_plan'])[0].queries[0].period_start,PS)

    def test_53_week_year_allowed_but_transition_and_gap_rejected(self):
        self.assertTrue(comparable_periods(START,END,PS-timedelta(days=7),PE))
        self.assertFalse(comparable_periods(START,END,PS-timedelta(days=8),PE))
        self.assertFalse(comparable_periods(START,END,PS,PE-timedelta(days=1)))
        self.assertFalse(comparable_periods(START,END,PE-timedelta(days=90),PE))

    def test_prior_period_is_not_inferred_from_fy_fp_or_frame(self):
        prior=row(PS,PE,100);prior.pop('start')
        r=plan(response=financial([row(),prior]))
        self.assertEqual(r['status'],'prior_period_unresolved')

    def test_quarter_and_other_accession_cannot_supply_prior(self):
        for changes in ({'form':'10-Q'},{'accn':'0000320193-25-000001'}):
            self.assertEqual(plan(response=financial([row(),row(PS,PE,100,**changes)]))['status'],'prior_period_unresolved')

    def test_conflicting_duplicates_do_not_supply_prior(self):
        r=plan(response=financial([row(),row(PS,PE,100),row(PS,PE,101)]))
        self.assertEqual(r['field_states']['revenue'],'conflicting_prior_values')

    def test_identical_duplicates_are_safe(self):
        self.assertEqual(plan(response=financial([row(),row(),row(PS,PE,100),row(PS,PE,100)]))['status'],'ready_for_ordered_collection')

    def test_two_explicit_prior_starts_are_ambiguous(self):
        r=plan(response=financial([row(),row(PS,PE,100),row(PS-timedelta(days=1),PE,100)]))
        self.assertEqual(r['field_states']['revenue'],'prior_period_absent_or_ambiguous')

    def test_invalid_value_and_filing_date_fail_closed(self):
        for changes in ({'val':True},{'val':'100'},{'filed':'2026-09-01'}):
            self.assertEqual(plan(response=financial([row(),row(PS,PE,100,**changes)]))['field_states']['revenue'],'invalid_concept_evidence')

    def test_source_identity_url_and_future_observation_rejected(self):
        for doc,response in ((replace(document(),url='https://example.com/annual.htm'),financial()),
                             (document(),replace(financial(),url=companyfacts_url('0000789019'))),
                             (replace(document(),retrieved_at=NOW+timedelta(seconds=1)),financial())):
            with self.assertRaises(ProviderFailure):plan(doc,response)

    def test_wrong_issuer_annual_context_rejected(self):
        with self.assertRaises(ProviderFailure):plan(replace(document(),body=document().body.replace(CIK.encode(),b'0000789019')))

    def test_growth_exact_and_original_inputs_retained(self):
        current,prior=fact(),fact(PS,PE,'100')
        r=calculate_growth(current,prior,as_of=NOW)
        self.assertEqual(r['value'],Decimal('.2'));self.assertEqual(r['inputs'][1]['period_start'],PS)
        self.assertFalse(r['scope_approved']);self.assertFalse(r['sector_model_supported'])

    def test_zero_negative_base_never_filled(self):
        for value in ('0','-100'):
            r=calculate_growth(fact(),fact(PS,PE,value),as_of=NOW)
            self.assertEqual(r['status'],'nonpositive_base');self.assertIsNone(r['value'])

    def test_negative_current_is_a_real_decline(self):
        self.assertEqual(calculate_growth(fact(value='-50'),fact(PS,PE,'100'),as_of=NOW)['value'],Decimal('-1.5'))

    def test_missing_and_hashless_inputs(self):
        self.assertEqual(calculate_growth(fact(),None,as_of=NOW)['status'],'pending_data')
        self.assertEqual(calculate_growth(fact(raw_sha256=None),fact(PS,PE,'100'),as_of=NOW)['status'],'invalid_inputs')

    def test_definition_currency_issuer_and_period_mismatch(self):
        for prior in (fact(PS,PE,'100',accounting_definition='us-gaap:Revenues'),fact(PS,PE,'100',currency='EUR'),
                      fact(PS,PE,'100',issuer_id='0000789019'),fact(PS+timedelta(days=30),PE,'100')):
            self.assertIsNone(calculate_growth(fact(),prior,as_of=NOW)['value'])

    def test_different_sec_accession_or_snapshot_cannot_mix_vintages(self):
        for changes in ({'filing_accession':'0000320193-25-000001'}, {'raw_sha256':'b'*64},{'retrieved_at':NOW-timedelta(hours=1)}):
            self.assertEqual(calculate_growth(fact(),fact(PS,PE,'100',**changes),as_of=NOW)['status'],'inconsistent_sec_filing_vintage')

    def test_comparative_report_validates_ordered_evidence_then_calculates(self):
        r=build_comparative_report(batch(fact()),batch(fact(PS,PE,'100')))
        self.assertEqual(r['summary']['arithmetic_results'],1);self.assertEqual(r['companies'][0]['calculations'][0]['value'],Decimal('.2'))
        self.assertFalse(r['mvp_accepted']);self.assertEqual(r['ranking'],[])

    def test_forged_winner_or_scope_cannot_reach_growth(self):
        for kind in ('winner','scope'):
            b=batch(fact())
            if kind=='winner':b['companies'][0]['fields'][0]['attempts'][0]['status']='valid'
            else:b['companies'][0]['scope_status']='approved'
            self.assertEqual(build_comparative_report(b,batch(fact(PS,PE,'100')))['summary']['arithmetic_results'],0)

    def test_issuer_set_and_symbol_mismatch_not_joined(self):
        b=batch(fact(PS,PE,'100'));b['companies'][0]['symbol']='WRONG'
        self.assertEqual(build_comparative_report(batch(fact()),b)['summary']['arithmetic_results'],0)
        b['companies'][0]['issuer_id']='0000789019'
        with self.assertRaises(ValueError):build_comparative_report(batch(fact()),b)

    def test_cross_field_prior_calendar_conflict_is_not_merged(self):
        response=financial();p=json.loads(response.body)
        p['facts']['us-gaap'][SPECS['operating_cash_flow'].tag]={'units':{'USD':[row(),row(PS-timedelta(days=1),PE,100)]}}
        r=plan(response=replace(response,body=json.dumps(p).encode()))
        self.assertEqual(r['status'],'conflicting_prior_periods');self.assertNotIn('prior_plan',r)

    def test_raw_body_nonfinite_and_wrong_payload_issuer_rejected(self):
        for body in (financial([row(value=float('nan'))]).body, financial().body.replace(b'320193',b'789019')):
            with self.assertRaises(ProviderFailure):plan(response=replace(financial(),body=body))

    def test_foreign_currency_discovery_is_not_silently_dollarized(self):
        with self.assertRaises(ProviderFailure):plan(currency='EUR')

    def test_unsupported_magnitude_is_bounded(self):
        self.assertEqual(calculate_growth(fact(value='1e1001'),fact(PS,PE,'100'),as_of=NOW)['status'],'unsupported_magnitude')

    def test_future_cutoff_and_naive_cutoff(self):
        self.assertEqual(calculate_growth(fact(),fact(PS,PE,'100'),as_of=NOW-timedelta(days=60))['status'],'invalid_inputs')
        with self.assertRaises(ValueError):calculate_growth(fact(),fact(PS,PE,'100'),as_of=NOW.replace(tzinfo=None))

    def test_decimal_global_precision_does_not_change_growth(self):
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec=2
            self.assertEqual(calculate_growth(fact(value='100001'),fact(PS,PE,'100000'),as_of=NOW)['value'],Decimal('.00001'))

    def test_alternative_accounting_definition_retains_review_label(self):
        values=[replace(f,field='profit_loss',accounting_definition=SPECS['profit_loss'].accounting_definition) for f in (fact(),fact(PS,PE,'100'))]
        r=calculate_growth(*values,as_of=NOW)
        self.assertEqual(r['value'],Decimal('.2'));self.assertTrue(r['semantic_model_review'])

    def test_comparative_markdown_escapes_input_and_shows_missing(self):
        from equity_research.comparative import render_comparative_markdown
        r=build_comparative_report(batch(fact()),batch(fact(PS,PE,'0')))
        r['companies'][0]['symbol']='<X|Y>'
        text=render_comparative_markdown(r)
        self.assertIn('&lt;X&#124;Y&gt;',text);self.assertIn('Mevcut değil',text)
        self.assertIn('ham kaynak özetleri',text)

    def test_cli_reads_compressed_batches_and_exports_report(self):
        import gzip, os, subprocess, sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);current=p/'current.json.gz';prior=p/'prior.json.gz';output=p/'report.json';markdown=p/'report.md'
            current.write_bytes(gzip.compress(json.dumps(batch(fact())).encode()))
            prior.write_bytes(gzip.compress(json.dumps(batch(fact(PS,PE,'100'))).encode()))
            command=[sys.executable,'-m','equity_research','comparative-report','--input',str(current),'--prior-input',str(prior),'--output',str(output),'--markdown',str(markdown)]
            result=subprocess.run(command,capture_output=True,text=True,env=os.environ)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(output.read_text())['summary']['arithmetic_results'],1)
            self.assertIn('0.2',markdown.read_text())
            command[command.index(str(output))]=str(prior)
            self.assertNotEqual(subprocess.run(command,capture_output=True,env=os.environ).returncode,0)
