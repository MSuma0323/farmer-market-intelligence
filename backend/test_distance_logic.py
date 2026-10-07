import unittest

from backend.app import _sanitize_route_distance


class DistanceSanityTest(unittest.TestCase):
    def test_very_long_route_is_reduced_to_conservative_estimate(self):
        # A route that is far more than a reasonable road detour should not be
        # accepted as the true road distance.
        distance = _sanitize_route_distance(17.0, 23.7)
        self.assertLess(distance, 23.7)
        self.assertAlmostEqual(distance, 22.1, places=1)

    def test_normal_route_is_kept(self):
        distance = _sanitize_route_distance(17.0, 19.5)
        self.assertAlmostEqual(distance, 19.5, places=1)


if __name__ == "__main__":
    unittest.main()
