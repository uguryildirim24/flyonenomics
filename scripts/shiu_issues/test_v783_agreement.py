"""Small, data-free tests for the reproduction comparison metrics."""
import unittest

import numpy as np

from v783_agreement import canonical_events, correlation, rates


class AgreementMetricsTest(unittest.TestCase):
    def test_canonical_events_ignore_monitor_order(self):
        a = canonical_events([2, 0, 2], [4, 0, 1], 10001)
        b = canonical_events([2, 2, 0], [1, 4, 0], 10001)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(a, [0, 20003, 20006])

    def test_duplicate_event_is_rejected(self):
        with self.assertRaises(ValueError):
            canonical_events([0, 0], [3, 3], 10001)

    def test_empty_events_and_undefined_correlation(self):
        self.assertEqual(canonical_events([], [], 10001).size, 0)
        self.assertIsNone(correlation([0, 0], [0, 0]))

    def test_silent_neurons_are_included_in_exact_counts(self):
        counts = np.array([[2, 0, 1, 0], [4, 0, 3, 0]])
        result = rates(counts, counts.copy(), 0, 1.0)
        self.assertEqual(result["total_neuron_trial_pairs"], 8)
        self.assertEqual(result["trial_count_equal_neuron_pairs"], 8)
        self.assertEqual(result["union_active_neurons"], 2)
        self.assertAlmostEqual(result["pearson_all_neuron_mean_rates"], 1.0)
        self.assertEqual(result["mn9_paired_rebuild_minus_upstream"]["ci95_hz"], [0.0, 0.0])

    def test_equal_means_are_not_equal_trials(self):
        a = np.array([[2, 0, 1], [4, 0, 3]])
        b = np.array([[4, 0, 1], [2, 0, 3]])
        result = rates(a, b, 0, 1.0)
        self.assertEqual(result["mean_rate_equal_neurons"], 3)
        self.assertEqual(result["trial_count_equal_neuron_pairs"], 4)
        self.assertEqual(result["mn9_paired_rebuild_minus_upstream"]["mean_hz"], 0.0)
        self.assertGreater(result["mn9_paired_rebuild_minus_upstream"]["ci95_hz"][1], 0)


if __name__ == "__main__":
    unittest.main()
