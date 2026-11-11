"""Common-sample admission never grants financial or investment approval."""
import copy,json,unittest,gzip,os,subprocess,sys,tempfile
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timedelta

from equity_research.common_sample import verify_common_sample,candidate_pool
from equity_research.filing_metadata import inline_date,filing_security_metadata
from equity_research.nasdaq import DIRECTORY_URLS
from equity_research.providers import ProviderFailure
from equity_research.submissions import submissions_url
from test_nasdaq import response as listing_response,data as listing_row
from test_scoring import metadata,ASOF
from test_valuation import CIK,filing,identity

PLAN={'companies':[dict(symbol='AAPL',issuer_id=CIK)]}
URL='https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/annual.htm'


def annual():
    r=filing();body=r.body.replace(b'>10-Q<',b'>10-K<').replace(b'2026-07-01',b'2025-01-01').replace(b'2026-09-30',b'2025-12-31')
    return replace(r,url=URL,body=body)


def sources():return [listing_response(),listing_response('otherlisted'),identity(),metadata(),annual()]


def run(responses=None,plan=None,as_of=ASOF,target=1):return verify_common_sample(plan or PLAN,responses or sources(),as_of=as_of,target=target)


class CommonSampleTests(unittest.TestCase):
    def test_verified_sample_keeps_scope_model_and_investment_approval_separate(self):
        r=run();self.assertTrue(r['target_sample_verified']);self.assertFalse(r['hundred_common_share_sample_verified'])
        self.assertEqual(r['candidate_plan'],PLAN);self.assertFalse(r['mvp_accepted'])
        c=r['companies'][0];self.assertFalse(c['scope_approved']);self.assertFalse(c['sector_model_supported'])
        self.assertFalse(c['investment_approved']);self.assertIsNone(c['total_score'])
        self.assertEqual(c['filing_source']['raw_sha256'],annual().sha256)

    def test_injected_plan_approval_does_not_override_invalid_original_document(self):
        plan=copy.deepcopy(PLAN);plan['companies'][0].update(scope_approved=True,total_score=100)
        responses=sources();responses[-1]=replace(annual(),body=annual().body.replace(b'>AAPL<',b'>MSFT<'))
        r=run(responses,plan);self.assertEqual(r['candidate_plan']['companies'],[])
        self.assertFalse(r['target_sample_verified'])

    def test_depositary_preferred_fund_and_wrong_company_are_not_common_candidates(self):
        for title in ('American Depositary Shares representing Common Stock','Preferred Stock','Units containing Common Stock'):
            responses=sources();responses[-1]=replace(annual(),body=annual().body.replace(b'>Common Stock<',b'>'+title.encode()+b'<'))
            self.assertFalse(run(responses)['target_sample_verified'])
        r=run(plan={'companies':[dict(symbol='AAPL',issuer_id='0000000001')]})
        self.assertFalse(r['target_sample_verified'])

    def test_listing_etf_and_outside_exchange_block_even_with_matching_common_cover(self):
        for row in (listing_row(ETF='Y'),listing_row(**{'Test Issue':'Y'})):
            responses=sources();responses[0]=listing_response(rows=[row])
            self.assertFalse(run(responses)['target_sample_verified'])

    def test_reported_shell_or_investment_company_overrides_common_cover(self):
        for concept,text in [('dei:EntityShellCompany','true'),('dei:EntityInvCompanyType','N-2')]:
            responses=sources();r=annual();extra=f'<ix:nonNumeric name="{concept}" contextRef="cover">{text}</ix:nonNumeric>'.encode()
            responses[-1]=replace(r,body=r.body.replace(b'</html>',extra+b'</html>'))
            self.assertEqual(run(responses)['companies'][0]['blockers'],['reported_fund_bdc_or_shell'])

    def test_banking_and_insurance_are_permanently_excluded_from_candidate_plan(self):
        for sic in ('6021','6029','6035','6311','6324','6331','6411','6162','6199','6211'):
            with self.subTest(sic=sic):
                responses=sources();responses[-2]=metadata(sic=sic)
                result=run(responses)
                self.assertEqual(result['candidate_plan']['companies'],[])
                self.assertEqual(result['companies'][0]['blockers'],['banking_or_insurance_permanently_excluded'])
                self.assertFalse(result['target_sample_verified'])

    def test_unknown_investment_issuer_route_stays_review(self):
        responses=sources();responses[-2]=metadata(entity='investment')
        self.assertFalse(run(responses)['target_sample_verified'])
        responses[-2]=metadata(sic='6722');self.assertFalse(run(responses)['target_sample_verified'])

    def test_missing_stale_future_or_wrong_annual_filing_cannot_admit(self):
        self.assertFalse(run(sources()[:-1])['target_sample_verified'])
        for idx in (-1,-2):
            responses=sources();responses[idx]=replace(responses[idx],retrieved_at=ASOF+timedelta(days=1))
            self.assertFalse(run(responses)['target_sample_verified'])
        responses=sources();responses[-2]=replace(responses[-2],retrieved_at=ASOF-timedelta(days=5))
        self.assertFalse(run(responses)['target_sample_verified'])
        responses=sources();responses[-1]=replace(annual(),url=URL+'wrong')
        self.assertFalse(run(responses)['target_sample_verified'])

    def test_wrong_date_transform_namespace_is_rejected(self):
        r=annual();b=r.body.replace(b'<html ',b'<html xmlns:ixt="https://evil.example/transforms" ')
        b=b.replace(b'name="dei:DocumentPeriodEndDate" contextRef="cover">2025-12-31',
                    b'name="dei:DocumentPeriodEndDate" contextRef="cover" format="ixt:date-month-day-year">12/31/2025')
        responses=sources();responses[-1]=replace(r,body=b)
        self.assertFalse(run(responses)['target_sample_verified'])

    def test_known_numeric_date_transform_uses_explicit_month_first_order(self):
        r=annual();b=r.body.replace(b'<html ',b'<html xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" ')
        b=b.replace(b'name="dei:DocumentPeriodEndDate" contextRef="cover">2025-12-31',
                    b'name="dei:DocumentPeriodEndDate" contextRef="cover" format="ixt:date-month-day-year">12/31/2025')
        responses=sources();responses[-1]=replace(r,body=b)
        self.assertTrue(run(responses)['target_sample_verified'])

    def test_duplicate_identity_and_outside_target_bounds_are_rejected(self):
        for rows in ([],PLAN['companies']*2,PLAN['companies']*126):
            with self.assertRaises(ValueError):candidate_pool({'companies':rows})
        for target in (0,101,True):
            with self.assertRaises(ValueError):run(target=target)

    def test_conflicting_observations_at_same_time_cannot_win(self):
        responses=sources();responses.append(replace(annual(),body=annual().body+b'conflicting'))
        with self.assertRaises(ValueError):run(responses)

    def test_registered_primary_exchange_filters_a_genuine_second_listing(self):
        r=annual();b=r.body.replace(b'</html>',b'<xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context><ix:nonNumeric name="dei:TradingSymbol" contextRef="other">AAPL</ix:nonNumeric><ix:nonNumeric name="dei:Security12bTitle" contextRef="other">Common Stock</ix:nonNumeric><ix:nonNumeric name="dei:SecurityExchangeName" contextRef="other">New York Stock Exchange</ix:nonNumeric></html>')
        responses=sources();responses[-1]=replace(r,body=b)
        self.assertTrue(run(responses)['target_sample_verified'])
        self.assertEqual(len(run(responses)['companies'][0]['cover']['registered_security']),1)


