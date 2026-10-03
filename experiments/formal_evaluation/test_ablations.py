import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deepseek_refinement'))
from ablations import random_rules
import shadow


class AblationChecks(unittest.TestCase):
    def test_random_rules_fixed(self):
        first=random_rules();self.assertEqual(first,random_rules())
        self.assertEqual(len(first),3)
        for candidate in first:
            self.assertEqual(len(candidate['rules']),3)
            self.assertTrue(all(-2<=int(r['delta'])<=2 for r in candidate['rules']))

    def test_search_only_skips_review(self):
        candidates=[{'id':'zero'},{'id':'a'},{'id':'b'}]
        def fake(candidate,*args,**kwargs):return dict(id=candidate['id'],valid=True,cost={'zero':10,'a':8,'b':7}[candidate['id']],downstream=1)
        with patch.object(shadow,'score',side_effect=fake) as score:
            chosen,result=shadow.select(candidates,{},[],[],[],[],[],([[]],[[]]),review=False)
            self.assertEqual(chosen,'b');self.assertEqual(score.call_count,3)
            self.assertIsNone(result['validation_candidate'])
        with patch.object(shadow,'score',side_effect=fake) as score:
            chosen,result=shadow.select(candidates,{},[],[],[],[],[],([[]],[[]]))
            self.assertEqual(chosen,'b');self.assertEqual(score.call_count,5)


if __name__=='__main__':unittest.main()
