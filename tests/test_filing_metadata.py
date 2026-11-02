import gzip,unittest
from datetime import date
from pathlib import Path
from equity_research.filing_metadata import filing_security_metadata
from equity_research.providers import ProviderFailure

CIK='0000320193';END=date(2026,9,30)
def body(title='Common Stock',symbol='AAPL',exchange='Nasdaq',context='c',namespace='http://xbrl.sec.gov/dei/2026'):
 return f'''<html xmlns:dei="{namespace}">
 <xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
 <ix:nonNumeric name="dei:DocumentType" contextRef="c">10-Q</ix:nonNumeric>
 <ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="c">2026-09-30</ix:nonNumeric>
 <ix:nonNumeric name="dei:TradingSymbol" contextRef="{context}">{symbol}</ix:nonNumeric>
 <ix:nonNumeric name="dei:Security12bTitle" contextRef="c">{title}</ix:nonNumeric>
 <ix:nonNumeric name="dei:SecurityExchangeName" contextRef="c">{exchange}</ix:nonNumeric></html>'''.encode()
def parse(b,**changes):
 args=dict(cik=CIK,symbol='AAPL',report_end=END,document_type='10-Q');args.update(changes)
 return filing_security_metadata(b,**args)

class FilingMetadataTests(unittest.TestCase):
 def test_explicit_common_title_is_corroboration_only(self):
  r=parse(body());self.assertTrue(r['explicit_common_share_title']);self.assertFalse(r['scope_approved'])
  self.assertEqual(r['registered_security'][0]['symbol'],'AAPL')
 def test_wrong_identity_symbol_date_or_form_rejected(self):
  for changes in ({'cik':'0000789019'},{'symbol':'MSFT'},{'report_end':date(2025,9,30)},{'document_type':'10-K'}):
   with self.assertRaises(ProviderFailure):parse(body(),**changes)
 def test_security_title_not_joined_across_contexts(self):
  with self.assertRaises(ProviderFailure):parse(body(context='other'))
 def test_debt_preferred_depositary_and_units_not_common(self):
  for title in ('Notes due 2030','Preferred Stock','Depositary Shares representing Common Stock','Units each containing Common Stock'):
   with self.assertRaises(ProviderFailure):parse(body(title=title))
 def test_fake_namespace_rejected(self):
  with self.assertRaises(ProviderFailure):parse(body(namespace='http://evil.example/dei/2026'))
 def test_conflicting_titles_rejected(self):
  b=body().replace(b'</html>',b'<ix:nonNumeric name="dei:Security12bTitle" contextRef="c">Class B Common Stock</ix:nonNumeric></html>')
  with self.assertRaises(ProviderFailure):parse(b)
 def test_known_inline_date_transform_and_unknown_transform(self):
  b=body().replace(b'name="dei:DocumentPeriodEndDate" contextRef="c">2026-09-30',b'name="dei:DocumentPeriodEndDate" contextRef="c" format="ixt:date-monthname-day-year-en">September 30, 2026')
  self.assertTrue(parse(b)['explicit_common_share_title'])
  with self.assertRaises(ProviderFailure):parse(b.replace(b'date-monthname-day-year-en',b'unknown-date'))
 def test_nil_security_title_not_evidence(self):
  b=body().replace(b'name="dei:Security12bTitle"',b'xsi:nil="true" name="dei:Security12bTitle"')
  with self.assertRaises(ProviderFailure):parse(b)
 def test_three_recorded_filings_keep_common_class_separate_from_notes(self):
  root=Path(__file__).parent/'fixtures'
  for symbol,cik,end in [('AAPL',CIK,'2026-06-27'),('MSFT','0000789019','2026-09-30'),('NVDA','0001045810','2026-07-26')]:
   r=parse(gzip.decompress((root/('filing-'+symbol.lower()+'.html.gz')).read_bytes()),cik=cik,symbol=symbol,report_end=date.fromisoformat(end))
   self.assertTrue(r['explicit_common_share_title']);self.assertEqual(len(r['registered_security']),1)