class CommonSampleCLITests(unittest.TestCase):
    def test_cli_emits_only_verified_plan_and_protects_input_and_bundle(self):
        from equity_research.response_archive import ResponseArchive
        from equity_research.evidence_bundle import write_bundle
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);archive=ResponseArchive(folder/'sources.sqlite')
            try:
                for r in sources():archive.record(r)
                write_bundle(archive,folder/'bundle')
            finally:archive.close()
            plan=folder/'input.json';plan.write_text(json.dumps(PLAN));report=folder/'report.json';output=folder/'candidates.json'
            cmd=[sys.executable,'-m','equity_research','common-sample','--candidates',str(plan),
                '--source-bundle',str(folder/'bundle'),'--as-of',ASOF.isoformat(),
                '--sample-size','1','--output',str(report),'--plan-output',str(output)]
            env={**os.environ,'PYTHONPATH':str(root/'src')}
            ran=subprocess.run(cmd,capture_output=True,text=True,env=env)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertEqual(json.loads(output.read_text()),PLAN)
            self.assertFalse(json.loads(report.read_text())['mvp_accepted'])
            before=plan.read_bytes();cmd[cmd.index('--plan-output')+1]=str(plan)
            refused=subprocess.run(cmd,capture_output=True,text=True,env=env)
            self.assertEqual(refused.returncode,2);self.assertEqual(plan.read_bytes(),before)
            cmd[cmd.index('--plan-output')+1]=str(folder/'bundle'/'manifest.json')
            before=(folder/'bundle'/'manifest.json').read_bytes()
            refused=subprocess.run(cmd,capture_output=True,text=True,env=env)
            self.assertEqual(refused.returncode,2);self.assertEqual((folder/'bundle'/'manifest.json').read_bytes(),before)

    def test_portable_listing_origins_are_exact_public_hosts_without_credentials(self):
        from equity_research.response_archive import public_url
        for host in ('ftp.nasdaqtrader.com','www.nasdaqtrader.com'):
            public_url('https://'+host+'/SymbolDirectory/nasdaqlisted.txt')
        for url in ('https://www.nasdaqtrader.com.evil.example/list.txt','https://www.nasdaqtrader.com/list.txt?api_key=secret'):
            with self.assertRaises(ValueError):public_url(url)

    def test_exchange_labels_use_known_case_variants_without_accepting_other_venues(self):
        r=annual();r=replace(r,body=r.body.replace(b'>Nasdaq<',b'>The NASDAQ Global Select Market<'))
        responses=sources();responses[-1]=r
        self.assertTrue(run(responses)['target_sample_verified'])
        responses[-1]=replace(r,body=r.body.replace(b'The NASDAQ Global Select Market',b'NYSE Arca'))
        self.assertFalse(run(responses)['target_sample_verified'])


