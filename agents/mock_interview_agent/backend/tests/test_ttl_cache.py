import unittest

from ttl_cache import BoundedTTLCache


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


class BoundedTTLCacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = BoundedTTLCache(60, 2, clock=self.clock)

    def test_returns_cached_copy_until_sixty_second_expiry(self):
        _, generation = self.cache.get_with_generation(1)
        original = {"scores": [7]}
        self.assertTrue(self.cache.set_if_generation(1, original, generation))
        original["scores"].append(9)
        cached = self.cache.get(1)
        self.assertEqual(cached, {"scores": [7]})
        cached["scores"].append(10)
        self.assertEqual(self.cache.get(1), {"scores": [7]})

        self.clock.now = 59.99
        self.assertIsNotNone(self.cache.get(1))
        self.clock.now = 60
        self.assertIsNone(self.cache.get(1))

    def test_evicts_least_recently_used_entry_at_hard_limit(self):
        for key in (1, 2):
            _, generation = self.cache.get_with_generation(key)
            self.cache.set_if_generation(key, {"id": key}, generation)
        self.cache.get(1)  # Student 2 is now least recently used.
        _, generation = self.cache.get_with_generation(3)
        self.cache.set_if_generation(3, {"id": 3}, generation)

        self.assertEqual(self.cache.size(), 2)
        self.assertIsNone(self.cache.get(2))
        self.assertEqual(self.cache.get(1), {"id": 1})
        self.assertEqual(self.cache.get(3), {"id": 3})

    def test_invalidation_removes_entry(self):
        _, generation = self.cache.get_with_generation(7)
        self.cache.set_if_generation(7, {"total": 4}, generation)
        self.cache.invalidate(7)
        self.assertIsNone(self.cache.get(7))

    def test_invalidation_rejects_stale_in_flight_population(self):
        _, old_generation = self.cache.get_with_generation(7)
        self.cache.invalidate(7)
        self.assertFalse(
            self.cache.set_if_generation(7, {"total": 4}, old_generation)
        )
        self.assertIsNone(self.cache.get(7))


if __name__ == "__main__":
    unittest.main()
