"""Synthetic directory contracts; never presented as successful live file access."""
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone

from equity_research.models import Exchange,Issuer
from equity_research.nasdaq import (DIRECTORY_URLS,NasdaqDirectories,UniverseStatus,
    build_universe,instrument_status,parse_directory)
from equity_research.providers import ProviderFailure
from equity_research.sec import DIRECTORY_URL,DirectoryEntry,DirectorySnapshot
from equity_research.transport import Response

NOW=datetime(2026,11,1,20,30,tzinfo=timezone.utc)
HEADERS={
 'nasdaqlisted':['Symbol','Security Name','Market Category','Test Issue','Financial Status','Round Lot Size','ETF','NextShares'],
 'otherlisted':['ACT Symbol','Security Name','Exchange','CQS Symbol','ETF','Round Lot Size','Test Issue','NASDAQ Symbol'],
}


def data(name='nasdaqlisted',**changes):
    row=({'Symbol':'AAPL','Security Name':'Apple Inc. - Common Stock','Market Category':'Q','Test Issue':'N','Financial Status':'N','Round Lot Size':'100','ETF':'N','NextShares':'N'}
         if name=='nasdaqlisted' else {'ACT Symbol':'IBM','Security Name':'IBM Common Stock','Exchange':'N','CQS Symbol':'IBM','ETF':'N','Round Lot Size':'100','Test Issue':'N','NASDAQ Symbol':'IBM'})
    row.update(changes);return row


def response(name='nasdaqlisted',rows=None,headers=None,footer='File Creation Time: 1101202615:00'):
    headers=headers or HEADERS[name];rows=rows or [data(name)]
    body='|'.join(headers)+'\n'+'\n'.join('|'.join(row.get(h,'') for h in headers) for row in rows)+'\n'+footer+'|'*(len(headers)-1)+'\n'
    return Response(DIRECTORY_URLS[name],body.encode(),NOW)


def snapshots():return tuple(parse_directory(response(name),name) for name in DIRECTORY_URLS)


def identity():
    return DirectorySnapshot((DirectoryEntry(Issuer('0000320193','Apple'),'AAPL','Nasdaq'),
                              DirectoryEntry(Issuer('0000051143','IBM'),'IBM','NYSE')),
                             DIRECTORY_URL,NOW-timedelta(hours=1),'0'*64)


