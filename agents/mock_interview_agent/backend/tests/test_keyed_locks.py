import threading
import unittest

from keyed_locks import KeyedLockPool


class KeyedLockPoolTests(unittest.TestCase):
    def test_same_key_serializes_waiters_and_evicts_after_last_user(self):
        pool = KeyedLockPool()
        first_entered = threading.Event()
        release_first = threading.Event()
        second_entered = threading.Event()

        def first():
            with pool.acquire((7, 2)):
                first_entered.set()
                release_first.wait(timeout=2)

        def second():
            first_entered.wait(timeout=2)
            with pool.acquire((7, 2)):
                second_entered.set()

        first_thread = threading.Thread(target=first)
        second_thread = threading.Thread(target=second)
        first_thread.start()
        second_thread.start()

        self.assertTrue(first_entered.wait(timeout=1))
        self.assertFalse(second_entered.wait(timeout=0.05))
        release_first.set()
        self.assertTrue(second_entered.wait(timeout=1))

        first_thread.join(timeout=1)
        second_thread.join(timeout=1)
        self.assertEqual(pool.active_key_count(), 0)

    def test_different_keys_run_independently(self):
        pool = KeyedLockPool()
        first_entered = threading.Event()
        release_first = threading.Event()
        other_entered = threading.Event()

        def first():
            with pool.acquire((1, 1)):
                first_entered.set()
                release_first.wait(timeout=2)

        def other():
            first_entered.wait(timeout=2)
            with pool.acquire((2, 1)):
                other_entered.set()

        first_thread = threading.Thread(target=first)
        other_thread = threading.Thread(target=other)
        first_thread.start()
        other_thread.start()

        self.assertTrue(other_entered.wait(timeout=1))
        release_first.set()
        first_thread.join(timeout=1)
        other_thread.join(timeout=1)
        self.assertEqual(pool.active_key_count(), 0)

    def test_exception_releases_and_evicts_entry(self):
        pool = KeyedLockPool()
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with pool.acquire((9, 9)):
                raise RuntimeError("boom")
        self.assertEqual(pool.active_key_count(), 0)


if __name__ == "__main__":
    unittest.main()
