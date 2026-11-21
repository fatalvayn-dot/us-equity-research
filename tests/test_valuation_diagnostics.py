import json,unittest
from dataclasses import replace
from datetime import timedelta
from equity_research.valuation import build_valuation_report
from equity_research.scoring import build_score_report,render_score_markdown
from equity_research.score_html import render_score_html
from test_valuation import batch,cf,meta,filing,identity,price,NOW
from test_scoring import financial,comparisons,companyfacts,metadata,history,ASOF

class DiagnosticTests(unittest.TestCase):
    def report(self, sources, as_of=NOW):return build_valuation_report(batch(),sources,as_of=as_of)['companies'][0]
    def test_absent_price_retains_exact_missing_url(self):
        r=self.report([cf(),meta(),filing(),identity()])
        self.assertEqual(r['missing_source_urls'],[price().url]);self.assertIsNone(r['valuation'])
    def test_stale_price_and_wrong_class_have_different_stages(self):
        r=self.report([cf(),meta(),filing(),identity(),price()],NOW+timedelta(minutes=20))
        self.assertEqual(r['failed_validation_stage'],'price');self.assertEqual(r['failure_detail'],'stale_response')
        r=self.report([cf(),meta(),filing(title='Preferred Stock'),identity(),price()])
        self.assertEqual(r['failed_validation_stage'],'share_class');self.assertIsNone(r['valuation'])
    def test_stale_share_snapshot_and_class_model_are_distinct(self):
        stale = replace(cf(), retrieved_at=NOW-timedelta(hours=7))
        r = self.report([stale, meta(), filing(), identity(), price()])
        self.assertEqual(r["failed_validation_stage"], "disclosed_shares")
        self.assertEqual(r["failure_detail"], "stale_share_companyfacts")
        self.assertIsNone(r["valuation"])

        r = self.report([cf(), meta(), filing(title="Class A Common Stock"), identity(), price()])
        self.assertEqual(r["failed_validation_stage"], "share_class")
        self.assertEqual(r["failure_detail"], "class_specific_share_model_required")
        self.assertIsNone(r["valuation"])

    def test_missing_disclosed_shares_is_not_invalid_data(self):
        source=cf();body=json.loads(source.body);body['facts']['dei']={}
        r=self.report([replace(source,body=json.dumps(body).encode()),meta(),filing(),identity(),price()])
        self.assertEqual(r['missing_evidence'],['disclosed_shares']);self.assertNotIn('provider_status',r)
    def test_missing_and_ambiguous_originals_are_distinguished(self):
        r=self.report([cf(),meta(),identity(),price()]);self.assertIn('exact_original_share_filing',r['missing_source_urls'])
        r=self.report([cf(),meta(),identity(),price(),filing(),replace(filing(),url=filing().url+'-other')])
        self.assertEqual(r['failure_detail'],'ambiguous_original_share_filing');self.assertIsNone(r['valuation'])
    def test_score_reports_keep_diagnostics_without_granting_score(self):
        b=financial();current,prior=comparisons(b)
        r=build_score_report(b,current,prior,[companyfacts(),metadata(),filing(),identity(),price(),history()],as_of=ASOF+timedelta(minutes=20))
        c=r['companies'][0];self.assertEqual(c['blockers'],['valuation_source_evidence_required'])
        self.assertEqual(c['valuation_diagnostics']['failure_detail'],'stale_response')
        self.assertIsNone(c['total_score']);self.assertEqual(r['ranking'],[])
        for rendered in (render_score_markdown(r),render_score_html(r)):
            self.assertIn('Fiyat gözleminin tazelik süresi dolmuş',rendered)
            self.assertIn(price().url.replace('&','&amp;'),rendered)
            self.assertIn(price().sha256,rendered)
    def test_untrusted_diagnostic_text_is_escaped_in_both_reports(self):
        b=financial();current,prior=comparisons(b);r=build_score_report(b,current,prior,[],as_of=ASOF)
        r['companies'][0]['valuation_diagnostics']['missing_source_urls']=['<script>alert(1)</script>|bad']
        for rendered in (render_score_markdown(r),render_score_html(r)):
            self.assertNotIn('<script>alert(1)</script>',rendered)
            self.assertIn('&lt;script&gt;',rendered)

    def test_sec_confirmation_failure_preserves_stage_and_never_scores(self):
        b=financial();current,prior=comparisons(b)
        r=build_score_report(b,current,prior,[companyfacts(revenue=999),metadata(),filing(),identity(),price(),history()],as_of=ASOF)
        c=r['companies'][0]
        self.assertEqual(c['valuation_diagnostics']['failed_validation_stage'],'sec_financial_confirmation')
        self.assertIsNone(c['total_score'])
        self.assertEqual(r['ranking'],[])

    def test_successful_valuation_preserves_original_source_times(self):
        sources=[cf(),meta(),filing(),identity(),price()]
        r=self.report(sources)
        self.assertEqual(r['status'],'indicative_arithmetic_only')
        self.assertIsNotNone(r['valuation'])
        self.assertNotIn('failed_validation_stage',r)
        observed={item['url']:item for item in r['source_observations']}
        for source in sources:
            self.assertEqual(observed[source.url]['raw_sha256'],source.sha256)
            self.assertEqual(observed[source.url]['retrieved_at'],source.retrieved_at.isoformat())