class NasdaqTests(unittest.TestCase):
    def test_source_provenance_and_footer(self):
        r=response();s=parse_directory(r,'nasdaqlisted')
        self.assertEqual(s.raw_sha256,r.sha256)
        self.assertEqual(s.created_on,NOW.date())
        self.assertEqual(s.creation_label,'File Creation Time: 1101202615:00')
        self.assertEqual(s.rows[0].exchange,Exchange.NASDAQ)

    def test_column_reordering_and_explicit_vendor_aliases(self):
        headers=list(reversed(HEADERS['otherlisted']))
        row=data('otherlisted',**{'ACT Symbol':'BRK.B','CQS Symbol':'BRK/B','NASDAQ Symbol':'BRK-B'})
        s=parse_directory(response('otherlisted',[row],headers),'otherlisted')
        self.assertEqual(s.rows[0].aliases,('BRK.B','BRK/B','BRK-B'))

    def test_corruption_and_truncation_not_partial_success(self):
        r=response()
        bodies=[r.body.rsplit(b'File Creation Time',1)[0],r.body.replace(b'1101202615:00',b'BAD'),
                r.body.replace(b'NextShares',b'ETF'),b'<html>blocked</html>',
                r.body.replace(b'Apple Inc. - Common Stock',b'Apple|extra')]
        for body in bodies:
            with self.subTest(body=body[:40]),self.assertRaises(ProviderFailure):
                parse_directory(replace(r,body=body),'nasdaqlisted')

    def test_duplicate_source_symbol_rejected(self):
        with self.assertRaises(ProviderFailure):
            parse_directory(response(rows=[data(),data()]),'nasdaqlisted')

    def test_two_sources_and_exact_sec_identity(self):
        result=build_universe(snapshots(),identity(),as_of=NOW)
        self.assertEqual([r.status for r in result],[UniverseStatus.CANDIDATE]*2)
        self.assertEqual([r.issuer_id for r in result],['0000320193','0000051143'])
        self.assertFalse(hasattr(result[0].listing,'active'))

    def test_known_non_common_descriptions_override_common_words(self):
        cases=['Company - Units each consisting of Common Stock and a Warrant',
               'Company - American Depositary Shares representing Ordinary Shares',
               'Company - Preferred Stock','Company - Rights','Company - 5% Notes',
               'Company - Closed-End Fund']
        for name in cases:
            row=parse_directory(response(rows=[data(**{'Security Name':name})]),'nasdaqlisted').rows[0]
            with self.subTest(name=name):self.assertEqual(instrument_status(row)[0],UniverseStatus.EXCLUDED_INSTRUMENT)

    def test_etf_nextshares_test_and_unknown_flags(self):
        for changes,status in (({'ETF':'Y'},UniverseStatus.EXCLUDED_INSTRUMENT),
                               ({'NextShares':'Y'},UniverseStatus.EXCLUDED_INSTRUMENT),
                               ({'Test Issue':'Y'},UniverseStatus.TEST_ISSUE),
                               ({'ETF':''},UniverseStatus.PENDING_LISTING)):
            row=parse_directory(response(rows=[data(**changes)]),'nasdaqlisted').rows[0]
            with self.subTest(changes=changes):self.assertEqual(instrument_status(row)[0],status)

    def test_other_exchanges_do_not_enter_scope(self):
        for code in ('P','Z','V','UNKNOWN'):
            row=parse_directory(response('otherlisted',[data('otherlisted',Exchange=code)]),'otherlisted').rows[0]
            self.assertEqual(instrument_status(row)[0],UniverseStatus.OUT_OF_SCOPE_EXCHANGE)
        row=parse_directory(response('otherlisted',[data('otherlisted',Exchange='A')]),'otherlisted').rows[0]
        self.assertEqual(row.exchange,Exchange.NYSE_AMERICAN)

    def test_unknown_type_is_pending_and_issuer_name_not_preferred_type(self):
        for name,status in (('Company Inc.',UniverseStatus.PENDING_CLASSIFICATION),
                            ('Preferred Bank - Common Stock',UniverseStatus.CANDIDATE),
                            ('Company - Ordinary Shares',UniverseStatus.CANDIDATE)):
            row=parse_directory(response(rows=[data(**{'Security Name':name})]),'nasdaqlisted').rows[0]
            self.assertEqual(instrument_status(row)[0],status)

    def test_financial_warning_preserved_not_universe_exclusion(self):
        row=parse_directory(response(rows=[data(**{'Financial Status':'Q'})]),'nasdaqlisted').rows[0]
        self.assertEqual(row.financial_status,'Q')
        self.assertEqual(instrument_status(row)[0],UniverseStatus.CANDIDATE)

    def test_stale_source_pending_and_future_identity_rejected(self):
        parts=list(snapshots());parts[0]=replace(parts[0],created_on=NOW.date()-timedelta(days=5))
        result=build_universe(tuple(parts),identity(),as_of=NOW)
        self.assertEqual(result[0].status,UniverseStatus.PENDING_LISTING)
        self.assertEqual(result[1].status,UniverseStatus.CANDIDATE)
        with self.assertRaises(ValueError):build_universe(snapshots(),replace(identity(),retrieved_at=NOW+timedelta(seconds=1)),as_of=NOW)

    def test_exact_symbol_only_no_punctuation_guess(self):
        parts=list(snapshots());parts[0]=parse_directory(response(rows=[data(Symbol='AAPL.X')]),'nasdaqlisted')
        result=build_universe(tuple(parts),identity(),as_of=NOW)
        self.assertEqual(result[0].status,UniverseStatus.PENDING_IDENTITY)

    def test_exchange_disagreement_pending(self):
        ident=identity();entries=(replace(ident.entries[0],exchange_label='NYSE'),ident.entries[1])
        result=build_universe(snapshots(),replace(ident,entries=entries),as_of=NOW)
        self.assertEqual(result[0].reason,'exchange_disagreement')

    def test_cross_directory_symbol_collision_never_promoted(self):
        parts=(snapshots()[0],parse_directory(response('otherlisted',[data('otherlisted',**{'ACT Symbol':'AAPL','CQS Symbol':'AAPL','NASDAQ Symbol':'AAPL'})]),'otherlisted'))
        result=build_universe(parts,identity(),as_of=NOW)
        self.assertTrue(all(r.status is UniverseStatus.PENDING_IDENTITY for r in result))

    def test_exhaustive_partition_and_no_silent_row_drop(self):
        rows=[data(Symbol='AAPL'),data(Symbol='ETF1',ETF='Y'),data(Symbol='UNKNOWN',**{'Security Name':'Ambiguous Co'}),data(Symbol='NO_CIK')]
        parts=(parse_directory(response(rows=rows),'nasdaqlisted'),snapshots()[1])
        result=build_universe(parts,identity(),as_of=NOW)
        self.assertEqual(len(result),5)
        self.assertEqual(len({(r.source_url,r.listing.symbol) for r in result}),5)
        self.assertEqual({r.status for r in result},{UniverseStatus.CANDIDATE,UniverseStatus.EXCLUDED_INSTRUMENT,UniverseStatus.PENDING_CLASSIFICATION,UniverseStatus.PENDING_IDENTITY})

    def test_both_files_required_and_transport_errors_propagate(self):
        with self.assertRaises(ValueError):build_universe((snapshots()[0],),identity(),as_of=NOW)
        class Missing:
            def get(self,url):raise ProviderFailure(__import__('equity_research.providers',fromlist=['Status']).Status.API_ERROR)
        with self.assertRaises(ProviderFailure):NasdaqDirectories(Missing()).fetch()
