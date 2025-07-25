#__init__
import unittest
from db import get_db

class TestInitDB(unittest.TestCase):
    def test_init_db_runs(self):
        db_gen = get_db()
        db = next(db_gen)
        self.assertIsNotNone(db)
        try:
            next(db_gen)
        except StopIteration:
            pass