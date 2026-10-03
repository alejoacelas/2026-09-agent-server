import sqlite3
import unittest
from server import expression, search

class SearchTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE VIRTUAL TABLE search USING fts5(title, text, prefix='2 3 4')")
        self.db.executemany('INSERT INTO search(title,text) VALUES(?,?)', [
            ('Quantum mechanics', 'Quantum mechanics explains the behavior of atoms.'),
            ('Octopus', 'An octopus is a sea animal.'),
            ('Atomic physics', 'Physics includes quantum mechanics and many other subjects.')])

    def tearDown(self):
        self.db.close()

    def test_prefix_and_rank(self):
        rows = search(self.db, 'quantum mec')
        self.assertEqual(rows[0]['title'], 'Quantum mechanics')
        self.assertEqual(len(rows), 2)
        self.assertIn('\x01', rows[1]['snippet'])

    def test_exact_title_beats_short_incidental_mentions(self):
        self.db.execute('INSERT INTO search(title,text) VALUES(?,?)', ('Quantum mechanics', 'Quantum mechanics. ' + 'A long explanation. ' * 500))
        self.assertEqual(search(self.db, 'Quantum mechanics')[0]['title'], 'Quantum mechanics')

    def test_untrusted_syntax_is_literal(self):
        for q in ['"', '*', '() :', 'OR NOT', '" OR 1=1 --']:
            search(self.db, q)
        self.assertEqual(expression('!!!'), '')
        self.assertEqual(search(self.db, 'zzzzmissing'), [])

if __name__ == '__main__':
    unittest.main()
