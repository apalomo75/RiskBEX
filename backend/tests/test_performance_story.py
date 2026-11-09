"""Offline presentation tests using small fixtures, without inference or providers."""
import ast
from pathlib import Path
import unittest

from src.riskbex.performance_story import comparison_stories, metric_difference, participation_stories
from test_dashboard_ui import SPANISH


class PerformanceStoryTests(unittest.TestCase):
    def test_signed_metrics_and_zero(self):
        self.assertIn('less severe loss', metric_difference('Expected Shortfall (95%)', -.01, -.02))
        self.assertIn('more severe loss', metric_difference('Maximum Drawdown', -.3, -.2))
        self.assertIn('lower volatility', metric_difference('Annualized Volatility', .1, .2))
        self.assertIn('lower return', metric_difference('Total Return', .5, .8))
        self.assertIn('higher return', metric_difference('Total Return', -.1, -.2))
        self.assertIn('unchanged', metric_difference('Total Return', 0., 0.))
        self.assertIn('unchanged', metric_difference('Maximum Drawdown', -.2, -.200001))
        for value in [None, float('nan'), float('inf')]:
            self.assertIn('unavailable', metric_difference('Total Return', value, 0.))
        self.assertIn('less severe loss', metric_difference('Maximum Drawdown', 0., -.1))

    def test_ml_and_probability_weighting_comparisons(self):
        rows = [dict(Strategy=name, **{'Total Return': ret, 'Annualized Volatility': vol,
                  'Expected Shortfall (95%)': tail, 'Maximum Drawdown': dd,
                  'Total Transaction Costs (Log Return)': cost})
                for name, ret, vol, tail, dd, cost in [
                    ('Buy & Hold', .8, .2, -.03, -.2, 0.),
                    ('Regime-Based', .6, .15, -.02, -.18, .02),
                    ('ML Hard', .5, .16, -.021, -.21, .03),
                    ('ML Probability-Weighted', .49, .14, -.019, -.19, .04)]]
        turns = [{'strategy': name, 'total_turnover': value} for name, value in
                 [('Regime-based', 20.), ('ML Hard Classification', 30.), ('ML Probability-Weighted', 40.)]]
        stories = comparison_stories(rows, ['ML Hard', 'ML Probability-Weighted'], turns)
        hard = next(s for s in stories if s.startswith('ML Hard versus Regime-Based'))
        self.assertIn('Total Return: -10.00', hard)
        self.assertIn('higher volatility', hard)
        self.assertIn('more severe loss', hard)
        self.assertIn('Total Turnover: +10.00 exposure units (higher turnover)', hard)
        self.assertIn('Transaction Costs: +1.00 log-return points (higher costs)', hard)
        weighted = next(s for s in stories if s.startswith('ML Probability-Weighted versus ML Hard'))
        self.assertIn('lower volatility', weighted)
        self.assertIn('less severe loss', weighted)
        self.assertIn('lower return', weighted)
        self.assertIn('higher costs', weighted)

    def test_missing_comparison_and_turnover(self):
        self.assertIn('unavailable', comparison_stories([], ['ML Hard'], [])[0])
        rows = [{'Strategy': name} for name in ['ML Hard', 'Regime-Based']]
        story = comparison_stories(rows, ['ML Hard'], [])[-1]
        self.assertIn('Total Turnover: unavailable', story)
        self.assertIn('Transaction Costs: unavailable', story)
        self.assertNotIn('higher', story)

    def test_participation_gross_net_and_common_sessions(self):
        records = [{'benchmark_return': -.1, 'ml_hard_return': -.05, 'ml_hard_return_net': -.06,
                    'strategy_exposure_ml_hard': .5},
                   {'benchmark_return': .1, 'ml_hard_return': .05, 'ml_hard_return_net': .04,
                    'strategy_exposure_ml_hard': .5},
                   {'benchmark_return': 0., 'ml_hard_return': 0., 'ml_hard_return_net': -.01,
                    'strategy_exposure_ml_hard': .5}]
        gross = participation_stories(records, ['ML Hard'], False)[0]
        net = participation_stories(records, ['ML Hard'], True)[0]
        self.assertIn('1 down-market sessions: average exposure 50.0%, +5.00', gross)
        self.assertIn('less loss than Buy & Hold', gross)
        self.assertIn('-5.00 log-return points (less gain', gross)
        self.assertIn('+4.00 log-return points', net)
        self.assertIn('-6.00 log-return points', net)
        self.assertEqual(participation_stories(records, ['Buy & Hold'], False), [])
        records[0]['ml_hard_return_net'] = None
        self.assertIn('unavailable', participation_stories(records, ['ML Hard'], True)[0])
        self.assertIn('unavailable', participation_stories([], ['ML Hard'], False)[0])

    def test_flat_and_one_sided_markets(self):
        row = dict(benchmark_return=0., ml_hard_return=0., strategy_exposure_ml_hard=0.)
        story = participation_stories([row], ['ML Hard'], False)[0]
        self.assertIn('no down-market sessions', story)
        self.assertIn('no up-market sessions', story)
        row['benchmark_return'] = .1
        self.assertIn('no down-market sessions', participation_stories([row], ['ML Hard'], False)[0])
        row['benchmark_return'] = -.1
        self.assertIn('no up-market sessions', participation_stories([row], ['ML Hard'], False)[0])

    def test_net_costs_can_reverse_protection(self):
        row = dict(benchmark_return=-.01, ml_hard_return=-.005, ml_hard_return_net=-.02,
                   strategy_exposure_ml_hard=.5)
        self.assertIn('less loss', participation_stories([row], ['ML Hard'], False)[0])
        self.assertIn('more loss', participation_stories([row], ['ML Hard'], True)[0])

    def test_english_only_literals(self):
        source = Path(__file__).resolve().parents[1] / 'src/riskbex/performance_story.py'
        offenders = [node.value for node in ast.walk(ast.parse(source.read_text()))
                     if isinstance(node, ast.Constant) and isinstance(node.value, str) and SPANISH.search(node.value)]
        self.assertEqual(offenders, [])