class DateTransformTests(unittest.TestCase):
    def test_explicit_four_digit_supported_transforms_not_calendar_inference(self):
        expected=datetime(2025,12,31).date()
        for text,fmt in [('DECEMBER\u00a031, 2025','ixt:date-monthname-day-year-en'),('Dec 31, 2025','ixt:datemonthdayyearen'),('12/31/2025','ixt:date-month-day-year')]:
            self.assertEqual(inline_date(text,fmt),expected)
        for text,fmt in [('31/12/2025','ixt:date-month-day-year'),('12/31/25','ixt:date-month-day-year'),('2025-12-31','ixt:unknown'),('December 32, 2025','ixt:datemonthdayyearen')]:
            with self.assertRaises(ValueError):inline_date(text,fmt)


class RecordedCommonSampleTests(unittest.TestCase):
    def test_actual_hundred_sample_has_exact_identity_class_evidence_without_scores(self):
        import hashlib
        root=Path(__file__).resolve().parents[1];folder=root/'docs/evidence/common100'
        report=json.loads(gzip.decompress((folder/'report.json.gz').read_bytes()))
        plan=json.loads((folder/'candidates.json').read_text())
        self.assertEqual(report['summary']['evaluated'],101);self.assertEqual(report['summary']['selected'],100)
        self.assertEqual(len(plan['companies']),100);self.assertEqual(len({r['issuer_id'] for r in plan['companies']}),100)
        self.assertTrue(report['hundred_common_share_sample_verified']);self.assertFalse(report['mvp_accepted'])
        self.assertFalse(report['active_universe_accepted'])
        verified=[r for r in report['companies'] if r['status']=='verified_registered_common_sample']
        self.assertEqual([dict(symbol=r['symbol'],issuer_id=r['issuer_id']) for r in verified],plan['companies'])
        for row in verified:
            self.assertEqual(row['cover']['issuer_id'],row['issuer_id'])
            self.assertEqual(row['cover']['raw_sha256'],row['filing_source']['raw_sha256'])
            self.assertFalse(row['investment_approved']);self.assertFalse(row['sector_model_supported'])
            self.assertIsNone(row['total_score'])
        ter=next(r for r in report['companies'] if r['symbol']=='TER');self.assertEqual(ter['status'],'review_required')
        manifest=json.loads((folder/'manifest.json').read_text())
        for row in manifest['files']:self.assertEqual(hashlib.sha256((folder/row['file']).read_bytes()).hexdigest(),row['sha256'])
        for name in ('base','extra'):
            self.assertEqual(hashlib.sha256((root/manifest[name+'_bundle']/'manifest.json').read_bytes()).hexdigest(),manifest[name+'_manifest_sha256'])
        proof=json.loads((folder/'resume-proof.json').read_text())
        self.assertEqual(proof['initial_new_get_invocations'],35);self.assertEqual(proof['reserve_new_get_invocations'],2)
        self.assertEqual(proof['warm_new_get_invocations'],0);self.assertTrue(proof['reserve_and_warm_evidence_events_unchanged'])

    def test_actual_replacement_covers_rebuild_from_archived_bytes_including_unresolved_ter(self):
        from equity_research.evidence_bundle import read_bundle
        from equity_research.cache import encode
        root=Path(__file__).resolve().parents[1]
        expected=json.loads(gzip.decompress((root/'docs/evidence/common100/report.json.gz').read_bytes()))
        symbols={'ADBE','INTU','TYL','TER'}
        selected=[r for r in expected['companies'] if r['symbol'] in symbols]
        pool=dict(companies=[dict(symbol=r['symbol'],issuer_id=r['issuer_id']) for r in selected])
        report=verify_common_sample(pool,read_bundle(root/'tests/fixtures/common-extra-sources'),
            as_of=datetime.fromisoformat(expected['as_of']),target=3)
        self.assertEqual(report['summary']['selected'],3);self.assertTrue(report['target_sample_verified'])
        for actual,want in zip(report['companies'],selected):
            self.assertEqual(json.loads(json.dumps(actual,default=encode)),want)


