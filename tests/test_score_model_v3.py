"""Model v3: declared, labeled alternate definitions; never silent aliasing."""
import copy,json,unittest
from dataclasses import replace
from equity_research.scoring import ACTIVE_MODEL_VERSION
from test_scoring import financial,comparisons,companyfacts,score

V3='operating-sector-research-batch-v3'
ALT=dict(revenue='revenue_total',capital_expenditure='productive_asset_cash_payments')


def _growth_pair(b):
    cur=copy.deepcopy(b);cur['companies'][0]['fields']=[r for r in cur['companies'][0]['fields'] if r['query']['field']=='revenue_total']
    pri=copy.deepcopy(cur)
    for row in pri['companies'][0]['fields']:
        row['query'].update(period_start='2024-01-01',period_end='2024-12-31')
        row['fact'].update(period_start='2024-01-01',period_end='2024-12-31',value='800')
    return cur,pri


def alt_inputs():
    """Issuer that discloses only Revenues and PaymentsToAcquireProductiveAssets."""
    b=financial(revenue=None,capital_expenditure=None,revenue_total='1000',productive_asset_cash_payments='20')
    cur,pri=_growth_pair(b)
    base=companyfacts();p=json.loads(base.body);g=p['facts']['us-gaap']
    g['Revenues']=g.pop('RevenueFromContractWithCustomerExcludingAssessedTax')
    g['PaymentsToAcquireProductiveAssets']=g.pop('PaymentsToAcquirePropertyPlantAndEquipment')
    return b,cur,pri,replace(base,body=json.dumps(p).encode())


class V3Tests(unittest.TestCase):
    def test_v2_never_scores_on_alternate_definitions(self):
        b,cur,pri,cf=alt_inputs()
        c=score(b=b,current=cur,prior=pri,cf_response=cf,model_version=ACTIVE_MODEL_VERSION)['companies'][0]
        self.assertIsNone(c['total_score']);self.assertEqual(c['status'],'pending_model_inputs')
        self.assertEqual(set(c['missing_fields']),{'revenue','capital_expenditure'})

    def test_v3_scores_with_labeled_alternates_and_same_arithmetic(self):
        b,cur,pri,cf=alt_inputs()
        r=score(b=b,current=cur,prior=pri,cf_response=cf,model_version=V3);c=r['companies'][0]
        self.assertEqual(c['status'],'scored_research_hypothesis');self.assertFalse(c['investment_approved'])
        self.assertEqual(c['total_score'],score(model_version=ACTIVE_MODEL_VERSION)['companies'][0]['total_score'])
        got={a['required_field']:a['used_field'] for a in c['alternate_definitions']}
        self.assertEqual(got,ALT)
        for a in c['alternate_definitions']:
            self.assertEqual(a['policy'],'v3_declared_alternate_not_equivalent_to_required_definition')
        self.assertIn('alternate_definitions_used_not_equivalent_to_required_concepts',c['limitations'])
        self.assertEqual(r['model_version'],V3)

    def test_v3_matches_v2_score_when_required_concepts_exist(self):
        v2=score(model_version=ACTIVE_MODEL_VERSION)['companies'][0]
        v3=score(model_version=V3)['companies'][0]
        self.assertEqual(v2['total_score'],v3['total_score']);self.assertNotIn('alternate_definitions',v3)

    def test_v3_prefers_required_concept_over_alternate(self):
        b=financial(revenue_total='999999')  # conflicting alternate must be ignored
        c=score(b=b,model_version=V3)['companies'][0]
        self.assertNotIn('alternate_definitions',c)
