
from app import init_db
import unittest

class TestInitDB(unittest.TestCase):
    def test_init_db_runs_again(self):
        # Another call to the function to make sure there is no exception
        init_db()