class RecordedCommonPriceTests(unittest.TestCase):
    def test_new_plan_hundred_prices_replay_exact_source_identity_currency_and_times(self):
        from dataclasses import asdict
        from equity_research.cache import encode
        from equity_research.evidence_bundle import read_bundle
        from equity_research.prices import parse_price
        from equity_research.sec import DIRECTORY_URL
        root=Path(__file__).resolve().parents[1];folder=root/'docs/evidence/common-price100'
        report=json.loads(gzip.decompress((folder/'report.json.gz').read_bytes()))
        plan=json.loads((root/'docs/evidence/common100/candidates.json').read_text())
        self.assertEqual(report['summary']['collected_prices'],100)
        self.assertEqual([dict(symbol=r['symbol'],issuer_id=r['issuer_id']) for r in report['companies']],plan['companies'])
        raw={(r.url,r.sha256,r.retrieved_at.isoformat()):r for r in read_bundle(root/'tests/fixtures/common-price100-sources')}
        self.assertEqual(len(raw),101)
        for row in report['companies']:
            price=row['price'];identity=raw[(DIRECTORY_URL,price['identity_evidence_sha256'],price['identity_observed_at'])]
            source=raw[(price['source_url'],price['raw_sha256'],price['retrieved_at'])]
            result=parse_price(source,identity,cik=row['issuer_id'],symbol=row['symbol'],as_of=datetime.fromisoformat(report['generated_at']))
            self.assertEqual(json.loads(json.dumps(asdict(result),default=encode)),price)
            self.assertFalse(row['scope_approved']);self.assertIsNone(row['total_score'])
        proof=json.loads((folder/'resume-proof.json').read_text())
        self.assertEqual(proof['initial_price_GETs'],100);self.assertEqual(proof['initial_identity_GETs'],1)
        self.assertEqual(proof['resume_price_GETs'],0);self.assertEqual(proof['resume_identity_GETs'],0)
        self.assertTrue(proof['all_100_price_values_source_times_and_identity_evidence_unchanged'])
