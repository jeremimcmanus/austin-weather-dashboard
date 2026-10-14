import unittest
from backtest import evaluate
class BacktestTests(unittest.TestCase):
    def row(self,event,day,p,y):
        return dict(event_id=event,prediction_at=f'2026-01-{day}T01:00:00Z',event_close=f'2026-01-{day}T22:00:00Z',settled_at=f'2026-01-{day}T23:00:00Z',probability=p,outcome=y)
    def test_chronological_baseline(self):
        result=evaluate([self.row('train','01',.4,1),self.row('holdout','03',.8,1)],'2026-01-02T00:00:00Z')
        self.assertAlmostEqual(result['holdout_brier'],.04)
        self.assertEqual(result['baseline_brier'],0)
    def test_refuses_post_close_prediction(self):
        row=self.row('bad','03',.8,1);row['prediction_at']='2026-01-04T00:00:00Z'
        with self.assertRaises(ValueError):evaluate([row],'2026-01-02T00:00:00Z')
    def test_refuses_duplicate_events(self):
        row=self.row('same','01',.4,1)
        with self.assertRaises(ValueError):evaluate([row,row],'2026-01-02T00:00:00Z')
if __name__=='__main__':unittest.main()
